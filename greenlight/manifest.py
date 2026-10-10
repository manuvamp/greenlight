"""Find and rewrite a dependency's version constraint in Python manifests.

Handles requirements*.txt / constraints files, setup.py and setup.cfg install_requires,
PEP 621 pyproject dependencies, and Poetry `[tool.poetry.dependencies]`.
Pure text functions so they're easy to test; the workspace applies them inside the sandbox.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MANIFEST_GLOBS = [
    "requirements*.txt", "requirements/*.txt", "requirements/*.in", "requirements*.in",
    "constraints*.txt", "setup.py", "setup.cfg", "pyproject.toml", "tox.ini",
]


def norm(name: str) -> str:
    """PEP 503 normalized project name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _name_pattern(lib: str) -> str:
    # pydantic / Pydantic / pydantic_core must not match each other: match normalized forms only
    parts = re.split(r"[-_.]+", lib)
    return r"[-_.]+".join(re.escape(p) for p in parts)


@dataclass
class PinChange:
    file: str
    before: str
    after: str


def bump_text(text: str, lib: str, new_spec: str, filename: str = "") -> tuple[str, list[tuple[str, str]]]:
    """Replace every constraint on `lib` with `new_spec` (e.g. ">=2,<3"). Returns (new_text, [(old, new)])."""
    name = _name_pattern(lib)
    changes: list[tuple[str, str]] = []
    fname = filename.lower()

    def record(old: str, new: str) -> str:
        if old != new:
            changes.append((old.strip(), new.strip()))
        return new

    if fname.endswith("pyproject.toml"):
        # Poetry: pydantic = "^1.10"  /  pydantic = {version = "^1.10", extras = [...]}
        def poetry_str(m: re.Match) -> str:
            return record(m.group(0), f'{m.group(1)}"{new_spec}"')

        def poetry_tbl(m: re.Match) -> str:
            return record(m.group(0), f'{m.group(1)}"{new_spec}"{m.group(3)}')

        text = re.sub(rf'(?im)^(\s*{name}\s*=\s*)"[^"\n]*"', poetry_str, text)
        text = re.sub(rf'(?im)^(\s*{name}\s*=\s*\{{[^}}\n]*?version\s*=\s*)("[^"\n]*")([^}}\n]*\}})',
                      poetry_tbl, text)

    # Quoted requirement strings: setup.py, PEP 621 arrays, setup.cfg doesn't quote (handled below)
    def quoted(m: re.Match) -> str:
        q, nm, extras, marker = m.group(1), m.group(2), m.group(3) or "", m.group(5) or ""
        return record(m.group(0), f"{q}{nm}{extras}{new_spec}{marker}{q}")

    text = re.sub(
        rf'(["\'])({name})(\[[^\]"\']*\])?\s*((?:[<>=!~]=?|===)[^"\';]*)?(\s*;[^"\']*)?\1',
        quoted, text, flags=re.I,
    )

    # Unquoted requirement lines: requirements files, setup.cfg install_requires, tox deps
    if not fname.endswith((".py", "pyproject.toml")):
        def line(m: re.Match) -> str:
            indent, nm, extras, marker = m.group(1), m.group(2), m.group(3) or "", m.group(5) or ""
            return record(m.group(0), f"{indent}{nm}{extras}{new_spec}{marker}")

        text = re.sub(
            rf'(?im)^(\s*)({name})(\[[^\]\n]*\])?[ \t]*((?:[<>=!~]=?|===)[^;#\n]*)?([ \t]*;[^#\n]*)?(?=[ \t]*(?:#.*)?$)',
            line, text,
        )
    return text, changes


def mentions(text: str, lib: str) -> bool:
    return re.search(rf'(?i)(?<![\w.-]){_name_pattern(lib)}(?![\w-])', text) is not None


def requirement_spec(major_to: int) -> str:
    """Constraint for 'upgrade to major N': >=N,<N+1."""
    return f">={major_to},<{major_to + 1}"
