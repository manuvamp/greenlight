"""A repo inside a sandbox: clone, install into /venv, bump a pin, run the tests, read results.

The venv lives at /venv (outside /repo) so it never shows up in the diff.
"""

from __future__ import annotations

import io
import re
import shlex
import tarfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .executor.base import ExecResult, Sandbox
from .manifest import MANIFEST_GLOBS, bump_text, mentions, norm

VENV = "/venv"
PY = f"{VENV}/bin/python"
JUNIT = "/tmp/greenlight-junit.xml"
TEST_EXTRAS = ("test", "tests", "testing", "dev")


@dataclass
class TestRun:
    """Outcome of one test-suite run, keyed by test id (classname::name)."""
    results: dict[str, str] = field(default_factory=dict)  # id -> passed|failed|error|skipped
    failures: dict[str, str] = field(default_factory=dict)  # id -> message + traceback (clipped)
    exit_code: int = 0
    timed_out: bool = False
    collection_error: str = ""
    duration_s: float = 0.0
    output_tail: str = ""

    @property
    def passed(self) -> set[str]:
        return {k for k, v in self.results.items() if v == "passed"}

    @property
    def failed(self) -> set[str]:
        return {k for k, v in self.results.items() if v in ("failed", "error")}

    @property
    def skipped(self) -> set[str]:
        return {k for k, v in self.results.items() if v == "skipped"}

    def summary(self) -> str:
        return (f"{len(self.passed)} passed, {len(self.failed)} failed, {len(self.skipped)} skipped"
                + (" (TIMEOUT)" if self.timed_out else "")
                + (" (collection error)" if self.collection_error else ""))


def _tolerant_install(reqs: list[str]) -> str:
    """Install all at once; if that fails, one by one, skipping what won't install. Never fails."""
    q = " ".join(shlex.quote(r) for r in reqs)
    return (f"uv pip install --python {PY} {q} || "
            f"for r in {q}; do uv pip install --python {PY} \"$r\" || echo \"greenlight: skipped dev dep $r\"; done; true")


def parse_junit(xml_text: str) -> tuple[dict[str, str], dict[str, str]]:
    results: dict[str, str] = {}
    failures: dict[str, str] = {}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return results, failures
    for case in root.iter("testcase"):
        cid = f"{case.get('classname', '')}::{case.get('name', '')}"
        status = "passed"
        detail = ""
        for child in case:
            if child.tag in ("failure", "error"):
                status = "failed" if child.tag == "failure" else "error"
                detail = ((child.get("message") or "") + "\n" + (child.text or "")).strip()
                break
            if child.tag == "skipped":
                status = "skipped"
                detail = child.get("message") or ""
        # pytest reports collection errors as testcases with empty classname
        results[cid] = status
        if detail and status != "skipped":
            failures[cid] = detail[-4000:]
    return results, failures


@dataclass
class Project:
    manifests: list[str]
    python: str
    install_cmds: list[str]
    test_cmd: str


