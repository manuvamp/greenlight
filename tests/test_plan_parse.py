from greenlight.agent import _parse_plan


def test_whole_plan():
    assert _parse_plan('{"diagnosis": "x", "steps": [{"file": "a.py"}]}')["steps"] == [{"file": "a.py"}]


def test_fenced_plan():
    assert _parse_plan('```json\n{"steps": [{"file": "a.py"}]}\n```')["steps"][0]["file"] == "a.py"


def test_truncated_plan_keeps_complete_steps():
    text = ('{"diagnosis": "d", "dependency_changes": [], "steps": [{"file": "a.py", "change": "x"}, '
            '{"file": "b.py", "change": "y"}, {"file": "c.py", "change": "unterminated')
    plan = _parse_plan(text)
    assert [s["file"] for s in plan["steps"]] == ["a.py", "b.py"]
    assert plan["truncated"] is True


def test_garbage_returns_none():
    assert _parse_plan("not json at all") is None
