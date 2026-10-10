"""Collect a project's test/dev dependencies from wherever it declares them.

Runs INSIDE the sandbox with the toolchain Python (3.12, has tomllib): the workspace writes this
file to /tmp and executes it, so it must only use the standard library. Prints one pip
requirement per line.

Sources: Poetry dev groups, PEP 735 [dependency-groups], Hatch envs, PDM dev-dependencies,
tox [testenv] deps. Lint/docs tools are skipped; pytest and its plugins are unpinned because
old pins (pytest ^3.4, ^6.2) don't run on modern Python.
"""

import configparser
import re
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None

SKIP = re.compile(r"^(black|flake8.*|isort|mypy|pylint|ruff|pre-commit|autopep8|yapf|bandit|"
                  r"sphinx.*|mkdocs.*|furo|myst.*|twine|build|wheel|setuptools|poetry.*|tox|nox|"
                  r"ipython|jupyter.*|notebook|types-.*|codecov|coveralls|python)$", re.I)
UNPIN = re.compile(r"^(pytest(-.*)?|coverage|hypothesis)$", re.I)
SKIP_GROUPS = re.compile(r"(?i)^(docs?|lint|style|typing|release|publish)$")


def norm(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def poetry_spec(spec):
    spec = spec.strip()
    if spec in ("*", ""):
        return ""
    out = []
    for part in spec.split(","):
        part = part.strip()
        m = re.match(r"^\^(\d+)(?:\.(\d+))?(?:\.(\d+))?", part)
        if m:
            major, minor = int(m.group(1)), int(m.group(2) or 0)
            lo = part[1:]
            hi = f"{major + 1}" if major > 0 else f"0.{minor + 1}"
            out.append(f">={lo},<{hi}")
            continue
        m = re.match(r"^~(\d+(?:\.\d+)*)$", part)
        if m:
            v = m.group(1)
            out.append(f"~={v}" if v.count(".") >= 1 else f">={v},<{int(v) + 1}")
            continue
        if re.match(r"^\d", part):
            out.append(f"=={part}")
        else:
            out.append(part)
    return ",".join(out)


def from_poetry_table(tbl):
    reqs = []
    for name, spec in (tbl or {}).items():
        if name.lower() == "python":
            continue
        if isinstance(spec, dict):
            if "path" in spec or "git" in spec or "url" in spec:
                continue
            extras = f"[{','.join(spec['extras'])}]" if spec.get("extras") else ""
            reqs.append(name + extras + poetry_spec(spec.get("version", "*")))
        elif isinstance(spec, list):
            continue
        else:
            reqs.append(name + poetry_spec(str(spec)))
    return reqs


def collect(root, skip_lib):
    reqs = []
    py = root / "pyproject.toml"
    if py.exists() and tomllib:
        data = tomllib.loads(py.read_text(encoding="utf-8", errors="replace"))
        tool = data.get("tool", {})
        poetry = tool.get("poetry", {})
        reqs += from_poetry_table(poetry.get("dev-dependencies"))
        for gname, group in (poetry.get("group") or {}).items():
            if not SKIP_GROUPS.match(gname):
                reqs += from_poetry_table(group.get("dependencies"))
        for gname, items in (data.get("dependency-groups") or {}).items():
            if not SKIP_GROUPS.match(gname):
                reqs += [i for i in items if isinstance(i, str)]
        for ename, env in ((tool.get("hatch") or {}).get("envs") or {}).items():
            if ename in ("default", "test", "tests", "dev") and isinstance(env, dict):
                reqs += [d for d in env.get("dependencies", []) if isinstance(d, str)]
                reqs += [d for d in env.get("extra-dependencies", []) if isinstance(d, str)]
        for gname, items in ((tool.get("pdm") or {}).get("dev-dependencies") or {}).items():
            if not SKIP_GROUPS.match(gname):
                reqs += [i for i in items if isinstance(i, str)]
    tox = root / "tox.ini"
    if tox.exists():
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            cp.read_string(tox.read_text(encoding="utf-8", errors="replace"))
            if cp.has_option("testenv", "deps"):
                for line in cp.get("testenv", "deps").splitlines():
                    line = line.strip()
                    if line and not line.startswith(("-", "{", "#", ".")) and "{" not in line:
                        reqs.append(line)
        except configparser.Error:
            pass

    out, seen = [], set()
    for r in reqs:
        r = r.split(";")[0].strip()
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?(.*)$", r)
        if not m:
            continue
        name, extras, spec = m.group(1), m.group(2) or "", m.group(3).strip()
        key = norm(name)
        if key in seen or SKIP.match(name) or key == norm(skip_lib):
            continue
        seen.add(key)
        if UNPIN.match(name):
            spec = ""
        out.append(f"{name}{extras}{spec}")
    return out


if __name__ == "__main__":
    for line in collect(Path(sys.argv[1] if len(sys.argv) > 1 else "."), sys.argv[2] if len(sys.argv) > 2 else ""):
        print(line)
