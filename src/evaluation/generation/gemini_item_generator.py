"""Live Gemini benchmark item generation (011)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import yaml
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from evaluation.generation.api_retry import with_transient_retry
from evaluation.judges.gemini_panel import JudgeParseError, _extract_json
from models.benchmark_generation import GeneratedBenchmarkItem, GenerationConfig, SamplingManifest
from models.enums import OperationClass
from models.evaluation import ExpectedBindings, GroundTruth


class GeminiItemGenerator:
    """Generate ``GeneratedBenchmarkItem`` rows via Gemini JSON completion."""

    def __init__(
        self,
        config: GenerationConfig,
        *,
        repo_root: Path | None = None,
    ) -> None:
        self._config = config
        self._root = repo_root or Path(__file__).resolve().parents[3]
        judge_path = self._resolve_path(config.generation_judge_config)
        self._judge_cfg = yaml.safe_load(judge_path.read_text(encoding="utf-8")) or {}
        self._model = str(self._judge_cfg.get("model", config.generation_judge_version))
        self._temperature = float(self._judge_cfg.get("temperature", 0))

    @staticmethod
    def require_api_key() -> None:
        if not os.environ.get("GOOGLE_API_KEY", "").strip():
            msg = "GOOGLE_API_KEY is required for live Gemini item generation (unset USE_MOCK_JUDGE)"
            raise RuntimeError(msg)

    @property
    def model_name(self) -> str:
        return self._model

    def _resolve_path(self, path: str) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else self._root / candidate

    def _load_profile(self, profile: str) -> dict[str, object]:
        rel = self._config.inspiration_profile_paths[profile]
        return yaml.safe_load(self._resolve_path(rel).read_text(encoding="utf-8")) or {}

    def _build_prompt(
        self,
        *,
        profile: str,
        seq: int,
        sampling: SamplingManifest,
        section_paths: list[str],
        validation_feedback: str | None = None,
    ) -> str:
        profile_cfg = self._load_profile(profile)
        template = str(profile_cfg.get("prompt_template", ""))
        issuers = [
            {
                "ticker": i.ticker,
                "accessions": i.accessions,
                "rationale": i.selection_rationale,
            }
            for i in sampling.selected_issuers
        ]
        paths_preview = section_paths[:80]
        feedback_block = ""
        if validation_feedback:
            feedback_block = (
                f"\nPrevious attempt failed validation:\n{validation_feedback}\n"
                "Fix the JSON so all section paths exist in available_section_paths.\n"
            )
        return (
            "You author evaluation benchmark items grounded in a materialized SEC/XBRL corpus.\n"
            f"Inspiration profile: {profile}\n"
            f"Profile config:\n{yaml.safe_dump(profile_cfg)}\n"
            f"Template:\n{template}\n"
            f"Item sequence: {seq}\n"
            f"Sampled issuers JSON:\n{json.dumps(issuers, indent=2)}\n"
            f"Available section paths ({len(section_paths)} total, showing up to 80):\n"
            f"{json.dumps(paths_preview, indent=2)}\n"
            f"{feedback_block}\n"
            "Return ONLY valid JSON with this shape (no markdown fences):\n"
            "{\n"
            '  "question": "string",\n'
            '  "question_type_tag": "string",\n'
            '  "ground_truth": {"answer": "string or null", "rubric": "string or null"},\n'
            '  "expected_bindings": {"accessions": ["..."], "fiscal_periods": ["..."]},\n'
            '  "expected_section_paths": ["accession/section_slug", "..."],\n'
            '  "multi_filing_required": false,\n'
            '  "operation_class": "QUALITATIVE"\n'
            "}\n"
            "Rules:\n"
            "- Every expected_bindings.accessions value MUST appear in sampled issuers.\n"
            "- Every expected_section_paths entry MUST be copied exactly from available_section_paths.\n"
            "- finagentbench profile MUST use >=2 accessions and set multi_filing_required true.\n"
            "- finder profile MUST include ground_truth.rubric.\n"
            "- financebench profile MUST include ground_truth.answer.\n"
        )

    def generate_one(
        self,
        *,
        profile: str,
        seq: int,
        sampling: SamplingManifest,
        section_paths: list[str],
        validation_feedback: str | None = None,
    ) -> tuple[GeneratedBenchmarkItem, int]:
        """Returns parsed item and Gemini call duration in milliseconds."""
        self.require_api_key()
        prompt = self._build_prompt(
            profile=profile,
            seq=seq,
            sampling=sampling,
            section_paths=section_paths,
            validation_feedback=validation_feedback,
        )
        llm = ChatGoogleGenerativeAI(model=self._model, temperature=self._temperature)
        started = time.perf_counter()

        def _invoke():
            return llm.invoke([HumanMessage(content=prompt)])

        resp = with_transient_retry(_invoke, label="Gemini")
        duration_ms = int((time.perf_counter() - started) * 1000)
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        item = self._parse_item(text, profile=profile, seq=seq)
        return item, duration_ms

    def _parse_item(self, text: str, *, profile: str, seq: int) -> GeneratedBenchmarkItem:
        try:
            data = _extract_json(text)
        except json.JSONDecodeError as exc:
            raise JudgeParseError(str(exc)) from exc
        if not isinstance(data, dict):
            raise JudgeParseError("Gemini response must be a JSON object")
        gt_raw = data.get("ground_truth") or {}
        bindings_raw = data.get("expected_bindings") or {}
        op_raw = str(data.get("operation_class", OperationClass.QUALITATIVE.value)).upper()
        try:
            operation_class = OperationClass(op_raw)
        except ValueError:
            operation_class = OperationClass.QUALITATIVE
        return GeneratedBenchmarkItem(
            item_id=str(data.get("item_id") or f"live-{profile}-{seq:04d}"),
            question=str(data.get("question", "")).strip(),
            question_type_tag=str(data.get("question_type_tag", f"{profile}-generated")),
            inspiration_profile=profile,  # type: ignore[arg-type]
            ground_truth=GroundTruth(
                answer=gt_raw.get("answer"),
                rubric=gt_raw.get("rubric"),
                relevant_chunk_ids=list(gt_raw.get("relevant_chunk_ids") or []),
            ),
            expected_bindings=ExpectedBindings(
                accessions=[str(a) for a in bindings_raw.get("accessions") or []],
                fiscal_periods=[str(p) for p in bindings_raw.get("fiscal_periods") or []],
            ),
            expected_section_paths=[str(p) for p in data.get("expected_section_paths") or []],
            multi_filing_required=bool(data.get("multi_filing_required", profile == "finagentbench")),
            operation_class=operation_class,
        )