class Workspace:
    def __init__(self, sandbox: Sandbox, log=print, *, baseline_pins: list[str] | None = None,
                 extra_deps: list[str] | None = None, test_env: dict[str, str] | None = None,
                 target_lib: str = ""):
        self.sb = sandbox
        self.log = log
        self.project: Project | None = None
        self.target_lib = target_lib
        self.dev_deps: list[str] = []
        # Pins that only hold the *starting* state (e.g. numpy==1.26.4 for a repo with no cap).
        self.baseline_pins = list(baseline_pins or [])
        self.extra_deps = list(extra_deps or [])
        self.test_env = dict(test_env or {})

    def drop_pins(self, lib: str) -> None:
        """After the bump, stop forcing the old version of `lib` (and its old-major companions)."""
        self.baseline_pins = [p for p in self.baseline_pins if not mentions(p, lib)]

    # ---------- setup ----------

    def clone(self, repo_url: str, ref: str | None = None) -> None:
        r = self.sb.run(f"git clone --quiet {shlex.quote(repo_url)} /repo", cwd="/", timeout=600)
        if not r.ok:
            raise RuntimeError(f"git clone failed: {r.output[-2000:]}")
        if ref:
            r = self.sb.run(f"git fetch --quiet --depth 1 origin {shlex.quote(ref)} || true; "
                            f"git checkout --quiet {shlex.quote(ref)}", timeout=300)
            if not r.ok:
                raise RuntimeError(f"git checkout {ref} failed: {r.output[-2000:]}")
        self.sb.run("git checkout -q -b greenlight/upgrade", timeout=60)
        self.ignore_junk()

    def upload(self, local_dir: str) -> None:
        """Copy a local folder in as a fresh git repo (used for examples and local projects)."""
        buf = io.BytesIO()
        root = Path(local_dir)
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for p in sorted(root.rglob("*")):
                rel = p.relative_to(root)
                if any(part in (".git", ".venv", "__pycache__", "node_modules") for part in rel.parts):
                    continue
                tar.add(p, arcname=str(rel).replace("\\", "/"), recursive=False)
        self.sb.write_file("/tmp/src.tgz", buf.getvalue())
        r = self.sb.run("mkdir -p /repo && tar -xzf /tmp/src.tgz -C /repo && cd /repo && git init -q -b main "
                        "&& git add -A && git commit -q -m 'baseline' && git checkout -q -b greenlight/upgrade",
                        cwd="/", timeout=120)
        if not r.ok:
            raise RuntimeError(f"upload failed: {r.output[-2000:]}")
        self.ignore_junk()

    def ignore_junk(self) -> None:
        """Keep build/test byproducts out of the diff without touching the repo's own .gitignore."""
        self.sb.run("mkdir -p .git/info && printf '%s\\n' '__pycache__/' '*.pyc' '.pytest_cache/' "
                    "'*.egg-info/' 'build/' '.eggs/' '.coverage' 'coverage.xml' 'htmlcov/' "
                    ">> .git/info/exclude", timeout=30)

    def head(self) -> str:
        return self.sb.run("git rev-parse HEAD", timeout=30).stdout.strip()

    def find_manifests(self) -> list[str]:
        globs = " ".join(MANIFEST_GLOBS)
        r = self.sb.run(f"shopt -s nullglob; for f in {globs}; do [ -f \"$f\" ] && echo \"$f\"; done; true",
                        timeout=30)
        return [ln for ln in r.stdout.splitlines() if ln.strip()]

    def detect(self, python_hint: str | None = None, test_cmd: str | None = None, test_args: str = "") -> Project:
        manifests = self.find_manifests()
        texts = {m: self._read(m) for m in manifests}
        python = python_hint or self._guess_python(texts)

        cmds: list[str] = []
        req_files = [m for m in manifests if m.endswith((".txt", ".in")) and "constraint" not in m]
        has_pkg = any(m in ("pyproject.toml", "setup.py", "setup.cfg") for m in manifests)
        if has_pkg:
            extras = self._extras(texts)
            target = f".[{','.join(extras)}]" if extras else "."
            cmds.append(f"uv pip install --python {PY} -e {shlex.quote(target)}")
        for rf in sorted(req_files, key=lambda f: ("dev" in f or "test" in f, f)):
            cmds.append(f"uv pip install --python {PY} -r {shlex.quote(rf)}")
        self.dev_deps = self._dev_deps()
        if self.dev_deps:
            self.log(f"test/dev dependencies: {', '.join(self.dev_deps)}")
            cmds.append(_tolerant_install(self.dev_deps))
        cmds.append(f"uv pip install --python {PY} pytest pytest-timeout")
        if self.extra_deps:
            cmds.append(f"uv pip install --python {PY} " + " ".join(shlex.quote(d) for d in self.extra_deps))

        if not test_cmd:
            test_cmd = (f"{PY} -m pytest -q -rfE -p no:cacheprovider --timeout=120 "
                        f"--junitxml={JUNIT} -o junit_family=xunit2")
            if test_args:
                test_cmd += " " + test_args
        self.project = Project(manifests, python, cmds, test_cmd)
        return self.project

    def _dev_deps(self) -> list[str]:
        """Test/dev deps declared in Poetry groups, PEP 735, Hatch, PDM or tox (see devdeps.py)."""
        script = (Path(__file__).parent / "devdeps.py").read_text(encoding="utf-8")
        self.sb.write_file("/tmp/gl-devdeps.py", script)
        r = self.sb.run(f"python3 /tmp/gl-devdeps.py /repo {shlex.quote(self.target_lib)}", timeout=60)
        return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()] if r.ok else []

    def _read(self, path: str) -> str:
        try:
            return self.sb.read_file(path)
        except FileNotFoundError:
            return ""

    @staticmethod
    def _guess_python(texts: dict[str, str]) -> str:
        blob = "\n".join(texts.values())
        # Old pandas/numpy pins only ship wheels for older Pythons.
        if re.search(r"(?i)pandas\s*[<=~]=?\s*1\.[0-4]\b", blob):
            return "3.9"
        if re.search(r"(?i)pandas\s*(<\s*2|[=~]=\s*1\.5)", blob):
            return "3.10"
        m = re.search(r"python_requires\s*=\s*['\"]\s*>=\s*3\.(\d+)", blob) or \
            re.search(r"requires-python\s*=\s*['\"]\s*>=\s*3\.(\d+)", blob)
        if m and int(m.group(1)) >= 12:
            return "3.12"
        return "3.11"

    @staticmethod
    def _extras(texts: dict[str, str]) -> list[str]:
        blob = "\n".join(t for f, t in texts.items() if f in ("pyproject.toml", "setup.py", "setup.cfg"))
        return [e for e in TEST_EXTRAS
                if re.search(rf"(?m)^\s*['\"]?{e}['\"]?\s*[=:]\s*[\[\n]", blob)
                or re.search(rf"['\"]{e}['\"]\s*:", blob)]

    def install(self, timeout: int = 900) -> ExecResult:
        assert self.project
        p = self.project
        steps = [f"uv venv --quiet --python {p.python} {VENV}"] + p.install_cmds
        if self.baseline_pins:
            steps.append(f"uv pip install --python {PY} " + " ".join(shlex.quote(x) for x in self.baseline_pins))
        out: list[str] = []
        last = None
        for i, cmd in enumerate(steps):
            if i == 0 and self.sb.exists(f"{VENV}/bin/python"):
                continue
            last = self.sb.run(cmd, timeout=timeout)
            out.append(f"$ {cmd}\n{last.output[-6000:]}")
            if not last.ok:
                return ExecResult(last.exit_code, "\n".join(out), "", last.duration_s, last.timed_out)
        return ExecResult(0, "\n".join(out), "", last.duration_s if last else 0.0)

    def installed_version(self, lib: str) -> str | None:
        r = self.sb.run(f"{PY} -c \"import importlib.metadata as m; print(m.version('{lib}'))\"", timeout=60)
        return (r.stdout.strip() or None) if r.ok else None

    # ---------- bump ----------

    def bump(self, lib: str, spec: str) -> list[dict]:
        """Rewrite every constraint on `lib`. Returns the changes made."""
        assert self.project
        changed: list[dict] = []
        for m in self.project.manifests:
            text = self._read(m)
            if not mentions(text, lib):
                continue
            new, ch = bump_text(text, lib, spec, m)
            if ch:
                self.sb.write_file(m, new)
                changed += [{"file": m, "before": a, "after": b} for a, b in ch]
        return changed

    def force_install(self, lib: str, spec: str) -> ExecResult:
        """Make sure the target version is what's installed, whatever the manifests say."""
        return self.sb.run(f"uv pip install --python {PY} {shlex.quote(norm(lib) + spec)}", timeout=900)

    # ---------- tests ----------

    def run_tests(self, select: list[str] | None = None, timeout: int = 900) -> TestRun:
        assert self.project
        cmd = self.project.test_cmd
        if select:
            cmd += " " + " ".join(shlex.quote(s) for s in select)
        self.sb.run(f"rm -f {JUNIT}", timeout=30)
        r = self.sb.run(cmd, timeout=timeout, env={"PYTHONDONTWRITEBYTECODE": "1", **self.test_env})
        xml = ""
        try:
            xml = self.sb.read_file(JUNIT)
        except FileNotFoundError:
            pass
        results, failures = parse_junit(xml)
        tr = TestRun(results, failures, r.exit_code, r.timed_out, duration_s=r.duration_s,
                     output_tail=r.output[-8000:])
        # exit 2 = interrupted (often collection errors), 4 = usage error, 5 = no tests collected
        if r.exit_code in (2, 3, 4) or (not results and r.exit_code != 5):
            tr.collection_error = r.output[-6000:]
        return tr

    # ---------- diff ----------

    def diff(self) -> str:
        return self.sb.run("git add -A -N . && git diff", timeout=60).stdout

    def changed_files(self) -> list[str]:
        r = self.sb.run("git add -A -N . && git diff --name-only", timeout=60)
        return [f for f in r.stdout.splitlines() if f.strip()]
