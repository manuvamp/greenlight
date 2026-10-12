"""Run Greenlight over the eval set and write a scoreboard.

  python evals/run.py --precheck                 # baseline + bump only, no model calls ($0)
  python evals/run.py --cases engorgio,nsopy      # full runs for some cases
  python evals/run.py --tag routed                # full run of every prechecked case

Results: evals/results/<tag>/<case>.json, events/<run>.jsonl, summary.md, scoreboard.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from greenlight.config import load_env  # noqa: E402

load_env()

from greenlight import tracing  # noqa: E402
from greenlight.agent import UpgradeSpec, Upgrader  # noqa: E402
from greenlight.executor import get_executor  # noqa: E402

DATASET = ROOT / "evals" / "dataset.toml"
RESULTS = ROOT / "evals" / "results"


def load_cases(only: set[str] | None, lib: str | None) -> list[dict]:
    cases = tomllib.loads(DATASET.read_text(encoding="utf-8"))["case"]
    if only:
        cases = [c for c in cases if c["id"] in only]
    if lib:
        cases = [c for c in cases if c["lib"] == lib]
    return cases


def spec_for(c: dict, a: argparse.Namespace) -> UpgradeSpec:
    return UpgradeSpec(
        source=c["repo"], ref=c.get("sha"), lib=c["lib"], to_major=int(c["to"]),
        python=c.get("python"), test_args=c.get("test_args", ""), test_env=c.get("test_env", {}),
        baseline_pins=c.get("baseline_pins", []), extra_deps=c.get("extra_deps", []),
        precheck=a.precheck, editor=a.editor, model_override=a.model, use_research=not a.no_research,
        max_minutes=a.max_minutes, max_iterations=a.max_iterations,
    )


def run_case(c: dict, a: argparse.Namespace, out: Path) -> dict:
    ex = get_executor("docker")
    up = Upgrader(spec_for(c, a), ex, run_id=f"{c['id']}-{int(time.time())}", runs_dir=out / "events")
    res = up.run()
    ex.cleanup()
    d = asdict(res)
    d["neatlogs_trace"] = getattr(up, "trace_id", "")
    d["case"] = c["id"]
    d["lib"] = c["lib"]
    (out / f"{c['id']}.json").write_text(json.dumps(d, indent=2, default=str), encoding="utf-8")
    return d


def summarize(rows: list[dict], out: Path, a: argparse.Namespace) -> None:
    rows = sorted(rows, key=lambda r: r["case"])
    lines = [f"# Greenlight eval: {out.name}", "",
             f"editor={a.editor} model={a.model or 'routed'} research={'off' if a.no_research else 'on'} "
             f"precheck={a.precheck}", "",
             "| case | lib | status | baseline | final | iters | esc | $ | s | headline |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        b, f = r.get("baseline") or {}, r.get("final") or {}
        lines.append(f"| {r['case']} | {r['lib']} | {r['status']} | {b.get('passed', '')}/{b.get('total', '')} "
                     f"| {f.get('passed', '')}/{f.get('total', '')} | {r['iterations']} | {r['escalations']} "
                     f"| {r['usd']:.3f} | {r['seconds']:.0f} | {r['headline'][:90]} |")
    full = [] if a.precheck else rows
    if a.precheck:
        ok = [r["case"] for r in rows if r["status"] == "precheck-ok"]
        lines += ["", f"**{len(ok)}/{len(rows)} cases usable** (green baseline, red after the bump): {', '.join(ok)}"]
    if full:
        green = [r for r in full if r["status"] == "green"]
        scored = [r for r in full if r["status"] in ("green", "partial", "failed")]
        board = {
            "tag": out.name, "cases": len(full), "green": len(green),
            "partial": sum(r["status"] == "partial" for r in full),
            "failed": sum(r["status"] == "failed" for r in full),
            "errors": sum(r["status"] == "error" for r in full),
            "green_rate": round(len(green) / max(len(scored), 1), 3),
            "median_usd_green": round(statistics.median([r["usd"] for r in green]), 4) if green else None,
            "median_seconds_green": round(statistics.median([r["seconds"] for r in green]), 1) if green else None,
            "total_usd": round(sum(r["usd"] for r in full), 4),
            "by_role_usd": _by_role(full),
            "rows": [{k: r.get(k) for k in ("case", "lib", "status", "headline", "usd", "seconds", "iterations",
                                            "escalations", "from_version", "to_version", "baseline", "final")}
                     for r in rows],
        }
        (out / "scoreboard.json").write_text(json.dumps(board, indent=2), encoding="utf-8")
        lines += ["", f"**green {board['green']}/{len(scored)}** (rate {board['green_rate']:.0%}) · "
                      f"median ${board['median_usd_green']} · median {board['median_seconds_green']}s · "
                      f"total ${board['total_usd']}"]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def _by_role(rows: list[dict]) -> dict:
    agg: dict[str, float] = {}
    for r in rows:
        for c in r.get("calls", []):
            key = f"{c['role']}:{c['model_label']}"
            agg[key] = round(agg.get(key, 0.0) + c["usd"], 5)
    return agg


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser()
    p.add_argument("--cases", help="comma-separated case ids")
    p.add_argument("--lib")
    p.add_argument("--precheck", action="store_true")
    p.add_argument("--editor", default="super-first")
    p.add_argument("--model")
    p.add_argument("--no-research", action="store_true")
    p.add_argument("--max-minutes", type=float, default=15)
    p.add_argument("--max-iterations", type=int, default=5)
    p.add_argument("--parallel", type=int, default=2)
    p.add_argument("--tag")
    a = p.parse_args()

    cases = load_cases(set(a.cases.split(",")) if a.cases else None, a.lib)
    tag = a.tag or (("precheck-" if a.precheck else "run-") + time.strftime("%Y%m%d-%H%M%S"))
    out = RESULTS / tag
    (out / "events").mkdir(parents=True, exist_ok=True)
    print(f"{len(cases)} cases → {out}", flush=True)
    tracing.init(tags=["greenlight", "eval", tag])
    rows = []
    with ThreadPoolExecutor(max_workers=a.parallel) as pool:
        futs = {pool.submit(run_case, c, a, out): c for c in cases}
        for f in as_completed(futs):
            c = futs[f]
            try:
                r = f.result()
            except Exception as e:  # noqa: BLE001
                r = {"case": c["id"], "lib": c["lib"], "status": "error", "headline": f"{type(e).__name__}: {e}",
                     "usd": 0.0, "seconds": 0.0, "iterations": 0, "escalations": 0}
            rows.append(r)
            print(f"[{len(rows)}/{len(cases)}] {r['case']:28s} {r['status']:14s} ${r['usd']:.3f} "
                  f"{r['seconds']:.0f}s  {r['headline'][:100]}", flush=True)
    summarize(rows, out, a)
    tracing.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
