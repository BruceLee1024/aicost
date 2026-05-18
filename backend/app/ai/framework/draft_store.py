"""Sprint 9 — Phase 2 draft store.

Process-level in-memory keyed cache for BOQ drafts. The
``propose_boq_items`` tool runs in the orchestrator's worker thread, so
its ``ctx`` is discarded after the SSE stream completes. To let the
frontend fetch the editable draft, we store it in this module-level
cache keyed by ``draft_token`` and TTL-evict old entries.

Thread-safe via a single lock — each entry is small (≤200 BOQ items).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DraftEntry:
    project_id: int
    items: list[dict[str, Any]]
    created_at: float = field(default_factory=time.time)


class _DraftStore:
    """Thread-safe TTL cache for BOQ drafts."""

    DEFAULT_TTL_SEC = 60 * 60  # 1 hour
    MAX_ENTRIES = 200

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, DraftEntry] = {}

    def _evict_expired_locked(self) -> None:
        now = time.time()
        expired = [
            tok
            for tok, e in self._entries.items()
            if now - e.created_at > self.DEFAULT_TTL_SEC
        ]
        for tok in expired:
            self._entries.pop(tok, None)

    def put(self, token: str, project_id: int, items: list[dict[str, Any]]) -> None:
        with self._lock:
            self._evict_expired_locked()
            # Cap total entries — drop oldest first
            if len(self._entries) >= self.MAX_ENTRIES:
                oldest_tok = min(
                    self._entries.keys(),
                    key=lambda k: self._entries[k].created_at,
                )
                self._entries.pop(oldest_tok, None)
            self._entries[token] = DraftEntry(
                project_id=project_id,
                items=list(items),
            )

    def get(self, token: str) -> DraftEntry | None:
        with self._lock:
            self._evict_expired_locked()
            return self._entries.get(token)

    def pop(self, token: str) -> DraftEntry | None:
        with self._lock:
            return self._entries.pop(token, None)

    def list_for_project(self, project_id: int) -> list[tuple[str, DraftEntry]]:
        with self._lock:
            self._evict_expired_locked()
            return [
                (tok, e)
                for tok, e in self._entries.items()
                if e.project_id == project_id
            ]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


# Process-wide singleton
_store = _DraftStore()


def get_draft_store() -> _DraftStore:
    return _store
