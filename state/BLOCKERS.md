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

- Phase 3 (Discover) closed 2026-10-16; Phase 4 (Compose) in progress — the open item is the second monolithic baseline (exit criterion)
- `basic-rag-pipeline` is the only remaining Phase 1 capability (DISCOVERED, unblocked since `vector-memory-store` → TESTED 2026-10-09)
- Six `DISCOVERED` capabilities await adoption decisions; review docs exist under `docs/discovery/review/`
