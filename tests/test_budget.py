import json
from datetime import datetime, timedelta, timezone

import pytest

from greenlight.budget import Budget, BudgetExceeded, Caps


def make(tmp_path, **caps):
    return Budget(home=tmp_path, caps=Caps(**{"usd_total": 1.0, "usd_daily": 1.0, "usd_per_run": 1.0, **caps}))


def test_reserve_and_settle_counts_actual_cost(tmp_path):
    b = make(tmp_path)
    r = b.reserve(run="r1", kind="llm", label="x", usd=0.5)
    assert b.totals().usd_total == pytest.approx(0.5)
    r.settle(usd=0.1)
    t = b.totals()
    assert t.usd_total == pytest.approx(0.1)
    assert t.open_reservations == 0


def test_global_cap_refuses_before_spending(tmp_path):
    b = make(tmp_path, usd_total=1.0)
    b.reserve(run="a", kind="llm", label="x", usd=0.6).settle(usd=0.6)
    with pytest.raises(BudgetExceeded, match="global cap"):
        b.reserve(run="b", kind="llm", label="x", usd=0.5)
    # the refused call left no trace in the totals
    assert b.totals().usd_total == pytest.approx(0.6)


def test_per_run_cap(tmp_path):
    b = make(tmp_path, usd_per_run=0.3)
    b.reserve(run="a", kind="llm", label="x", usd=0.2).settle(usd=0.2)
    with pytest.raises(BudgetExceeded, match="per-run cap"):
        b.reserve(run="a", kind="llm", label="x", usd=0.2)
    # a different run is still allowed
    b.reserve(run="b", kind="llm", label="x", usd=0.2)


def test_daily_cap_ignores_older_days(tmp_path):
    b = make(tmp_path, usd_daily=0.5, usd_total=10)
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    with b.ledger.open("a") as f:
        f.write(json.dumps({"type": "reserve", "id": "old", "ts": old, "run": "z", "kind": "llm",
                            "label": "x", "usd": 3.0, "credits": 0}) + "\n")
        f.write(json.dumps({"type": "settle", "id": "old", "ts": old, "usd": 3.0, "credits": 0}) + "\n")
    t = b.totals()
    assert t.usd_total == pytest.approx(3.0)
    assert t.usd_today == pytest.approx(0.0)
    b.reserve(run="n", kind="llm", label="x", usd=0.4)
    with pytest.raises(BudgetExceeded, match="daily cap"):
        b.reserve(run="n2", kind="llm", label="x", usd=0.2)


def test_unsettled_reservation_keeps_counting_at_estimate(tmp_path):
    """A crash between reserve and settle must make the guard stricter, not looser."""
    b = make(tmp_path, usd_total=1.0)
    b.reserve(run="a", kind="llm", label="x", usd=0.9)  # never settled
    b2 = Budget(home=tmp_path, caps=b.caps)  # new process
    assert b2.totals().open_reservations == 1
    with pytest.raises(BudgetExceeded):
        b2.reserve(run="b", kind="llm", label="x", usd=0.2)


def test_tavily_credit_cap(tmp_path):
    b = make(tmp_path, tavily_credits_total=3)
    b.reserve(run="a", kind="tavily", label="search", credits=2).settle(credits=2)
    with pytest.raises(BudgetExceeded, match="Tavily"):
        b.reserve(run="a", kind="tavily", label="search", credits=2)


def test_settle_twice_is_noop(tmp_path):
    b = make(tmp_path)
    r = b.reserve(run="a", kind="llm", label="x", usd=0.2)
    r.settle(usd=0.1)
    r.settle(usd=0.9)
    assert b.totals().usd_total == pytest.approx(0.1)


def test_negative_estimate_rejected(tmp_path):
    b = make(tmp_path)
    with pytest.raises(ValueError):
        b.reserve(run="a", kind="llm", label="x", usd=-1)


def test_torn_write_counts_as_spend_not_zero(tmp_path):
    """A crash can leave garbage at the end of the ledger; it must make the guard stricter."""
    b = make(tmp_path, usd_total=1.0)
    b.reserve(run="a", kind="llm", label="x", usd=0.2).settle(usd=0.2)
    with b.ledger.open("ab") as f:
        f.write(b'{"type": "settle", "id": "tr' + b"\x00" * 64)
    t = b.totals()
    assert t.usd_total == pytest.approx(0.2 + 0.05)
    b.reserve(run="b", kind="llm", label="x", usd=0.1)  # still usable after the crash
    # ...and the new entry is recorded on its own line, not glued to the garbage
    assert b.totals().usd_total == pytest.approx(0.2 + 0.05 + 0.1)


def test_manual_adjustment_counts(tmp_path):
    b = make(tmp_path, usd_total=1.0)
    with b.ledger.open("a") as f:
        f.write(json.dumps({"type": "adjust", "ts": datetime.now(timezone.utc).isoformat(), "usd": 0.9}) + "\n")
    with pytest.raises(BudgetExceeded):
        b.reserve(run="a", kind="llm", label="x", usd=0.2)
