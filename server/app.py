"""Greenlight web API: replays (free, always on), live runs (gated), scoreboard, static UI.

  uvicorn server.app:app --port 8080

Live runs cost real tokens, so they're off unless GREENLIGHT_LIVE=1, need GREENLIGHT_ACCESS_CODE,
run one at a time, are limited per day, and only accept cases from the eval set (or the bundled
example). Replays cost nothing and are what judges see by default.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import tomllib
import uuid
from dataclasses import asdict
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from greenlight.config import load_env

load_env()

from greenlight.agent import UpgradeSpec, Upgrader  # noqa: E402
from greenlight.budget import Budget  # noqa: E402
from greenlight.events import EventLog  # noqa: E402
from greenlight.executor import get_executor  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPLAYS = ROOT / "replays"
RESULTS = ROOT / "evals" / "results"
DATASET = ROOT / "evals" / "dataset.toml"
WEB = ROOT / "web" / "dist"
LIVE_DIR = ROOT / "runs" / "live"

LIVE = os.environ.get("GREENLIGHT_LIVE") == "1"
ACCESS_CODE = os.environ.get("GREENLIGHT_ACCESS_CODE", "")
LIVE_PER_DAY = int(os.environ.get("GREENLIGHT_LIVE_PER_DAY", "10"))
EXECUTOR = os.environ.get("GREENLIGHT_EXECUTOR", "docker")

app = FastAPI(title="Greenlight")

_runs: dict[str, EventLog] = {}
_live_lock = threading.Lock()
_live_count = {"day": date.today().isoformat(), "n": 0}


# ---------------- helpers ----------------

def _read_events(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _replay_meta(path: Path) -> dict:
    events = _read_events(path)
    run = next((e for e in events if e["type"] == "run"), {})
    res = next((e for e in reversed(events) if e["type"] == "result"), {})
    return {
        "id": path.stem, "lib": run.get("lib"), "to_major": run.get("to_major"),
        "source": run.get("source"), "ref": run.get("ref"),
        "status": res.get("status"), "headline": res.get("headline"),
        "from_version": res.get("from_version"), "to_version": res.get("to_version"),
        "usd": res.get("usd"), "seconds": res.get("seconds"), "events": len(events),
    }


def _cases() -> list[dict]:
    return tomllib.loads(DATASET.read_text(encoding="utf-8"))["case"]


def _latest_scoreboard() -> dict | None:
    # The combined official board (latest Nemotron result per repo) wins; otherwise the newest eval-* run.
    # One-off trials and prechecks are never shown.
    official = RESULTS / "eval-official" / "scoreboard.json"
    if official.exists():
        return json.loads(official.read_text(encoding="utf-8"))
    boards = sorted(RESULTS.glob("eval-*/scoreboard.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return json.loads(boards[0].read_text(encoding="utf-8")) if boards else None


# ---------------- API ----------------

@app.get("/api/health")
def health() -> dict:
    t = Budget().totals()
    return {"ok": True, "live": LIVE, "executor": EXECUTOR, "spent_usd": round(t.usd_total, 4),
            "replays": len(list(REPLAYS.glob("*.jsonl")))}


@app.get("/api/replays")
def replays() -> list[dict]:
    return [_replay_meta(p) for p in sorted(REPLAYS.glob("*.jsonl"))]


@app.get("/api/replays/{rid}")
def replay(rid: str) -> JSONResponse:
    path = (REPLAYS / f"{rid}.jsonl").resolve()
    if path.parent != REPLAYS.resolve() or not path.exists():
        raise HTTPException(404, "no such replay")
    return JSONResponse(_read_events(path))


@app.get("/api/scoreboard")
def scoreboard() -> dict:
    return _latest_scoreboard() or {"cases": 0, "rows": []}


@app.get("/api/cases")
def cases() -> list[dict]:
    return [{k: c.get(k) for k in ("id", "repo", "sha", "lib", "to")} for c in _cases()]


class LiveRequest(BaseModel):
    case: str
    code: str


@app.post("/api/runs")
def start_run(req: LiveRequest) -> dict:
    if not LIVE:
        raise HTTPException(403, "live runs are disabled on this deployment; watch a replay instead")
    if not ACCESS_CODE or req.code != ACCESS_CODE:
        raise HTTPException(401, "wrong access code")
    today = date.today().isoformat()
    if _live_count["day"] != today:
        _live_count.update(day=today, n=0)
    if _live_count["n"] >= LIVE_PER_DAY:
        raise HTTPException(429, "daily live-run limit reached; replays are still available")
    if req.case == "example":
        c = {"repo": str(ROOT / "examples" / "pydantic-v1-shop"), "lib": "pydantic", "to": 2}
    else:
        c = next((x for x in _cases() if x["id"] == req.case), None)
        if not c:
            raise HTTPException(404, "unknown case")
    if not _live_lock.acquire(blocking=False):
        raise HTTPException(409, "a live run is already in progress; try again in a few minutes")
    _live_count["n"] += 1
    run_id = f"live-{req.case}-{uuid.uuid4().hex[:6]}"
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    ev = EventLog(run_id, LIVE_DIR / f"{run_id}.jsonl")
    _runs[run_id] = ev

    def work() -> None:
        try:
            spec = UpgradeSpec(source=c["repo"], ref=c.get("sha"), lib=c["lib"], to_major=int(c["to"]),
                               python=c.get("python"), test_args=c.get("test_args", ""),
                               test_env=c.get("test_env", {}), baseline_pins=c.get("baseline_pins", []),
                               extra_deps=c.get("extra_deps", []), max_minutes=12)
            ex = get_executor(EXECUTOR)
            Upgrader(spec, ex, events=ev, run_id=run_id).run()
            ex.cleanup()
        except Exception as e:  # noqa: BLE001
            ev.emit("result", status="error", headline=f"{type(e).__name__}: {e}")
        finally:
            _live_lock.release()

    threading.Thread(target=work, daemon=True).start()
    return {"run_id": run_id}


@app.get("/api/runs/{run_id}/stream")
async def stream(run_id: str) -> StreamingResponse:
    ev = _runs.get(run_id)
    if not ev:
        raise HTTPException(404, "no such live run")

    async def gen():
        i = 0
        last_beat = time.monotonic()
        while True:
            while i < len(ev.events):
                e = ev.events[i]
                i += 1
                yield f"data: {json.dumps(e, default=str)}\n\n"
                if e["type"] == "result":
                    return
            if time.monotonic() - last_beat > 15:
                yield ": keep-alive\n\n"
                last_beat = time.monotonic()
            await asyncio.sleep(0.3)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------- static UI ----------------

if WEB.exists():
    app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str) -> FileResponse:
        f = (WEB / path).resolve()
        if path and f.is_file() and WEB.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(WEB / "index.html")
