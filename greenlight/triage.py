"""Turn a red test run into a few grouped root causes, small enough for a prompt."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .workspace import TestRun

MAX_GROUPS = 12


@dataclass
class FailureGroup:
    signature: str
    tests: list[str] = field(default_factory=list)
    sample: str = ""  # trimmed traceback of the first test in the group


def _signature(detail: str) -> str:
    lines = [ln.strip() for ln in detail.splitlines() if ln.strip()]
    e_lines = [ln[1:].strip() for ln in lines if ln.startswith("E ")]
    sig = e_lines[0] if e_lines else (lines[0] if lines else "unknown failure")
    sig = re.sub(r"0x[0-9a-f]+", "0x…", sig)
    sig = re.sub(r"\d+(\.\d+)?", "N", sig)
    sig = re.sub(r"'[^']{25,}'", "'…'", sig)
    return sig[:220]


def _trim_trace(detail: str, limit: int = 1800) -> str:
    """Keep the frames in repo code plus the error lines; drop site-packages noise."""
    keep = []
    for ln in detail.splitlines():
        s = ln.strip()
        if not s:
            continue
        if "site-packages" in s or "/opt/uv-python" in s:
            continue
        keep.append(ln.rstrip())
    text = "\n".join(keep)
    return text if len(text) <= limit else text[: limit // 3] + "\n…\n" + text[-(2 * limit) // 3:]


def group_failures(run: TestRun) -> list[FailureGroup]:
    groups: dict[str, FailureGroup] = {}
    if run.collection_error and not run.failures:
        g = FailureGroup(_signature(run.collection_error), ["<collection>"], _trim_trace(run.collection_error, 3000))
        return [g]
    for tid in sorted(run.failed):
        detail = run.failures.get(tid, "")
        sig = _signature(detail)
        g = groups.setdefault(sig, FailureGroup(sig, [], _trim_trace(detail)))
        g.tests.append(tid)
    ranked = sorted(groups.values(), key=lambda g: -len(g.tests))
    return ranked[:MAX_GROUPS]


def render(groups: list[FailureGroup], run: TestRun, limit_chars: int = 9000) -> str:
    out = [f"Test run: {run.summary()}"]
    if run.collection_error and run.failures:
        out.append("Collection errors present:\n" + _trim_trace(run.collection_error, 1500))
    for i, g in enumerate(groups, 1):
        names = ", ".join(t.split("::")[-1] for t in g.tests[:6]) + (" …" if len(g.tests) > 6 else "")
        out.append(f"\n## Group {i}: {len(g.tests)} test(s) — {g.signature}\nTests: {names}\n{g.sample}")
    text = "\n".join(out)
    return text if len(text) <= limit_chars else text[:limit_chars] + "\n… (truncated)"
