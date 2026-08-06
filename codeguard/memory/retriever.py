from codeguard.memory.models import MemoryRecord, MemoryType, MemoryStatus, TrustLevel
from codeguard.memory.store import JSONMemoryStore

_TRUST_ORDER = {
    TrustLevel.USER_APPROVED: 3,
    TrustLevel.HARNESS_VERIFIED: 2,
    TrustLevel.LLM_PROPOSED: 1,
}


class MemoryRetriever:
    """Retrieves and filters memory records with deterministic ordering.

    Pipeline: project_id isolation → ACTIVE only → type filter →
    exact tags match → keywords match → sort (trust_level DESC,
    updated_at DESC, id ASC) → top_k → context_budget truncation.
    """

    def __init__(self, store: JSONMemoryStore, top_k: int = 10, context_budget: int = 2048):
        self._store = store
        self._top_k = top_k
        self._context_budget = context_budget

    def retrieve(
        self,
        project_id: str,
        type: MemoryType | None = None,
        tags: list[str] | None = None,
        keywords: list[str] | None = None,
    ) -> list[MemoryRecord]:
        records = self._store.list(project_id)

        records = [r for r in records if r.status == MemoryStatus.ACTIVE]

        if type is not None:
            records = [r for r in records if r.type == type]

        if tags:
            records = [r for r in records if any(t in r.tags for t in tags)]

        if keywords:
            records = [r for r in records if any(k in r.keywords for k in keywords)]

        records.sort(key=lambda r: (
            -_TRUST_ORDER.get(r.trust_level, 0),
            -r.updated_at.timestamp(),
            r.id,
        ))

        if self._top_k > 0:
            records = records[:self._top_k]
        else:
            records = []

        if self._context_budget > 0:
            total = 0
            filtered = []
            for r in records:
                if total + len(r.content) > self._context_budget:
                    break
                filtered.append(r)
                total += len(r.content)
            records = filtered
        else:
            records = []

        return records