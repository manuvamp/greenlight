"""Before/after table for two Greenlight runs, from their event logs.

    python scripts/compare_runs.py runs/<before>.jsonl runs/<after>.jsonl [--md]

Counts what the neatlogs trace shows per run: LLM calls by role, tokens, Nemotron-priced cost,
tool calls (and how many failed), full test-suite runs, wall time and the final status.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def stats(path: Path) -> dict:
    ev = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    llm = [e for e in ev if e["type"] == "llm"]
    tools = [e for e in ev if e["type"] == "tool"]
    tests = [e for e in ev if e["type"] == "tests" and e.get("label") in ("fix", "after bump", "baseline")]
    result = next((e for e in ev if e["type"] == "result"), {})
    roles = Counter(e["role"] for e in llm)
    return {
        "run": path.stem,
        "status": result.get("status", "?"),
        "llm calls": len(llm),
        "editor calls": roles.get("edit", 0),
        "tokens in": sum(e["tokens_in"] for e in llm),
        "tokens out": sum(e["tokens_out"] for e in llm),
        "cost (USD, Nemotron prices)": round(sum(e["usd"] for e in llm), 4),
        "tool calls": len(tools),
        "failed tool calls": sum(1 for e in tools if str(e.get("result_brief", "")).startswith(("ERROR", "REFUSED", "refused"))),
        "full test runs": len(tests),
        "seconds": result.get("seconds", ev[-1]["t"] if ev else 0),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("before", type=Path)
    p.add_argument("after", type=Path)
    a = p.parse_args()
    b, f = stats(a.before), stats(a.after)
    print("| metric | before | after | change |")
    print("|---|---|---|---|")
    for k in b:
        x, y = b[k], f[k]
        if isinstance(x, (int, float)) and not isinstance(x, bool) and x:
            ch = f"{(y - x) / x * 100:+.0f}%"
        else:
            ch = ""
        print(f"| {k} | {x} | {y} | {ch} |")


if __name__ == "__main__":
    main()
