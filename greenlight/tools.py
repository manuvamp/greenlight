"""Tools the editor model can call. Each one runs inside the sandbox and returns plain text.

Guardrails live here, not in the prompt: test files and the target pin can't be edited
(unless the run allows test edits), and patches must match exactly once.
"""

from __future__ import annotations

import difflib
import json
import re
import shlex
from dataclasses import dataclass, field
from typing import Callable

from .events import EventLog
from .manifest import mentions
from .workspace import Workspace

MAX_READ_LINES = 400
MAX_GREP_LINES = 120
READ_MARK = "FILE "  # prefix of read_file output; lets the agent find and drop stale copies

TEST_PATH = re.compile(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")


def is_test_file(path: str) -> bool:
    return bool(TEST_PATH.search(path.replace("\\", "/")))


def norm_path(path: str) -> str:
    """Repo-relative path, whatever form the model used."""
    return path.replace("\\", "/").removeprefix("/repo/").removeprefix("./").lstrip("/")


SCHEMAS = [
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a file from the repo with line numbers. Use start/end to page through big files.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "start": {"type": "integer", "description": "first line (1-based)"},
            "end": {"type": "integer", "description": "last line (inclusive)"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "grep",
        "description": "Search the repo (git grep -nE). Returns file:line:text.",
        "parameters": {"type": "object", "properties": {
            "pattern": {"type": "string", "description": "POSIX extended regex"},
            "path": {"type": "string", "description": "optional path or glob to limit the search"}},
            "required": ["pattern"]}}},
    {"type": "function", "function": {
        "name": "apply_patch",
        "description": ("Replace an exact snippet in a file. `search` must match the file exactly once "
                        "(include enough surrounding lines). To create a new file, use search=\"\"."),
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "search": {"type": "string"},
            "replace": {"type": "string"},
            "rule": {"type": "string", "description": "rule id(s) from the rule sheet this change applies, e.g. R14"}},
            "required": ["path", "search", "replace"]}}},
    {"type": "function", "function": {
        "name": "rewrite_file",
        "description": ("Replace a whole file with new content. Best for files under ~250 lines that need many "
                        "changes: one call instead of many patches. Keep everything that doesn't need to change."),
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "content": {"type": "string", "description": "the complete new file"},
            "rule": {"type": "string", "description": "rule ids applied, e.g. R14 R37"}},
            "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "run_tests",
        "description": "Run the test suite (or selected test ids/paths) and get a summary of failures.",
        "parameters": {"type": "object", "properties": {
            "select": {"type": "array", "items": {"type": "string"},
                       "description": "optional pytest node ids or paths"}}}}},
    {"type": "function", "function": {
        "name": "reinstall",
        "description": "Reinstall dependencies from the manifests (after editing requirements/pyproject).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "search_docs",
        "description": "Search the web (official docs first) for how to fix a specific migration problem.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Call when the suite passes, or when you can make no further progress.",
        "parameters": {"type": "object", "properties": {
            "summary": {"type": "string", "description": "what you changed and why, briefly"}},
            "required": ["summary"]}}},
]


@dataclass
class Patch:
    path: str
    rule: str
    added: int
    removed: int


