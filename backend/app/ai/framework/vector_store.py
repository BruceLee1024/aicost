"""Sprint 9 Phase 3 — persistent vector store.

A thin facade over the ``embeddings`` SQLAlchemy table that:

  - upserts vectors keyed by ``(namespace, ref_id, sub_key)``
  - searches by cosine similarity (in-memory; SQLite has no native ANN)
  - filters by ``provider`` so we never mix dimensions or backends

Quality scaling:
  - For < ~10K vectors per namespace, naive scan is fine on a laptop
    (≤30ms with hash:256 dim and pure Python).
  - The interface stays narrow so we can swap to FAISS / pgvector /
    Qdrant later without touching call sites.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session

from app.ai.framework.embedding_provider import (
    EmbeddingError,
    EmbeddingProvider,
    get_embedding_provider,
)
from app.ai.framework.vector_utils import dot, l2_norm, top_k
from app.models.embedding import Embedding

logger = logging.getLogger(__name__)


@dataclass
class SimilarHit:
    ref_id: str
    sub_key: str | None
    score: float
    snippet: str | None
    meta: dict[str, Any]


class VectorStore:
    """Persistent vector store backed by the ``embeddings`` table.

    A ``VectorStore`` is bound to a single SQLAlchemy session — instantiate
    one per request / unit of work and let SQLAlchemy manage the lifecycle.
    """

    def __init__(
        self,
        db: Session,
        provider: EmbeddingProvider | None = None,
    ) -> None:
        self.db = db
        self.provider = provider or get_embedding_provider()

    # ── Mutation ─────────────────────────────────────────────────

    def upsert(
        self,
        *,
        namespace: str,
        ref_id: str,
        text: str,
        sub_key: str | None = None,
        meta: dict[str, Any] | None = None,
        snippet: str | None = None,
    ) -> int:
        """Embed ``text`` and store; replaces any existing entry with the
        same ``(namespace, ref_id, sub_key, provider)`` key.

        Returns the row id.
        """
        try:
            vec = self.provider.embed(text)
        except EmbeddingError as e:
            logger.warning("upsert: embedding failed (%s); skipping %s/%s", e, namespace, ref_id)
            raise

        # Delete prior entry under same key to keep upsert semantics simple.
        self.db.execute(
            delete(Embedding).where(
                and_(
                    Embedding.namespace == namespace,
                    Embedding.ref_id == ref_id,
                    Embedding.sub_key.is_(sub_key) if sub_key is None else Embedding.sub_key == sub_key,
                    Embedding.provider == self.provider.name,
                )
            )
        )

        row = Embedding(
            namespace=namespace,
            ref_id=ref_id,
            sub_key=sub_key,
            provider=self.provider.name,
            dim=len(vec),
            vector_json=json.dumps(vec),
            meta_json=json.dumps(meta, ensure_ascii=False) if meta else None,
            snippet=(snippet or text)[:2000],
        )
        self.db.add(row)
        self.db.flush()
        return row.id

    def upsert_many(
        self,
        namespace: str,
        items: Iterable[dict[str, Any]],
    ) -> int:
        """Bulk upsert. Each item: {ref_id, text, sub_key?, meta?, snippet?}."""
        items_list = list(items)
        if not items_list:
            return 0
        texts = [item["text"] for item in items_list]
        try:
            vectors = self.provider.embed_many(texts)
        except EmbeddingError as e:
            logger.warning("upsert_many: embedding failed (%s)", e)
            raise

        count = 0
        for item, vec in zip(items_list, vectors):
            ref_id = str(item["ref_id"])
            sub_key = item.get("sub_key")
            self.db.execute(
                delete(Embedding).where(
                    and_(
                        Embedding.namespace == namespace,
                        Embedding.ref_id == ref_id,
                        Embedding.sub_key.is_(sub_key) if sub_key is None else Embedding.sub_key == sub_key,
                        Embedding.provider == self.provider.name,
                    )
                )
            )
            row = Embedding(
                namespace=namespace,
                ref_id=ref_id,
                sub_key=sub_key,
                provider=self.provider.name,
                dim=len(vec),
                vector_json=json.dumps(vec),
                meta_json=json.dumps(item.get("meta"), ensure_ascii=False)
                if item.get("meta")
                else None,
                snippet=(item.get("snippet") or item["text"])[:2000],
            )
            self.db.add(row)
            count += 1
        self.db.flush()
        return count

    def delete_namespace(self, namespace: str, ref_id: str | None = None) -> int:
        """Delete entries by namespace (and optionally ref_id). Returns count."""
        stmt = delete(Embedding).where(Embedding.namespace == namespace)
        if ref_id is not None:
            stmt = stmt.where(Embedding.ref_id == str(ref_id))
        result = self.db.execute(stmt)
        return result.rowcount or 0

    # ── Query ────────────────────────────────────────────────────

    def search(
        self,
        namespace: str,
        query: str,
        *,
        top_n: int = 5,
        min_score: float | None = None,
        exclude_ref_ids: set[str] | None = None,
    ) -> list[SimilarHit]:
        """Cosine top-k search within ``namespace`` for the active provider.

        Vectors are L2-normalized at ingest, so cosine reduces to dot product.
        """
        try:
            qvec = self.provider.embed(query)
        except EmbeddingError as e:
            logger.warning("search: embedding failed (%s); returning empty list", e)
            return []
        return self._search_vec(
            namespace,
            qvec,
            top_n=top_n,
            min_score=min_score,
            exclude_ref_ids=exclude_ref_ids,
        )

    def search_by_vector(
        self,
        namespace: str,
        vector: list[float],
        *,
        top_n: int = 5,
        min_score: float | None = None,
        exclude_ref_ids: set[str] | None = None,
    ) -> list[SimilarHit]:
        return self._search_vec(
            namespace,
            vector,
            top_n=top_n,
            min_score=min_score,
            exclude_ref_ids=exclude_ref_ids,
        )

    def _search_vec(
        self,
        namespace: str,
        qvec: list[float],
        *,
        top_n: int,
        min_score: float | None,
        exclude_ref_ids: set[str] | None,
    ) -> list[SimilarHit]:
        if not qvec:
            return []
        # Normalize query defensively
        n = l2_norm(qvec)
        if n == 0:
            return []
        qvec = [x / n for x in qvec]

        rows = (
            self.db.execute(
                select(Embedding).where(
                    and_(
                        Embedding.namespace == namespace,
                        Embedding.provider == self.provider.name,
                        Embedding.dim == len(qvec),
                    )
                )
            )
            .scalars()
            .all()
        )

        excluded = exclude_ref_ids or set()
        scored: list[tuple[float, Embedding]] = []
        for row in rows:
            if row.ref_id in excluded:
                continue
            try:
                rv = json.loads(row.vector_json)
            except (TypeError, ValueError):
                continue
            if len(rv) != len(qvec):
                continue
            score = dot(qvec, rv)
            scored.append((score, row))

        top = top_k(scored, top_n, min_score=min_score)
        return [
            SimilarHit(
                ref_id=row.ref_id,
                sub_key=row.sub_key,
                score=float(score),
                snippet=row.snippet,
                meta=json.loads(row.meta_json) if row.meta_json else {},
            )
            for score, row in top
        ]

    # ── Introspection ────────────────────────────────────────────

    def count(self, namespace: str) -> int:
        return (
            self.db.query(Embedding)
            .filter(
                Embedding.namespace == namespace,
                Embedding.provider == self.provider.name,
            )
            .count()
        )
