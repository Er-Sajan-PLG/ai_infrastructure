"""Consumer prototype: use 5 capabilities from an installed package.

Run after `pip install ai_infrastructure-*.whl`. No sys.path manipulation,
no imports from catalog/ internals.
"""

from __future__ import annotations

import ai_infrastructure
from execution_trace_recorder import TraceRecorder
from model_provider.providers import OpenAIProvider
from rate_limiting import TokenBucket, retry
from react_agent_loop import run
from tool_registry import ToolRegistry


def main() -> None:
    print(f"ai_infrastructure {ai_infrastructure.__version__}")
    print("tool_registry:", ToolRegistry)
    print("model_provider:", OpenAIProvider)
    print("react_agent_loop:", run)
    print("rate_limiting:", TokenBucket, retry)
    print("execution_trace_recorder:", TraceRecorder)
    print("OK — 5 capabilities consumed from installed package")


if __name__ == "__main__":
    main()
