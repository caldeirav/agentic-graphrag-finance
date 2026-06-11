"""Flat-chunk dense embedding baseline (012)."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from evaluation.reproduction.snapshot_loader import load_bundle_snapshot
from models.enums import GraphNodeType
from models.graph import GraphSnapshot
from models.query import AnswerPackage, EvidenceChunk
from models.reproduction import SystemVariantConfig

EVIDENCE_TYPES = frozenset(
    {
        GraphNodeType.CHUNK_PARAGRAPH,
        GraphNodeType.CHUNK_XBRL_FACT,
        GraphNodeType.CHUNK_TABLE,
        GraphNodeType.CHUNK_ROW,
    }
)
_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
_HASH_EMBED_DIM = 64
_ENCODE_BATCH_SIZE = 32


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _hash_embed(text: str, dim: int = _HASH_EMBED_DIM) -> list[float]:
    vec = [0.0] * dim
    for tok in _tokenize(text):
        h = int(hashlib.sha256(tok.encode()).hexdigest(), 16)
        idx = h % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        msg = f"Embedding dimension mismatch: {len(a)} vs {len(b)}"
        raise ValueError(msg)
    return sum(x * y for x, y in zip(a, b, strict=True))


def _to_vector(raw) -> list[float]:
    return [float(x) for x in raw]


@dataclass
class ChunkRecord:
    node_id: str
    text: str
    source: str = ""


class FlatChunkBaseline:
    """Dense retrieval over frozen corpus chunks without graph navigation."""

    def __init__(
        self,
        *,
        bundle_root: Path,
        variant: SystemVariantConfig,
        snapshot: GraphSnapshot | None = None,
    ) -> None:
        self._variant = variant
        if snapshot is not None:
            self._snapshot = snapshot
        else:
            _, self._snapshot = load_bundle_snapshot(bundle_root)
        self._records = self._load_records(self._snapshot)
        self._cache_dir = bundle_root / "corpus" / "chunk_embeddings" / (
            variant.embedding_cache_subdir or "hash-fallback"
        )
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._st_model = self._load_sentence_transformer()
        self._chunk_vectors = self._load_or_build_chunk_vectors()

    @staticmethod
    def _load_records(snapshot: GraphSnapshot) -> list[ChunkRecord]:
        records: list[ChunkRecord] = []
        for node in snapshot.nodes:
            if node.node_type not in EVIDENCE_TYPES:
                continue
            text = str(node.properties.get("text") or node.label or node.node_id)
            source = str(node.properties.get("source") or node.properties.get("sec_source") or "")
            records.append(ChunkRecord(node_id=node.node_id, text=text, source=source))
        return records

    def _load_sentence_transformer(self):
        try:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415

            cache_key = hashlib.sha256(_MODEL_ID.encode()).hexdigest()[:16]
            marker = self._cache_dir / f"model-{cache_key}.json"
            if not marker.exists():
                marker.write_text(json.dumps({"model_id": _MODEL_ID}), encoding="utf-8")
            return SentenceTransformer(_MODEL_ID)
        except Exception:
            return None

    def _vectors_cache_path(self) -> Path:
        model_tag = "minilm" if self._st_model is not None else "hash"
        return self._cache_dir / f"vectors-{model_tag}-{self._snapshot.snapshot_id}.json"

    def _expected_embed_dim(self) -> int:
        if self._st_model is not None:
            dim_fn = getattr(self._st_model, "get_embedding_dimension", None)
            if callable(dim_fn):
                return int(dim_fn())
            return int(self._st_model.get_sentence_embedding_dimension())
        return _HASH_EMBED_DIM

    def _cache_is_valid(self, cached: dict[str, list], expected_ids: set[str]) -> bool:
        if set(cached.keys()) != expected_ids:
            return False
        if not cached:
            return True
        sample = cached[next(iter(cached))]
        return len(sample) == self._expected_embed_dim()

    def _load_or_build_chunk_vectors(self) -> dict[str, list[float]]:
        expected_ids = {rec.node_id for rec in self._records}
        cache_path = self._vectors_cache_path()
        if cache_path.is_file():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if self._cache_is_valid(cached, expected_ids):
                return {node_id: _to_vector(vec) for node_id, vec in cached.items()}

        vectors = self._encode_records(self._records)
        cache_path.write_text(json.dumps(vectors), encoding="utf-8")
        return vectors

    def _encode_records(self, records: list[ChunkRecord]) -> dict[str, list[float]]:
        if not records:
            return {}
        if self._st_model is not None:
            texts = [rec.text for rec in records]
            encoded = []
            for start in range(0, len(texts), _ENCODE_BATCH_SIZE):
                batch = texts[start : start + _ENCODE_BATCH_SIZE]
                batch_vecs = self._st_model.encode(
                    batch,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                encoded.extend(batch_vecs)
            return {
                rec.node_id: _to_vector(vec)
                for rec, vec in zip(records, encoded, strict=True)
            }
        return {rec.node_id: _hash_embed(rec.text) for rec in records}

    def _embed_query(self, text: str) -> list[float]:
        if self._st_model is not None:
            return _to_vector(self._st_model.encode(text, normalize_embeddings=True))
        return _hash_embed(text)

    def retrieve(self, query: str, *, top_k: int | None = None) -> list[str]:
        k = top_k or self._variant.top_k
        if not self._records:
            return []
        q_vec = self._embed_query(query)
        scored = [(_cosine(q_vec, self._chunk_vectors[rec.node_id]), rec.node_id) for rec in self._records]
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [node_id for _, node_id in scored[:k]]

    def answer(self, query: str, *, top_k: int | None = None) -> tuple[list[str], AnswerPackage]:
        chunk_ids = self.retrieve(query, top_k=top_k)
        citations = [
            EvidenceChunk(
                chunk_node_id=cid,
                excerpt=next((r.text for r in self._records if r.node_id == cid), cid),
                content_hash=cid,
                accession="",
                section_id="",
            )
            for cid in chunk_ids
        ]
        if not citations:
            answer = AnswerPackage(
                text="Insufficient evidence in flat-chunk retrieval.",
                citations=[],
            )
            return chunk_ids, answer
        body = "\n\n".join(c.excerpt[:500] for c in citations)
        answer = AnswerPackage(
            text=f"Based on retrieved chunks:\n{body[:2000]}",
            citations=citations,
        )
        return chunk_ids, answer
