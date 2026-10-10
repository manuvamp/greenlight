"""Day-1 check of every Nemotron model on Token Factory.

Checks: plain answer with thinking off/on, tool calling (Super, Lightning, Nano), JSON mode.
Prints one line per call with tokens, cost and latency. Every call goes through the budget guard.
"""

from __future__ import annotations

import json
import sys

from greenlight.config import load_env

load_env()

from greenlight.llm import LLM, LLMError  # noqa: E402
from greenlight.models import LIGHTNING, NANO, SUPER, ULTRA, Role  # noqa: E402

RUN = "smoke-models"
results: list[dict] = []

TOOL = [{
    "type": "function",
    "function": {
        "name": "apply_patch",
        "description": "Replace an exact snippet in a file.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "search": {"type": "string"},
                "replace": {"type": "string"},
            },
            "required": ["path", "search", "replace"],
        },
    },
}]

CODE = "from pydantic import BaseModel, validator\n\nclass User(BaseModel):\n    name: str\n\n    @validator('name')\n    def strip(cls, v):\n        return v.strip()\n"


def show(tag: str, fn):
    try:
        r = fn()
        rec = r.record
        out = (r.content or json.dumps(r.tool_calls)[:160]).replace("\n", " ")[:120]
        print(f"OK   {tag:38s} in={rec.tokens_in:5d} out={rec.tokens_out:5d} ${rec.usd:.5f} "
              f"{rec.latency_s:5.1f}s fin={r.finish_reason:10s} reasoning={len(r.reasoning):5d}ch | {out}")
        results.append({"tag": tag, "ok": True, **rec.__dict__, "content": r.content[:400],
                        "tool_calls": r.tool_calls, "reasoning_chars": len(r.reasoning)})
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {tag:38s} {type(e).__name__}: {str(e)[:200]}")
        results.append({"tag": tag, "ok": False, "error": f"{type(e).__name__}: {e}"})


def main() -> int:
    llm = LLM()
    q = [{"role": "user", "content": "In one short sentence: what replaced pydantic v1's @validator in v2?"}]

    for model in (ULTRA, SUPER, LIGHTNING, NANO):
        llm.model_override = model.id
        show(f"{model.label} think=off", lambda: llm.chat(Role.WRITE, q, run=RUN, max_tokens=120, thinking=False))
    for model in (ULTRA, SUPER, LIGHTNING):
        llm.model_override = model.id
        show(f"{model.label} think=on (1200)", lambda: llm.chat(Role.PLAN, q, run=RUN, max_tokens=1200, thinking=True))

    edit = [
        {"role": "system", "content": "You migrate Python code from pydantic v1 to v2. Use the apply_patch tool. Make one patch."},
        {"role": "user", "content": f"File app/models.py:\n```python\n{CODE}```\nMigrate the validator to pydantic v2."},
    ]
    for model in (SUPER, LIGHTNING, NANO):
        llm.model_override = model.id
        show(f"{model.label} tools", lambda: llm.chat(Role.EDIT, edit, run=RUN, tools=TOOL, max_tokens=600, thinking=False))

    js = [{"role": "user", "content": 'Return JSON {"old": string, "new": string} for the v1->v2 rename of .dict() in pydantic.'}]
    for model in (SUPER, LIGHTNING):
        llm.model_override = model.id
        show(f"{model.label} json", lambda: llm.chat(Role.DIGEST, js, run=RUN, max_tokens=200, thinking=False, json_mode=True))

    t = llm.budget.totals()
    print(f"\nrun spend ${t.usd_by_run.get(RUN, 0):.5f} | ledger total ${t.usd_total:.5f} | open reservations {t.open_reservations}")
    with open("scripts/smoke_models.out.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
