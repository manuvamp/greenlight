"""Everything a run does is an event: the web UI streams them live, and replays are just the saved file."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Callable


class EventLog:
    def __init__(self, run_id: str, path: Path | None = None):
        self.run_id = run_id
        self.path = path
        self.events: list[dict] = []
        self.listeners: list[Callable[[dict], None]] = []
        self._lock = threading.Lock()
        self.t0 = time.time()
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")

    def subscribe(self, fn: Callable[[dict], None]) -> None:
        self.listeners.append(fn)

    def emit(self, type: str, **data: Any) -> dict:
        ev = {"seq": len(self.events), "t": round(time.time() - self.t0, 3), "type": type, **data}
        with self._lock:
            ev["seq"] = len(self.events)
            self.events.append(ev)
            if self.path:
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(ev, default=str) + "\n")
        for fn in self.listeners:
            try:
                fn(ev)
            except Exception:
                pass
        return ev

    # shorthands
    def stage(self, name: str, status: str = "start", **data: Any) -> dict:
        return self.emit("stage", name=name, status=status, **data)

    def log(self, msg: str, level: str = "info") -> dict:
        return self.emit("log", msg=msg, level=level)


def console_printer(ev: dict) -> None:
    """Compact terminal view of a run, used by the CLI."""
    t = ev["type"]
    ts = f"{ev['t']:7.1f}s"
    if t == "stage":
        mark = {"start": "▶", "done": "✓", "fail": "✗"}.get(ev["status"], "·")
        extra = f" {ev['detail']}" if ev.get("detail") else ""
        print(f"{ts} {mark} {ev['name']}{extra}", flush=True)
    elif t == "log":
        print(f"{ts}   {ev['msg']}", flush=True)
    elif t == "tests":
        print(f"{ts}   tests [{ev['label']}]: {ev['summary']}", flush=True)
    elif t == "llm":
        via = f" via {ev['served_by']}" if ev.get("backend") == "standin" else ""
        cost = f"~${ev['usd']:.4f} est" if via else f"${ev['usd']:.4f}"
        print(f"{ts}   ⚙ {ev['role']:9s} {ev['model_label']:24s}{via} {ev['tokens_in']:6d}→{ev['tokens_out']:5d} tok "
              f"{cost} {ev['latency_s']:.1f}s{' think' if ev['thinking'] else ''}", flush=True)
    elif t == "tool":
        print(f"{ts}   🔧 {ev['name']}({ev.get('brief', '')}) → {ev.get('result_brief', '')}", flush=True)
    elif t == "source":
        print(f"{ts}   🔎 {ev['title'][:70]} — {ev['url']}", flush=True)
    elif t == "patch":
        print(f"{ts}   ✎ {ev['path']} (+{ev.get('added', 0)}/-{ev.get('removed', 0)})", flush=True)
    elif t == "result":
        print(f"{ts} ■ {ev['status'].upper()}: {ev.get('headline', '')}", flush=True)
