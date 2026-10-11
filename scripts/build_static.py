"""Pre-render the read-only API into web/dist for the static demo (GitHub Pages).

  cd web && VITE_STATIC=1 npx vite build --base /greenlight/ && cd ..
  python scripts/build_static.py

Writes the same JSON the FastAPI server returns (server/app.py) for health, replays, the official
scoreboard and the eval cases, plus a 404.html copy of index.html so deep links like
/greenlight/replay/<id> load the app. Stdlib only, so CI needs no project install.
"""

from __future__ import annotations

import json
import shutil
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "web" / "dist"
REPLAYS = ROOT / "replays"
BOARD = ROOT / "evals" / "results" / "eval-official" / "scoreboard.json"
DATASET = ROOT / "evals" / "dataset.toml"


def _events(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _meta(path: Path, events: list[dict]) -> dict:
    run = next((e for e in events if e["type"] == "run"), {})
    res = next((e for e in reversed(events) if e["type"] == "result"), {})
    return {
        "id": path.stem, "lib": run.get("lib"), "to_major": run.get("to_major"),
        "source": run.get("source"), "ref": run.get("ref"),
        "status": res.get("status"), "headline": res.get("headline"),
        "from_version": res.get("from_version"), "to_version": res.get("to_version"),
        "usd": res.get("usd"), "seconds": res.get("seconds"), "events": len(events),
    }


def _write(rel: str, data: object) -> None:
    out = DIST / "api" / f"{rel}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    if not (DIST / "index.html").exists():
        print("web/dist is missing: build the web app first", file=sys.stderr)
        return 2
    metas = []
    for path in sorted(REPLAYS.glob("*.jsonl")):
        events = _events(path)
        metas.append(_meta(path, events))
        _write(f"replays/{path.stem}", events)
    _write("replays", metas)
    _write("scoreboard", json.loads(BOARD.read_text(encoding="utf-8")) if BOARD.exists() else {"cases": 0, "rows": []})
    cases = tomllib.loads(DATASET.read_text(encoding="utf-8"))["case"]
    _write("cases", [{k: c.get(k) for k in ("id", "repo", "sha", "lib", "to")} for c in cases])
    _write("health", {"ok": True, "live": False, "executor": "docker", "spent_usd": 0, "replays": len(metas)})
    shutil.copyfile(DIST / "index.html", DIST / "404.html")
    (DIST / ".nojekyll").touch()
    print(f"static API written: {len(metas)} replays")
    return 0


if __name__ == "__main__":
    sys.exit(main())
