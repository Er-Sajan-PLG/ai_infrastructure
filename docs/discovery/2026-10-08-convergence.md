result = discover(Path('.')); \
print(render_discovery(result))"
# Discovery — Cross-Repo Pattern Convergence

Generated from 25 studied repositories.

> **This document is a proposal, not a taxonomy change.**
> Adopting a category requires an ADR and a session decision
> (ADR-0021 Decision 2, charter §4).

## Convergent patterns (≥3 repositories)

These categories were proposed by 3 or more independent
repositories. The convergence is the evidence.

| Proposed id | Count | % of repos | From patterns | Repos |
|---|---|---|---|---|
| `config` | 15 | 60% | `config` | `OpenHands`, `SWE-agent`, `agno`, `ai`, `autogen`, … (10 more) |
| `caching` | 14 | 56% | `caching` | `agno`, `autogen`, `crewAI`, `dspy`, `haystack`, … (9 more) |
| `guardrails` | 10 | 40% | `guardrails` | `agno`, `ai`, `haystack`, `langfuse`, `litellm`, … (5 more) |
| `rate-limiting` | 6 | 24% | `rate-limiting` | `SWE-agent`, `dspy`, `haystack`, `langchain`, `langfuse`, … (1 more) |

## Confirmed categories

These existing taxonomy categories were confirmed by studies
mapping to them. This is evidence that the taxonomy covers
ground real projects also found worth building.

- `agents`
- `evaluation`
- `mcp`
- `memory`
- `models`
- `observability`
- `retrieval`
- `tools`

## Repositories studied

25 repositories were analysed:

- `OpenHands`
- `SWE-agent`
- `agno`
- `ai`
- `autogen`
- `crewAI`
- `dspy`
- `haystack`
- `haystack-experimental`
- `langchain`
- `langfuse`
- `langgraph`
- `letta`
- `litellm`
- `llama_index`
- `mastra`
- `openai-python`
- `phidata`
- `phoenix`
- `pydantic-ai`
- `python-sdk`
- `ragas`
- `semantic-kernel`
- `swarm`
- `trulens`