@dataclass
class ToolBox:
    ws: Workspace
    ev: EventLog
    lib: str
    target_spec: str
    lookup: Callable[[str], str]
    on_tests: Callable[[str], str]  # runs tests, returns condensed text
    allow_test_edits: bool = False
    patches: list[Patch] = field(default_factory=list)
    finished: str | None = None
    state: int = 0                      # bumps on every successful patch/reinstall
    since_tests: int = 0                # tool calls since the last full test run
    _seen: dict = field(default_factory=dict)
    _lookups: dict = field(default_factory=dict)

    def call(self, name: str, args_json: str) -> str:
        try:
            args = json.loads(args_json or "{}")
        except json.JSONDecodeError as e:
            return f"ERROR: arguments are not valid JSON ({e})"
        fn = getattr(self, f"t_{name}", None)
        if not fn:
            return f"ERROR: unknown tool {name}"
        # Repeat guard: the same call against the same code state gives the same answer.
        key = (name, json.dumps(args, sort_keys=True), self.state)
        self._seen[key] = self._seen.get(key, 0) + 1
        if self._seen[key] > 1 and name not in ("finish",):
            out = ("REPEATED: you already made this exact call and nothing has changed since. "
                   "Use what you learned: apply a patch, run the tests, or call finish.")
            self.ev.emit("tool", name=name, brief=_brief(name, args), result_brief="refused: repeated call")
            return out
        self.since_tests = 0 if name == "run_tests" else self.since_tests + 1
        try:
            out = fn(**args)
        except TypeError as e:
            out = f"ERROR: bad arguments for {name}: {e}"
        except Exception as e:  # noqa: BLE001
            out = f"ERROR: {type(e).__name__}: {e}"
        self.ev.emit("tool", name=name, brief=_brief(name, args), result_brief=out.splitlines()[0][:140] if out else "")
        if self.since_tests >= 12 and name != "run_tests":
            out += "\n\n(Reminder: you have made many changes since the last run_tests. Run the tests now.)"
        return out

    # ---------- tools ----------

    def t_read_file(self, path: str, start: int = 1, end: int | None = None,
                    offset: int | None = None, limit: int | None = None) -> str:
        if offset is not None:
            start = int(offset) + (0 if int(offset) >= 1 else 1)
        if limit is not None:
            end = start + int(limit) - 1
        path = norm_path(path)
        text = self.ws.sb.read_file(path)
        lines = text.splitlines()
        start = max(1, int(start or 1))
        end = min(len(lines), int(end) if end else start + MAX_READ_LINES - 1)
        body = "\n".join(f"{i:5d}| {lines[i - 1]}" for i in range(start, end + 1))
        more = f"\n... ({len(lines) - end} more lines; read with start={end + 1})" if end < len(lines) else ""
        return f"{READ_MARK}{path} (lines {start}-{end} of {len(lines)})\n{body}{more}"

    def t_grep(self, pattern: str, path: str | None = None) -> str:
        cmd = f"git grep -nIE {shlex.quote(pattern)}"
        if path:
            cmd += f" -- {shlex.quote(path)}"
        r = self.ws.sb.run(cmd + f" | head -n {MAX_GREP_LINES + 1}", timeout=60)
        lines = r.stdout.splitlines()
        if not lines:
            return "no matches"
        extra = "\n... (more matches truncated)" if len(lines) > MAX_GREP_LINES else ""
        return "\n".join(lines[:MAX_GREP_LINES]) + extra

    def t_apply_patch(self, path: str, search: str, replace: str, rule: str = "") -> str:
        path = norm_path(path)
        if is_test_file(path) and not self.allow_test_edits:
            return ("REFUSED: test files are the contract and can't be edited in this run. "
                    "Fix the library code so the existing tests pass.")
        try:
            current = self.ws.sb.read_file(path)
        except FileNotFoundError:
            current = None
        if search == "":
            if current is not None:
                return "ERROR: file exists; give a non-empty `search` snippet to edit it"
            new = replace
        else:
            if current is None:
                return f"ERROR: {path} does not exist"
            n = current.count(search)
            if n == 0:
                hint = _closest(current, search)
                return f"ERROR: search text not found in {path}.{hint}"
            if n > 1:
                return f"ERROR: search text matches {n} places in {path}; include more context to make it unique"
            new = current.replace(search, replace, 1)
        if "requirements" in path or "constraints" in path or path.endswith(("pyproject.toml", "setup.py", "setup.cfg")):
            if self._rolls_back_pin(current or "", new):
                return f"REFUSED: that edit loosens or removes the {self.lib}{self.target_spec} upgrade pin"
        self.ws.sb.write_file(path, new)
        self.state += 1
        added = max(0, replace.count("\n") + 1) if replace else 0
        removed = max(0, search.count("\n") + 1) if search else 0
        self.patches.append(Patch(path, rule, added, removed))
        self.ev.emit("patch", path=path, rule=rule, search=search[:2000], replace=replace[:2000],
                     added=added, removed=removed)
        return f"OK: patched {path}"

    def t_rewrite_file(self, path: str, content: str, rule: str = "") -> str:
        path = norm_path(path)
        if is_test_file(path) and not self.allow_test_edits:
            return "REFUSED: test files are the contract and can't be edited in this run."
        try:
            current = self.ws.sb.read_file(path)
        except FileNotFoundError:
            return f"ERROR: {path} does not exist (use apply_patch with search=\"\" to create files)"
        old_n, new_n = len(current.splitlines()), len(content.splitlines())
        if old_n >= 20 and new_n < 0.6 * old_n:
            return (f"REFUSED: the rewrite has {new_n} lines but the file has {old_n}; it looks truncated. "
                    "Rewrite the complete file or use apply_patch.")
        if ("requirements" in path or path.endswith(("pyproject.toml", "setup.py", "setup.cfg"))) \
                and self._rolls_back_pin(current, content):
            return f"REFUSED: that edit loosens or removes the {self.lib}{self.target_spec} upgrade pin"
        if not content.endswith("\n"):
            content += "\n"
        if content == current:
            return "NO CHANGE: the content is identical to the current file"
        self.ws.sb.write_file(path, content)
        self.state += 1
        diff = list(difflib.unified_diff(current.splitlines(), content.splitlines(), lineterm="", n=0))
        added = sum(1 for d in diff if d.startswith("+") and not d.startswith("+++"))
        removed = sum(1 for d in diff if d.startswith("-") and not d.startswith("---"))
        self.patches.append(Patch(path, rule, added, removed))
        self.ev.emit("patch", path=path, rule=rule, rewrite=True, diff="\n".join(diff)[:4000],
                     added=added, removed=removed)
        return f"OK: rewrote {path} (+{added}/-{removed} lines)"

    def t_run_tests(self, select: list[str] | None = None) -> str:
        return self.on_tests(" ".join(select or []))

    def t_reinstall(self) -> str:
        self.state += 1
        r = self.ws.install()
        self.ws.force_install(self.lib, self.target_spec)
        v = self.ws.installed_version(self.lib)
        return (f"{'OK' if r.ok else 'FAILED'}: install exit {r.exit_code}; {self.lib}=={v}\n"
                + (r.output[-3000:] if not r.ok else ""))

    def t_search_docs(self, query: str) -> str:
        q = " ".join(query.lower().split())
        if q not in self._lookups:
            self._lookups[q] = self.lookup(query)
        return self._lookups[q]

    def t_finish(self, summary: str) -> str:
        self.finished = summary
        return "OK"

    # ---------- helpers ----------

    def _rolls_back_pin(self, before: str, after: str) -> bool:
        lib = re.escape(self.lib)
        pat = re.compile(rf"(?i){lib}\s*(\[[^\]]*\])?\s*([<>=!~^][^\"'\n;#,\]]*(?:,[^\"'\n;#\]]*)*)")
        old = [m.group(2).strip() for m in pat.finditer(before)]
        new = [m.group(2).strip() for m in pat.finditer(after)]
        if old and not new and mentions(before, self.lib) and not mentions(after, self.lib):
            return True  # removed the requirement entirely
        major = re.search(r"\d+", self.target_spec)
        if not major:
            return False
        bad = re.compile(rf"(<\s*{major.group(0)}\b|==\s*{int(major.group(0)) - 1}\.|~=\s*{int(major.group(0)) - 1}\.)")
        return any(bad.search(s) for s in new) and not any(bad.search(s) for s in old)


