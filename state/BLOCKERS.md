# BLOCKERS — Active Blockers & Dependencies

> Things that prevent work from proceeding. Update in real-time.

---

## Active Blockers

| ID | Blocker | Blocks | Depends On | Status |
|---|---|---|---|---|
| — | — | — | — | — |

_(No active blockers.)_

---

## Dependency Graph

```text
tool-registry ──┬──→ react-agent-loop ──→ agent_loop_end_to_end (integration)
                │
model-provider ─┘

vector-memory-store ──→ basic-rag-pipeline

mcp-client ──→ (standalone, depends on tool-registry)

execution-trace-recorder ──→ (standalone)
```

---

## Notes

- `vector-memory-store` and `basic-rag-pipeline` are the only remaining Phase 1 capabilities (both DISCOVERED)
- Phase 3 (Discover) is not blocked — it can start when ready
- The uncommitted infrastructure scanner work is not blocked, just incomplete
