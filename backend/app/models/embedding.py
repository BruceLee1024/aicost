"""Embedding — Sprint 9 Phase 3 persistent vector store.

Stores semantic vectors for projects, skill chunks, and other entities so
RAG tools can retrieve them by cosine similarity. Schema is provider-aware
(``provider`` column) so we never mix vectors from different embedding
backends in a single nearest-neighbor search.

The dimension is intentionally not constrained at the column level — the
JSON-encoded vector is variable-length and we filter by provider+dim at
query time. This avoids any migration when switching from
``hash:256`` to ``openai:1536``.
"""

from datetime import datetime, timezone

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Logical addressing ──
    # namespace ∈ {"project", "skill", "boq_template", ...}
    namespace: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # ref_id: id of the source row (e.g. project.id, skill.id)
    ref_id: Mapped[str] = mapped_column(String(80), nullable=False)
    # Optional sub-key for splittable assets (e.g. skill chunk index)
    sub_key: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # ── Vector + metadata ──
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    # JSON-encoded list[float]
    vector_json: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON-encoded dict — anything callers want to retrieve alongside the hit
    meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Original snippet (for skill chunks) ──
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(),
    )

    __table_args__ = (
        Index("idx_embeddings_namespace_provider", "namespace", "provider"),
        Index("idx_embeddings_namespace_ref", "namespace", "ref_id"),
    )
