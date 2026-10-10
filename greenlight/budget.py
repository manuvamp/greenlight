"""Hard spending caps for Token Factory and Tavily.

Token Factory is postpaid: once free credit runs out the balance goes negative and the card
on file is charged. Nebius has no spending limit, so this module is the limit.

Every paid call goes through `Budget.reserve()` *before* it is sent, with a worst-case estimate.
If the estimate would cross any cap (global, daily, per run) the call is refused with
`BudgetExceeded`. After the call, `Reservation.settle()` records the real cost.

The ledger is an append-only JSONL file shared by every process on the machine, guarded by a
lock file. A reservation that is never settled (crash) keeps counting at its estimate, so a crash
can only make the guard stricter, never looser.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


class BudgetExceeded(RuntimeError):
    pass


UNREADABLE_USD = 0.05  # assumed cost of each ledger line that can't be parsed


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


@dataclass
class Caps:
    usd_total: float = 20.0      # account balance is $30.50; keep $10 headroom
    usd_daily: float = 5.0
    usd_per_run: float = 0.75
    tavily_credits_total: int = 7000  # 9,000 available

    @classmethod
    def from_env(cls) -> "Caps":
        return cls(
            usd_total=_env_float("GREENLIGHT_BUDGET_USD", cls.usd_total),
            usd_daily=_env_float("GREENLIGHT_BUDGET_DAILY_USD", cls.usd_daily),
            usd_per_run=_env_float("GREENLIGHT_BUDGET_RUN_USD", cls.usd_per_run),
            tavily_credits_total=int(_env_float("GREENLIGHT_TAVILY_CREDITS", cls.tavily_credits_total)),
        )


@dataclass
class Totals:
    usd_total: float = 0.0
    usd_today: float = 0.0
    usd_by_run: dict[str, float] = field(default_factory=dict)
    tavily_credits: int = 0
    open_reservations: int = 0


def default_home() -> Path:
    return Path(os.environ.get("GREENLIGHT_HOME", Path.home() / ".greenlight"))


class Budget:
    def __init__(self, home: Path | None = None, caps: Caps | None = None):
        self.home = Path(home) if home else default_home()
        self.home.mkdir(parents=True, exist_ok=True)
        self.ledger = self.home / "ledger.jsonl"
        self.lockfile = self.home / "ledger.lock"
        self.caps = caps or Caps.from_env()

    # ---------- locking ----------

    @contextmanager
    def _lock(self, timeout: float = 30.0, stale_after: float = 60.0):
        deadline = time.monotonic() + timeout
        while True:
            try:
                fd = os.open(self.lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                break
            except FileExistsError:
                try:
                    if time.time() - self.lockfile.stat().st_mtime > stale_after:
                        self.lockfile.unlink(missing_ok=True)
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() > deadline:
                    raise TimeoutError(f"budget ledger is locked: {self.lockfile}")
                time.sleep(0.05)
        try:
            yield
        finally:
            self.lockfile.unlink(missing_ok=True)

    # ---------- ledger ----------

    def _append(self, entry: dict) -> None:
        prefix = ""
        if self.ledger.exists() and self.ledger.stat().st_size:
            with self.ledger.open("rb") as f:
                f.seek(-1, os.SEEK_END)
                if f.read(1) != b"\n":  # a torn last line must not swallow this entry
                    prefix = "\n"
        with self.ledger.open("a", encoding="utf-8") as f:
            f.write(prefix + json.dumps(entry) + "\n")
            f.flush()
            os.fsync(f.fileno())  # a power cut must not lose spend records

    def _entries(self) -> list[dict]:
        """Ledger entries. A line that can't be read (e.g. a torn write after a crash) becomes a
        conservative 'unreadable' charge instead of being ignored."""
        if not self.ledger.exists():
            return []
        out = []
        raw = self.ledger.read_bytes().decode("utf-8", errors="replace")
        for line in raw.splitlines():
            line = line.strip().strip("\x00")
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                out.append({"type": "unreadable"})
        return out

    def totals(self) -> Totals:
        """Spend so far. Open reservations count at their estimate."""
        today = datetime.now(timezone.utc).date().isoformat()
        reserved: dict[str, dict] = {}
        settled: dict[str, dict] = {}
        t = Totals()
        for e in self._entries():
            if e["type"] == "reserve":
                reserved[e["id"]] = e
            elif e["type"] == "settle":
                settled[e["id"]] = e
            elif e["type"] == "unreadable":
                t.usd_total += UNREADABLE_USD
            elif e["type"] == "adjust":  # manual correction, e.g. after reconciling with the billing page
                t.usd_total += e.get("usd", 0.0)
                if e.get("ts", "")[:10] == today:
                    t.usd_today += e.get("usd", 0.0)
                t.tavily_credits += e.get("credits", 0)
        for rid, r in reserved.items():
            s = settled.get(rid)
            usd = s["usd"] if s else r["usd"]
            credits = s.get("credits", 0) if s else r.get("credits", 0)
            if not s:
                t.open_reservations += 1
            t.usd_total += usd
            if r["ts"][:10] == today:
                t.usd_today += usd
            t.usd_by_run[r["run"]] = t.usd_by_run.get(r["run"], 0.0) + usd
            t.tavily_credits += credits
        return t

    # ---------- reserve / settle ----------

    def reserve(self, *, run: str, kind: str, label: str, usd: float = 0.0, credits: int = 0) -> "Reservation":
        """Claim a worst-case amount before a paid call. Raises BudgetExceeded instead of overspending."""
        if usd < 0 or credits < 0:
            raise ValueError("estimates must be non-negative")
        with self._lock():
            t = self.totals()
            c = self.caps
            run_spent = t.usd_by_run.get(run, 0.0)
            if t.usd_total + usd > c.usd_total:
                raise BudgetExceeded(
                    f"global cap ${c.usd_total:.2f} reached (spent ${t.usd_total:.4f}, this call up to ${usd:.4f})"
                )
            if t.usd_today + usd > c.usd_daily:
                raise BudgetExceeded(
                    f"daily cap ${c.usd_daily:.2f} reached (today ${t.usd_today:.4f}, this call up to ${usd:.4f})"
                )
            if run_spent + usd > c.usd_per_run:
                raise BudgetExceeded(
                    f"per-run cap ${c.usd_per_run:.2f} reached (run ${run_spent:.4f}, this call up to ${usd:.4f})"
                )
            if t.tavily_credits + credits > c.tavily_credits_total:
                raise BudgetExceeded(
                    f"Tavily cap {c.tavily_credits_total} credits reached (used {t.tavily_credits})"
                )
            rid = uuid.uuid4().hex
            self._append({
                "type": "reserve", "id": rid, "ts": datetime.now(timezone.utc).isoformat(),
                "run": run, "kind": kind, "label": label, "usd": usd, "credits": credits,
            })
        return Reservation(self, rid)

    def _settle(self, rid: str, usd: float, credits: int, meta: dict) -> None:
        with self._lock():
            self._append({
                "type": "settle", "id": rid, "ts": datetime.now(timezone.utc).isoformat(),
                "usd": usd, "credits": credits, **meta,
            })


class Reservation:
    def __init__(self, budget: Budget, rid: str):
        self.budget = budget
        self.id = rid
        self.done = False

    def settle(self, *, usd: float = 0.0, credits: int = 0, **meta) -> None:
        """Record what the call really cost. Call with zeros if the request failed before billing."""
        if self.done:
            return
        self.budget._settle(self.id, usd, credits, meta)
        self.done = True
