"""Build the official scoreboard: the most recent Nemotron result for every repo.

  python evals/combine.py eval-nemotron eval-nemotron-2 --out eval-official

Later passes override earlier ones per repo (they ran on newer harness code). Each row records
which pass it came from, so nothing is hidden.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("passes", nargs="+", help="result dirs, oldest first")
    p.add_argument("--out", default="eval-official")
    a = p.parse_args()
    rows: dict[str, dict] = {}
    for tag in a.passes:
        board = json.loads((RESULTS / tag / "scoreboard.json").read_text(encoding="utf-8"))
        for r in board["rows"]:
            rows[r["case"]] = {**r, "pass": tag}
    full = list(rows.values())
    green = [r for r in full if r["status"] == "green"]
    scored = [r for r in full if r["status"] in ("green", "partial", "failed")]
    out = {
        "tag": a.out,
        "note": "Most recent NVIDIA Nemotron result per repo across passes " + ", ".join(a.passes)
                + " (later passes ran on improved harness code).",
        "passes": a.passes,
        "cases": len(full), "green": len(green),
        "partial": sum(r["status"] == "partial" for r in full),
        "failed": sum(r["status"] == "failed" for r in full),
        "errors": sum(r["status"] == "error" for r in full),
        "green_rate": round(len(green) / max(len(scored), 1), 3),
        "median_usd_green": round(statistics.median([r["usd"] for r in green]), 4) if green else None,
        "median_seconds_green": round(statistics.median([r["seconds"] for r in green]), 1) if green else None,
        "total_usd": round(sum(json.loads((RESULTS / t / "scoreboard.json").read_text())["total_usd"]
                               for t in a.passes), 4),
        "rows": sorted(full, key=lambda r: (r["status"] != "green", r["case"])),
    }
    d = RESULTS / a.out
    d.mkdir(parents=True, exist_ok=True)
    (d / "scoreboard.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("cases", "green", "partial", "failed", "errors", "green_rate",
                                         "median_usd_green", "median_seconds_green", "total_usd")}))
    for r in out["rows"]:
        print(f"  {r['case']:22s} {r['status']:8s} {r['final'].get('passed', '')}/{r['baseline'].get('passed', '')} "
              f"${r['usd']:.3f} {r['seconds']:.0f}s  [{r['pass']}]")


if __name__ == "__main__":
    main()
