"""greenlight upgrade <repo-or-folder> <lib>@<major>   ·   greenlight budget"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import tracing
from .config import load_env


def _upgrade(a: argparse.Namespace) -> int:
    from .agent import UpgradeSpec, Upgrader
    from .events import EventLog, console_printer
    from .executor import get_executor

    lib, _, major = a.target.partition("@")
    if not major.isdigit():
        print("target must look like pydantic@2", file=sys.stderr)
        return 2
    spec = UpgradeSpec(source=a.source, lib=lib, to_major=int(major), ref=a.ref, python=a.python,
                       test_cmd=a.test_cmd, test_policy=a.test_policy,
                       max_iterations=a.max_iterations, max_minutes=a.max_minutes,
                       model_override=a.model, use_research=not a.no_research, editor=a.editor,
                       bulk=not a.no_bulk)
    runs = Path(a.runs_dir)
    ex = get_executor(a.executor)
    tracing.init(tags=["greenlight", f"{lib}@{major}", *a.tag])
    up = Upgrader(spec, ex, runs_dir=runs)
    if not a.quiet:
        up.ev.subscribe(console_printer)
    res = up.run()
    ex.cleanup()
    out = runs / f"{res.run_id}.result.json"
    out.write_text(json.dumps(asdict(res), indent=2, default=str), encoding="utf-8")
    print(f"\n{res.status.upper()}: {res.headline}")
    print(f"cost ${res.usd:.4f} · {res.seconds:.0f}s · {res.iterations} iteration(s) · events {runs / (res.run_id + '.jsonl')}")
    if tracing.enabled():
        tracing.flush()
        print(f"neatlogs trace {tracing.last_trace_id}")
    if a.show_diff and res.diff:
        print("\n" + res.diff)
    return 0 if res.status in ("green", "noop") else 1


def _budget(a: argparse.Namespace) -> int:
    from .budget import Budget
    b = Budget()
    t = b.totals()
    c = b.caps
    print(f"Token Factory: ${t.usd_total:.4f} of ${c.usd_total:.2f} cap  (today ${t.usd_today:.4f} of ${c.usd_daily:.2f})")
    print(f"Tavily:        {t.tavily_credits} of {c.tavily_credits_total} credits")
    print(f"open reservations: {t.open_reservations} · ledger: {b.ledger}")
    if a.runs:
        for run, usd in sorted(t.usd_by_run.items(), key=lambda kv: -kv[1])[:20]:
            print(f"  {usd:9.4f}  {run}")
    return 0


def main(argv: list[str] | None = None) -> int:
    load_env()
    p = argparse.ArgumentParser(prog="greenlight")
    sub = p.add_subparsers(dest="cmd", required=True)

    u = sub.add_parser("upgrade", help="upgrade a dependency across a major version and fix the code")
    u.add_argument("source", help="git URL or local folder")
    u.add_argument("target", help="lib@major, e.g. pydantic@2")
    u.add_argument("--ref", help="commit, branch or tag to start from")
    u.add_argument("--python", help="force a Python version, e.g. 3.10")
    u.add_argument("--test-cmd", help="custom test command (must write junit xml to /tmp/greenlight-junit.xml)")
    u.add_argument("--test-policy", default="audited", choices=["audited", "frozen", "free"],
                   help="audited: tests may be migrated to the new API but never weakened (default)")
    u.add_argument("--max-iterations", type=int, default=6)
    u.add_argument("--max-minutes", type=float, default=20)
    u.add_argument("--model", help="force one model for every role (ablation)")
    u.add_argument("--no-research", action="store_true", help="skip Tavily rule sheet (ablation)")
    u.add_argument("--no-bulk", action="store_true", help="skip the one-pass parallel file migration (ablation)")
    u.add_argument("--editor", default="super-first", choices=["super-first", "cascade", "lightning", "super", "ultra"],
                   help="which model edits code; super-first = Super, then Ultra if it stalls; "
                        "cascade = Lightning → Super → Ultra")
    u.add_argument("--executor", default="docker", choices=["docker", "contree"])
    u.add_argument("--runs-dir", default="runs")
    u.add_argument("--show-diff", action="store_true")
    u.add_argument("--quiet", action="store_true")
    u.add_argument("--tag", action="append", default=[], help="extra neatlogs trace tag (repeatable)")
    u.set_defaults(fn=_upgrade)

    b = sub.add_parser("budget", help="show spend against the caps")
    b.add_argument("--runs", action="store_true")
    b.set_defaults(fn=_budget)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
