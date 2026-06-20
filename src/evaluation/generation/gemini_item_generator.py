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
from evaluation.generation.comparison_gt import format_generation_validation_feedback
from evaluation.generation.v2_item_normalize import normalize_v2_item
from evaluation.judges.gemini_panel import JudgeParseError, _extract_json
from models.benchmark_generation import AnswerType, GeneratedBenchmarkItem, GenerationConfig, SamplingManifest
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
        negative_questions: list[str] | None = None,
        blocked_tickers: list[str] | None = None,
    ) -> str:
        profile_cfg = self._load_profile(profile)
        template = str(profile_cfg.get("prompt_template", ""))
        v2 = self._config.bundle_schema_version.startswith("2")
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
            feedback_block = format_generation_validation_feedback(
                validation_feedback,
                profile=profile,
            )
        negative_block = ""
        if negative_questions:
            negative_block = (
                "\nDo NOT repeat or closely paraphrase these prior accepted questions "
                f"for profile {profile}:\n"
                + "\n".join(f"- {q}" for q in negative_questions[:20])
                + "\n"
            )
        blocked_block = ""
        if blocked_tickers:
            blocked_block = (
                "\nIssuer caps reached for these tickers in this profile — "
                "prefer other sampled issuers:\n"
                + ", ".join(blocked_tickers)
                + "\n"
            )
        profile_v2 = ""
        if v2:
            if profile == "financebench":
                profile_v2 = (
                    "- financebench v2: use answer_type numeric or short_label for numeric answers; "
                    "omit required_claims for numeric/short_label.\n"
                )
            elif profile == "finder":
                profile_v2 = (
                    "- finder v2: ground_truth.answer is REQUIRED (prose evidence summary); "
                    "answer_type narrative with 2-8 required_claims decomposed from the answer.\n"
                )
            elif profile == "finagentbench":
                profile_v2 = (
                    "- finagentbench v2: answer_type comparison_structured; >=2 accessions; "
                    "canonical answer MUST state a compared conclusion (difference, similarity, "
                    "or relative emphasis), not only section co-occurrence; "
                    ">=3 required_claims (per-filing + cross-filing).\n"
                    "- Valid canonical answers: 'Both {A} and {B} discuss ... differently' OR "
                    "'Both {A} and {B} emphasize ... whereas ...'.\n"
                )
        rules_tail = (
            "- v2 bundle: ground_truth.answer is REQUIRED for every profile (non-empty).\n"
            "- v2 bundle: narrative items need 2-8 required_claims; comparison_structured needs >=3.\n"
            "- v2 comparison answers MUST include a compared conclusion (whereas/while/emphasizes/differs), "
            "not only that both filings mention a topic.\n"
            f"{profile_v2}"
            if v2
            else (
                "- finder profile MUST include ground_truth.rubric.\n"
                "- financebench profile MUST include ground_truth.answer.\n"
            )
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
            f"{feedback_block}{negative_block}{blocked_block}\n"
            "Return ONLY valid JSON with this shape (no markdown fences):\n"
            "{\n"
            '  "question": "string",\n'
            '  "question_type_tag": "string",\n'
            '  "answer_type": "numeric|short_label|narrative|comparison_structured",\n'
            '  "ground_truth": {"answer": "string", "required_claims": ["..."], "rubric": null},\n'
            '  "expected_bindings": {"accessions": ["..."], "fiscal_periods": ["..."]},\n'
            '  "expected_section_paths": ["accession/section_slug", "..."],\n'
            '  "multi_filing_required": false,\n'
            '  "operation_class": "QUALITATIVE"\n'
            "}\n"
            "Rules:\n"
            "- Every expected_bindings.accessions value MUST appear in sampled issuers.\n"
            "- Every expected_section_paths entry MUST be copied exactly from available_section_paths.\n"
            "- NEVER paste answer text, dollar amounts, or sentence fragments into expected_section_paths; "
            "use section slugs only (e.g. Item 1A. Risk Factors, Item 7. Management's Discussion, "
            "XBRL Financial Facts).\n"
            "- finagentbench profile MUST use >=2 accessions and set multi_filing_required true.\n"
            f"{rules_tail}"
        )

    def generate_one(
        self,
        *,
        profile: str,
        seq: int,
        sampling: SamplingManifest,
        section_paths: list[str],
        validation_feedback: str | None = None,
        negative_questions: list[str] | None = None,
        blocked_tickers: list[str] | None = None,
    ) -> tuple[GeneratedBenchmarkItem, int]:
        """Returns parsed item and Gemini call duration in milliseconds."""
        self.require_api_key()
        prompt = self._build_prompt(
            profile=profile,
            seq=seq,
            sampling=sampling,
            section_paths=section_paths,
            validation_feedback=validation_feedback,
            negative_questions=negative_questions,
            blocked_tickers=blocked_tickers,
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
        answer_type_raw = data.get("answer_type")
        answer_type: AnswerType | None = None
        if answer_type_raw:
            try:
                answer_type = AnswerType(str(answer_type_raw).lower())
            except ValueError:
                answer_type = None
        try:
            operation_class = OperationClass(op_raw)
        except ValueError:
            operation_class = OperationClass.QUALITATIVE
        answer = gt_raw.get("answer")
        required_claims = list(gt_raw.get("required_claims") or [])
        v2 = self._config.bundle_schema_version.startswith("2")
        item_id = str(data.get("item_id") or f"v2-{profile}-{seq:04d}" if v2 else f"live-{profile}-{seq:04d}")
        item = GeneratedBenchmarkItem(
            item_id=item_id,
            question=str(data.get("question", "")).strip(),
            question_type_tag=str(data.get("question_type_tag", f"{profile}-generated")),
            answer_type=answer_type,
            inspiration_profile=profile,  # type: ignore[arg-type]
            ground_truth=GroundTruth(
                answer=answer,
                rubric=gt_raw.get("rubric"),
                relevant_chunk_ids=list(gt_raw.get("relevant_chunk_ids") or []),
                required_claims=required_claims or None,
                answer_type=answer_type.value if answer_type else None,
            ),
            expected_bindings=ExpectedBindings(
                accessions=[str(a) for a in bindings_raw.get("accessions") or []],
                fiscal_periods=[str(p) for p in bindings_raw.get("fiscal_periods") or []],
            ),
            expected_section_paths=[str(p) for p in data.get("expected_section_paths") or []],
            multi_filing_required=bool(data.get("multi_filing_required", profile == "finagentbench")),
            operation_class=operation_class,
        )
        if v2:
            item = normalize_v2_item(item)
        return item
