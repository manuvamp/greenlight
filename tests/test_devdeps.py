from greenlight.devdeps import collect, poetry_spec


def test_poetry_caret_and_tilde():
    assert poetry_spec("^1.9.0") == ">=1.9.0,<2"
    assert poetry_spec("^0.13.1") == ">=0.13.1,<0.14"
    assert poetry_spec("~1.4") == "~=1.4"
    assert poetry_spec("1.2.3") == "==1.2.3"
    assert poetry_spec("*") == ""
    assert poetry_spec(">=1.2,<2") == ">=1.2,<2"


def test_collect_poetry_groups_hatch_and_pep735(tmp_path):
    (tmp_path / "pyproject.toml").write_text("""
[tool.poetry.dependencies]
python = "^3.8"
pydantic = "^1.10"

[tool.poetry.dev-dependencies]
pytest = "^6.2.5"
pyfakefs = "^5.2"
black = "^23"

[tool.poetry.group.docs.dependencies]
mkdocs = "*"

[tool.poetry.group.test.dependencies]
polyfactory = {version = "^2.0", extras = ["full"]}
local-thing = {path = "../x"}

[dependency-groups]
dev = ["hypothesis>=6", "pydantic<2"]

[tool.hatch.envs.default]
dependencies = ["respx"]
""")
    reqs = collect(tmp_path, "pydantic")
    assert "pytest" in reqs                         # unpinned: old pytest pins break on new Python
    assert "pyfakefs>=5.2,<6" in reqs
    assert "polyfactory[full]>=2.0,<3" in reqs
    assert "hypothesis" in reqs
    assert "respx" in reqs
    assert not any(r.startswith(("black", "mkdocs", "local-thing", "pydantic")) for r in reqs)


def test_collect_tox_deps(tmp_path):
    (tmp_path / "tox.ini").write_text("[testenv]\ndeps =\n    pytest-mock\n    -rrequirements.txt\n    freezegun==1.2\n")
    assert collect(tmp_path, "") == ["pytest-mock", "freezegun==1.2"]
