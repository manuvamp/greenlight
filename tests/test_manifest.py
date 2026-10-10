from greenlight.manifest import bump_text, mentions

SPEC = ">=2,<3"


def test_requirements_pinned():
    out, ch = bump_text("fastapi==0.95\npydantic==1.10.13\nrequests\n", "pydantic", SPEC, "requirements.txt")
    assert "pydantic>=2,<3\n" in out
    assert "fastapi==0.95" in out
    assert ch == [("pydantic==1.10.13", "pydantic>=2,<3")]


def test_requirements_extras_marker_comment():
    src = "pydantic[email] < 2 ; python_version >= '3.8'  # pinned\n"
    out, ch = bump_text(src, "pydantic", SPEC, "requirements.txt")
    assert out.startswith("pydantic[email]>=2,<3; python_version >= '3.8'")
    assert "# pinned" in out
    assert len(ch) == 1


def test_does_not_touch_similar_names():
    src = "pydantic-settings==1.0\npydantic_core==2.0\npydantic>=1.8,<2\n"
    out, ch = bump_text(src, "pydantic", SPEC, "requirements.txt")
    assert "pydantic-settings==1.0" in out
    assert "pydantic_core==2.0" in out
    assert "pydantic>=2,<3" in out
    assert len(ch) == 1


def test_setup_py_install_requires():
    src = 'install_requires=["numpy<2", "scipy>=1.7", \'pandas >= 1.3, <2.0\']'
    out, _ = bump_text(src, "numpy", SPEC, "setup.py")
    assert '"numpy>=2,<3"' in out and '"scipy>=1.7"' in out
    out2, _ = bump_text(src, "pandas", SPEC, "setup.py")
    assert "'pandas>=2,<3'" in out2


def test_pep621_pyproject():
    src = '[project]\ndependencies = [\n  "pydantic>=1.10,<2",\n  "httpx",\n]\n'
    out, ch = bump_text(src, "pydantic", SPEC, "pyproject.toml")
    assert '"pydantic>=2,<3"' in out
    assert len(ch) == 1


def test_poetry_string_and_table():
    src = '[tool.poetry.dependencies]\npython = "^3.10"\npydantic = "^1.10"\nnumpy = {version = "^1.24", optional = true}\n'
    out, _ = bump_text(src, "pydantic", "^2", "pyproject.toml")
    assert 'pydantic = "^2"' in out
    out2, _ = bump_text(src, "numpy", "^2", "pyproject.toml")
    assert 'numpy = {version = "^2", optional = true}' in out2


def test_setup_cfg_unquoted():
    src = "[options]\ninstall_requires =\n    numpy>=1.20,<2\n    click\n"
    out, ch = bump_text(src, "numpy", SPEC, "setup.cfg")
    assert "    numpy>=2,<3\n" in out
    assert len(ch) == 1


def test_unpinned_name_gets_constraint():
    out, ch = bump_text("pandas\nnumpy\n", "pandas", SPEC, "requirements.txt")
    assert out.splitlines()[0] == "pandas>=2,<3"
    assert len(ch) == 1


def test_mentions():
    assert mentions("pydantic==1.10", "pydantic")
    assert not mentions("pydantic-settings==1.0", "pydantic")


def test_keywords_and_classifiers_untouched():
    src = ('[project]\nkeywords = ["hashicorp", "pydantic"]\n'
           'dependencies = [\n  "pydantic",\n  "hvac>=0.10",\n]\n')
    out, ch = bump_text(src, "pydantic", SPEC, "pyproject.toml")
    assert 'keywords = ["hashicorp", "pydantic"]' in out
    assert '"pydantic>=2,<3"' in out
    assert len(ch) == 1


def test_setup_py_keywords_untouched():
    src = 'setup(keywords=["pydantic", "vault"], install_requires=["pydantic", "hvac"])'
    out, ch = bump_text(src, "pydantic", SPEC, "setup.py")
    assert 'keywords=["pydantic", "vault"]' in out
    assert 'install_requires=["pydantic>=2,<3", "hvac"]' in out