def _brief(name: str, args: dict) -> str:
    if name in ("apply_patch", "rewrite_file"):
        return f"{args.get('path')}{' ' + args['rule'] if args.get('rule') else ''}"
    if name in ("read_file",):
        return args.get("path", "")
    if name == "grep":
        return args.get("pattern", "")[:60]
    if name == "search_docs":
        return args.get("query", "")[:80]
    if name == "run_tests":
        return " ".join(args.get("select") or [])[:80]
    return ""


def _closest(text: str, search: str) -> str:
    """Help the model recover from a near-miss patch: name the first line that doesn't match and show
    what the file really contains there."""
    lines = text.splitlines()
    anchor = None
    for s_ln in search.splitlines():
        if not s_ln.strip():
            continue
        if s_ln not in text:
            target = s_ln.strip()
            # best guess at where it should be: the line sharing the most words with it
            words = set(re.findall(r"\w+", target))
            best, score = None, 0
            for i, ln in enumerate(lines):
                sc = len(words & set(re.findall(r"\w+", ln)))
                if sc > score:
                    best, score = i, sc
            near = ""
            if best is not None and score:
                lo, hi = max(0, best - 3), min(len(lines), best + 4)
                near = "\n" + "\n".join(f"{j + 1:5d}| {lines[j]}" for j in range(lo, hi))
            return f" This line is not in the file: {target!r}. Closest current text:{near}"
        anchor = s_ln
    if anchor is not None:
        return " Every line exists but not in this order/adjacency; re-read the file and copy the block exactly."
    return " Re-read the file; it may have changed."
