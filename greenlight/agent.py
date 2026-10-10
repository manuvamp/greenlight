"""The upgrade run: baseline → bump → research → plan → fix ⟲ → verify.

Model routing (see models.py):
  Ultra     plans the migration, and re-plans when the editor stalls
  Super     edits code through tools until the tests pass
  Lightning digests migration guides and writes the PR description
"""

from __future__ import annotations

import ast
import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .budget import Budget, BudgetExceeded
from .events import EventLog
from .executor.base import Executor
from .llm import LLM, LLMError, LLMTruncated, record_to_dict
from .manifest import requirement_spec
from .models import Role
from .research import Researcher, RuleSheet
from .tools import READ_MARK, SCHEMAS, ToolBox, is_test_file, norm_path
from .triage import group_failures, render
from .verify import VerifyReport, verify
from .workspace import TestRun, Workspace

PYTHON_FALLBACKS = ["3.11", "3.10", "3.12", "3.9"]
MAX_PROMPT_RULES = 40
BULK_MAX_FILES = 16
BULK_MAX_LINES = 700

BULK_SYSTEM = """You migrate ONE file of a project whose dependency `{lib}` was upgraded {from_v} → {to_v} ({spec}).
Return the COMPLETE migrated file in a single fenced code block, and nothing else.
- Apply every relevant migration below; keep all other code, comments, order and formatting identical.
- Use the real new APIs. Never use compatibility shims (e.g. pydantic.v1).
- Keep behaviour identical. If a feature moved to another package, import it from there
  (and for a requirements/pyproject file, add that package).
- Never loosen or remove the {lib} constraint.
- If nothing in this file needs to change, return it unchanged.

Migration rules (from the official guide):
{rules}"""


@dataclass
class UpgradeSpec:
    source: str                 # git URL or local folder
    lib: str
    to_major: int
    ref: str | None = None      # commit / branch / tag
    spec: str | None = None     # override constraint, default ">=N,<N+1"
    python: str | None = None
    test_cmd: str | None = None
    test_policy: str = "audited"      # frozen | audited (API-only test migrations) | free
    max_iterations: int = 6
    steps_per_iteration: int = 40
    max_minutes: float = 20
    model_override: str | None = None  # e.g. all-Ultra ablation
    use_research: bool = True          # ablation: no Tavily rule sheet
    editor: str = "super-first"        # super-first | cascade | lightning | super | ultra
    test_args: str = ""                # appended to the pytest command (paths, -o addopts="", --deselect …)
    test_env: dict = field(default_factory=dict)
    baseline_pins: list = field(default_factory=list)  # hold the starting state, e.g. numpy==1.26.4
    extra_deps: list = field(default_factory=list)     # e.g. pytest<8
    precheck: bool = False             # stop after baseline + bump (no model calls)
    bulk: bool = True                  # one-pass parallel migration of planned files before the tool loop
    test_args: str = ""                # appended to the default pytest command
    test_env: dict = field(default_factory=dict)
    baseline_pins: list = field(default_factory=list)  # hold the starting versions, e.g. numpy==1.26.4
    extra_deps: list = field(default_factory=list)     # e.g. pytest<8 for old suites
    stop_after_bump: bool = False      # precheck: baseline + bump only, no model calls

    @property
    def target_spec(self) -> str:
        return self.spec or requirement_spec(self.to_major)


@dataclass
class RunResult:
    run_id: str
    status: str                 # green | partial | failed | error | noop
    headline: str
    lib: str
    from_version: str = ""
    to_version: str = ""
    baseline: dict = field(default_factory=dict)
    final: dict = field(default_factory=dict)
    verify: dict = field(default_factory=dict)
    diff: str = ""
    pin_changes: list = field(default_factory=list)
    patches: list = field(default_factory=list)
    iterations: int = 0
    escalations: int = 0
    usd: float = 0.0
    tavily_credits: int = 0
    seconds: float = 0.0
    calls: list = field(default_factory=list)
    summary: str = ""


def _run_stats(r: TestRun) -> dict:
    return {"passed": len(r.passed), "failed": len(r.failed), "skipped": len(r.skipped),
            "total": len(r.results), "collection_error": bool(r.collection_error)}


PLAN_SYSTEM = """You are the planner of Greenlight, an agent that upgrades a Python dependency across a major version
and fixes the code so the project's existing test suite passes again.

You get: the project layout, the failing test groups after the version bump, call sites of APIs that changed,
and a rule sheet distilled from the official migration guide (rule ids like R14).

Write a migration plan as JSON:
{"diagnosis": "2-4 sentences on what broke and why",
 "dependency_changes": ["e.g. add pydantic-settings>=2 to requirements.txt", ...],
 "steps": [{"file": "path", "change": "what to change, concretely", "rules": ["R14"], "why": "short"}],
 "risks": ["behaviour changes to watch for"]}

Rules:
- Change library/application code. Test files are the contract: only touch one when the test itself
  uses a removed/renamed API (e.g. imports BaseSettings from pydantic) and then only migrate that API;
  never change, remove or skip an assertion or a test.
- Prefer the real new APIs over compatibility layers (never use pydantic.v1 or similar shims).
- Cover every call site of a changed API, not only the ones the failing tests hit.
- Keep behaviour identical; note any semantic changes (defaults, validation order) as steps or risks.
- If a new package is needed (e.g. a feature moved to a separate distribution), list it in dependency_changes.
- Be concise: at most 25 steps, one sentence each. Group repeated changes into one step per file
  ("apply R14, R37 throughout"), never one step per call site."""

EDIT_SYSTEM = """You are the code editor of Greenlight. The project's dependency `{lib}` was just upgraded to {spec}
({from_v} → {to_v}) and the test suite broke. Make the existing tests pass again by migrating the code.

Use the tools efficiently; every turn costs time and money:
- Read all the files you need in ONE turn (several read_file calls in a single response).
- For a file under ~250 lines that needs several changes, use `rewrite_file` once with the complete new content.
  For a large file, or one or two small changes, use `apply_patch` (several in one turn is fine).
- Then run the tests. Re-read a file before patching it again.
- `apply_patch` needs an exact, unique `search` snippet copied from read_file output (without the line-number prefix).
- Tag each patch or rewrite with the rule id(s) it applies, e.g. "R14 R37".
- Fix library code first. Edit a test file ONLY to migrate an API the test itself uses (imports, renamed
  calls); assertions, test functions and markers must stay as they are (the tool enforces this).
- Never loosen or remove the {lib} upgrade pin. Never use compatibility shims (e.g. pydantic.v1),
  and never create a module named after the library to fake the old API.
- If a feature moved to another package, add it to the requirements file, then call `reinstall`.
- When a failure isn't covered by the rules, call `search_docs` with a precise query.
- Call `finish` once the suite passes (or if you are truly stuck, explaining why).

Migration rules (from the official guide; ids for citations):
{rules}"""


class Upgrader:
    def __init__(self, spec: UpgradeSpec, executor: Executor, *, llm: LLM | None = None,
                 budget: Budget | None = None, events: EventLog | None = None,
                 run_id: str | None = None, runs_dir: Path | None = None):
        self.spec = spec
        self.executor = executor
        self.run_id = run_id or f"{spec.lib}-{spec.to_major}-{uuid.uuid4().hex[:8]}"
        self.budget = budget or Budget()
        self.llm = llm or LLM(self.budget, model_override=spec.model_override)
        path = (runs_dir / f"{self.run_id}.jsonl") if runs_dir else None
        self.ev = events or EventLog(self.run_id, path)
        self.calls: list[dict] = []
        self.llm.on_call(self._on_llm)
        self.t0 = time.monotonic()

    def _on_llm(self, rec) -> None:
        d = record_to_dict(rec)
        self.calls.append(d)
        self.ev.emit("llm", **d)

    def _elapsed_min(self) -> float:
        return (time.monotonic() - self.t0) / 60

    def _budget_low(self, frac: float = 0.85) -> bool:
        """Leave headroom so a run that runs low can still re-test, verify and write its PR."""
        spent = sum(c["usd"] for c in self.calls)
        return spent >= frac * self.budget.caps.usd_per_run

    # ------------------------------------------------------------------

    def run(self) -> RunResult:
        s = self.spec
        self.ev.emit("run", run_id=self.run_id, source=s.source, ref=s.ref, lib=s.lib, to_major=s.to_major,
                     spec=s.target_spec, executor=self.executor.name, backend=self.llm.backend,
                     model_override=s.model_override, use_research=s.use_research)
        res = RunResult(self.run_id, "error", "", s.lib)
        sb = None
        try:
            sb = self.executor.open()
            ws = Workspace(sb, log=self.ev.log, baseline_pins=s.baseline_pins, extra_deps=s.extra_deps,
                           test_env=s.test_env, target_lib=s.lib)
            self._prepare(ws)
            baseline = self._baseline(ws, res)
            if baseline is None:
                return self._finish(res, ws)
            bumped = self._bump(ws, res)
            if bumped is None:
                return self._finish(res, ws)
            if s.precheck:
                broken = len(baseline.passed - bumped.passed)
                res.status = "precheck-ok" if broken else "precheck-noop"
                res.final = _run_stats(bumped)
                res.headline = (f"baseline {len(baseline.passed)} pass; after bump {broken} of them break"
                                if broken else "the bump breaks nothing; not a useful case")
                return self._finish(res, ws)
            if not (baseline.passed - bumped.passed):
                res.status, res.headline = "noop", "tests already pass after the bump; only the pin changed"
                res.final = _run_stats(bumped)
                res.verify = verify(ws, baseline, bumped, s.lib, s.to_major, s.test_policy).as_dict()
                return self._finish(res, ws)
            sheet = self._research() if s.use_research else RuleSheet(s.lib, 0, s.to_major)
            final = self._fix(ws, baseline, bumped, sheet, res)
            rep = verify(ws, baseline, final, s.lib, s.to_major, s.test_policy)
            self.ev.emit("verify", **rep.as_dict())
            res.final = _run_stats(final)
            res.verify = rep.as_dict()
            kept = len(baseline.passed & final.passed)
            total = len(baseline.passed)
            if rep.passed:
                res.status = "green"
                res.headline = f"{s.lib} {res.from_version} → {res.to_version}: all {total} baseline tests pass"
            elif kept / max(total, 1) >= 0.8 and kept > len(baseline.passed & bumped.passed):
                res.status = "partial"
                res.headline = f"{kept}/{total} baseline tests pass after migration"
            else:
                res.status = "failed"
                res.headline = f"{kept}/{total} baseline tests pass; verification failed"
            res.summary = self._write_summary(ws, res, rep, sheet)
            return self._finish(res, ws)
        except BudgetExceeded as e:
            res.status, res.headline = "error", f"stopped by budget guard: {e}"
            self.ev.log(res.headline, level="error")
            return self._finish(res, None)
        except Exception as e:  # noqa: BLE001
            res.status, res.headline = "error", f"{type(e).__name__}: {e}"
            self.ev.log(res.headline, level="error")
            return self._finish(res, None)
        finally:
            if sb:
                try:
                    if res.diff == "" and res.status in ("green", "partial", "failed"):
                        res.diff = Workspace(sb).diff()
                except Exception:
                    pass
                sb.close()

    def _finish(self, res: RunResult, ws: Workspace | None) -> RunResult:
        if ws is not None and not res.diff:
            try:
                res.diff = ws.diff()
            except Exception:
                pass
        t = self.budget.totals()
        res.usd = round(sum(c["usd"] for c in self.calls), 5)
        res.tavily_credits = t.tavily_credits  # informational (ledger-wide)
        res.seconds = round(time.monotonic() - self.t0, 1)
        res.calls = self.calls
        self.ev.emit("result", **{k: v for k, v in asdict(res).items() if k not in ("calls",)})
        return res

    # ---------- stages ----------

    def _prepare(self, ws: Workspace) -> None:
        s = self.spec
        self.ev.stage("prepare", detail=s.source)
        if s.source.startswith(("http://", "https://", "git@")):
            ws.clone(s.source, s.ref)
        else:
            ws.upload(s.source)
        self.ev.log(f"commit {ws.head()[:12]}")
        p = ws.detect(s.python, s.test_cmd, s.test_args)
        self.ev.emit("project", manifests=p.manifests, python=p.python, test_cmd=p.test_cmd)
        tried = []
        for py in [p.python] + [v for v in PYTHON_FALLBACKS if v != p.python]:
            p.python = py
            tried.append(py)
            ws.sb.run("rm -rf /venv", timeout=60)
            r = ws.install()
            if r.ok:
                self.ev.stage("prepare", "done", detail=f"python {py}, deps installed")
                return
            self.ev.log(f"install failed on python {py}: {r.output.splitlines()[-1][:200] if r.output else ''}")
            if s.python:
                break
        raise RuntimeError(f"could not install the project (tried python {', '.join(tried)})")

    def _baseline(self, ws: Workspace, res: RunResult) -> TestRun | None:
        s = self.spec
        self.ev.stage("baseline")
        res.from_version = ws.installed_version(s.lib) or ""
        if not res.from_version:
            res.status, res.headline = "error", f"{s.lib} is not installed by this project"
            return None
        if int(res.from_version.split(".")[0]) >= s.to_major:
            res.status, res.headline = "noop", f"already on {s.lib} {res.from_version}"
            return None
        run = ws.run_tests()
        res.baseline = _run_stats(run)
        self.ev.emit("tests", label="baseline", summary=run.summary(), **_run_stats(run))
        if not run.passed:
            res.status, res.headline = "error", "no passing tests at baseline; nothing to protect"
            self.ev.log(run.output_tail[-1500:])
            return None
        self.ev.stage("baseline", "done", detail=f"{s.lib}=={res.from_version}, {run.summary()}")
        return run

    def _bump(self, ws: Workspace, res: RunResult) -> TestRun | None:
        s = self.spec
        self.ev.stage("bump", detail=f"{s.lib}{s.target_spec}")
        changes = ws.bump(s.lib, s.target_spec)
        ws.drop_pins(s.lib)
        res.pin_changes = changes
        self.ev.emit("pins", changes=changes)
        if not changes:
            self.ev.log(f"no pin on {s.lib} in the manifests; installing the target directly")
        r = ws.install()
        if not r.ok:
            self.ev.log("manifest install failed after the bump (likely a co-dependency pin); "
                        "forcing the target and leaving the conflict to the planner")
            self.install_conflict = r.output[-3000:]
        else:
            self.install_conflict = ""
        f = ws.force_install(s.lib, s.target_spec)
        if not f.ok:
            res.status, res.headline = "error", f"could not install {s.lib}{s.target_spec}: {f.output[-300:]}"
            return None
        res.to_version = ws.installed_version(s.lib) or ""
        run = ws.run_tests()
        self.ev.emit("tests", label="after bump", summary=run.summary(), **_run_stats(run))
        self.ev.stage("bump", "done", detail=f"{s.lib}=={res.to_version}: {run.summary()}")
        return run

    def _research(self) -> RuleSheet:
        s = self.spec
        self.ev.stage("research", detail=f"{s.lib} migration guide")
        fr = 1 if s.lib.lower() in ("pydantic", "numpy", "pandas") else s.to_major - 1
        self.researcher = Researcher(self.llm, self.ev, self.run_id, self.budget)
        sheet = self.researcher.rule_sheet(s.lib, fr, s.to_major)
        self.ev.stage("research", "done", detail=f"{len(sheet.rules)} rules from {len(sheet.sources)} sources")
        return sheet

    # ---------- fix loop ----------

    def _relevant_rules(self, ws: Workspace, sheet: RuleSheet, failures_text: str) -> tuple[set[str], str]:
        """Rules whose grep pattern hits non-test code, or whose identifiers appear in the failures."""
        hits: dict[str, list[str]] = {}
        greppable = [r for r in sheet.rules if r.grep]
        if greppable:
            script = "\n".join(
                f"echo '@@{r.id}'; git grep -nIE {_shq(r.grep)} -- '*.py' ':!tests' ':!test' ':!**/test_*.py' | head -n 8"
                for r in greppable)
            out = ws.sb.run(script, timeout=120).stdout
            cur = None
            for ln in out.splitlines():
                if ln.startswith("@@"):
                    cur = ln[2:]
                elif cur and ln.strip():
                    hits.setdefault(cur, []).append(ln)
        low = failures_text.lower()
        for r in sheet.rules:
            for ident in re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", r.old):
                if ident.lower() in low and ident.lower() not in ("field", "model", "config", "class"):
                    hits.setdefault(r.id, [])
                    break
        self._rule_hits = hits
        # Rules with real call sites first, then the ones only named in the failures; cap the total.
        with_sites = [r for r in sheet.rules if hits.get(r.id)]
        named = [r for r in sheet.rules if r.id in hits and not hits[r.id]]
        chosen = (with_sites + named)[:MAX_PROMPT_RULES]
        lines = []
        for r in chosen:
            sites = hits[r.id]
            site_txt = ("\n    " + "\n    ".join(s[:160] for s in sites[:3])) if sites else ""
            note = f" — {r.note[:140]}" if r.note else ""
            lines.append(f"[{r.id}] {r.old} → {r.new}{note}{site_txt}")
        return {r.id for r in chosen}, "\n".join(lines)

    def _plan(self, ws: Workspace, failures: str, rules_txt: str, extra: str = "", role: Role = Role.PLAN) -> dict:
        s = self.spec
        files = ws.sb.run("git ls-files '*.py' | head -n 200", timeout=60).stdout
        user = (f"Upgrade: {s.lib} {self.from_v} → {self.to_v} (constraint {s.target_spec})\n\n"
                f"Python files:\n{files}\n\n"
                + (f"Dependency install conflict after the bump:\n{self.install_conflict}\n\n" if self.install_conflict else "")
                + f"Failures after the bump:\n{failures}\n\n"
                f"Relevant migration rules with call sites:\n{rules_txt or '(none matched; rely on the failures)'}\n"
                + (f"\n{extra}" if extra else ""))
        msgs = [{"role": "system", "content": PLAN_SYSTEM}, {"role": "user", "content": user}]
        plan = None
        for attempt, (tokens, think) in enumerate([(12000, None), (8000, False)]):
            try:
                r = self.llm.chat(role, msgs, run=self.run_id, max_tokens=tokens, json_mode=True,
                                  thinking=think)
            except LLMError as e:
                self.ev.log(f"planner call failed ({type(e).__name__})")
                continue
            plan = _parse_plan(r.content)
            if plan is not None:
                break
            self.ev.log("planner returned no usable JSON; retrying without reasoning" if attempt == 0
                        else "planner output still unusable; continuing with a minimal plan")
        if plan is None:
            # The call sites found by the rule grep still drive the migration pass.
            plan = {"diagnosis": "Planner output was unusable; migrating every file with matched call sites.",
                    "dependency_changes": [], "steps": [], "risks": []}
        self.ev.emit("plan", escalation=role == Role.ESCALATE, **plan)
        return plan

    def _fix(self, ws: Workspace, baseline: TestRun, bumped: TestRun, sheet: RuleSheet, res: RunResult) -> TestRun:
        s = self.spec
        self.from_v, self.to_v = res.from_version, res.to_version
        current = bumped
        groups = group_failures(current)
        failures = render(groups, current)
        _, rules_txt = self._relevant_rules(ws, sheet, failures)
        self.ev.stage("plan")
        plan = self._plan(ws, failures, rules_txt)
        self.ev.stage("plan", "done", detail=f"{len(plan.get('steps', []))} steps")

        def run_tests_tool(select: str) -> str:
            nonlocal current
            sel = select.split() if select else None
            tr = ws.run_tests(sel)
            if not sel:
                current = tr
                kept = len(baseline.passed & tr.passed)
                self.ev.emit("tests", label="fix", summary=tr.summary(), kept=kept,
                             of=len(baseline.passed), **_run_stats(tr))
            else:
                self.ev.emit("tests", label="selected", summary=tr.summary(), **_run_stats(tr))
            if not tr.failed and not tr.collection_error:
                return f"ALL PASS: {tr.summary()}"
            return render(group_failures(tr), tr, limit_chars=7000)

        lookup = (lambda q: self.researcher.lookup(s.lib, q)) if s.use_research else (lambda q: "search disabled")
        tb = ToolBox(ws, self.ev, s.lib, s.target_spec, lookup, run_tests_tool, s.test_policy)

        progress = ""
        if s.bulk:
            self.ev.stage("migrate", detail="Super migrates each planned file in one pass, in parallel")
            n = self._bulk_migrate(ws, plan, sheet, tb)
            if any(not p.path.endswith(".py") for p in tb.patches):
                self.ev.log(f"manifests changed; reinstalling: {tb.t_reinstall().splitlines()[0]}")
            if n:
                failures = run_tests_tool("")
                progress = ws.diff()
            self.ev.stage("migrate", "done", detail=f"{n} file(s) migrated; "
                          f"{len(baseline.passed & current.passed)}/{len(baseline.passed)} baseline tests pass")
            if baseline.passed <= current.passed:
                res.patches = [p.__dict__ for p in tb.patches]
                return current

        tiers = _editor_tiers(s.editor)
        tier = 0
        best_kept = len(baseline.passed & current.passed)
        last_sig = _failure_signature(current)
        stalls = replans = 0
        messages = self._editor_messages(plan, failures, rules_txt, progress=progress)
        for it in range(1, s.max_iterations + 1):
            res.iterations = it
            editor = tiers[tier]
            self.ev.stage("fix", detail=f"iteration {it} · editor {editor.label}")
            tb.finished = None
            out_of_budget = False
            for _ in range(s.steps_per_iteration):
                if self._elapsed_min() > s.max_minutes:
                    self.ev.log("time limit reached")
                    break
                if self._budget_low():
                    self.ev.log("run budget nearly used; stopping the fix loop to verify and report")
                    out_of_budget = True
                    break
                try:
                    r = self.llm.chat(Role.EDIT, _trim_history(messages), run=self.run_id, tools=SCHEMAS,
                                      max_tokens=8192, temperature=0.2, model_id=editor.id)
                except LLMTruncated:
                    # Usually a whole-file rewrite that didn't fit. Recover instead of failing the run.
                    self.ev.log("editor reply hit the output limit; asking for smaller edits")
                    messages.append({"role": "user", "content":
                                     "Your last reply was cut off at the output limit and was lost. Make smaller "
                                     "changes: use apply_patch with focused snippets instead of rewriting big files."})
                    continue
                except BudgetExceeded as e:
                    self.ev.log(f"budget guard: {e}; stopping the fix loop to verify and report")
                    out_of_budget = True
                    break
                messages.append(_assistant_msg(r))
                if not r.tool_calls:
                    messages.append({"role": "user", "content": "Use the tools to continue, or call finish."})
                    continue
                for tc in r.tool_calls:
                    fn = tc["function"]
                    out = tb.call(fn["name"], fn.get("arguments") or "{}")
                    if out.startswith(("OK: patched", "OK: rewrote")):
                        _drop_stale_reads(messages, fn.get("arguments") or "{}")
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": out})
                _compact_tool_args(messages[-1 - len(r.tool_calls)])
                if tb.finished is not None:
                    break
            # Always judge by a fresh full run, not the model's word.
            final_text = run_tests_tool("")
            kept = len(baseline.passed & current.passed)
            self.ev.stage("fix", "done", detail=f"iteration {it}: {kept}/{len(baseline.passed)} baseline tests pass")
            if baseline.passed <= current.passed:
                break
            if self._elapsed_min() > s.max_minutes or out_of_budget or self._budget_low():
                break
            # Progress = more baseline tests pass, or the failures changed (e.g. an import error that
            # hid the whole suite is gone). Only a run that changes nothing counts as a stall.
            sig = _failure_signature(current)
            if kept > best_kept or sig != last_sig:
                best_kept, stalls = max(best_kept, kept), 0
            else:
                stalls += 1
            last_sig = sig
            if stalls and tier < len(tiers) - 1:
                tier += 1
                res.escalations += 1
                stalls = 0
                self.ev.stage("escalate", detail=f"no progress; editor moves up to {tiers[tier].label}")
                # Fresh, compact context for the stronger model instead of the weaker one's transcript.
                messages = self._editor_messages(plan, final_text, rules_txt, progress=ws.diff())
            elif stalls:
                if replans >= 2:
                    self.ev.log("still stuck after two re-plans; stopping")
                    break
                replans += 1
                res.escalations += 1
                self.ev.stage("escalate", detail="no progress; Nemotron 3 Ultra re-plans from the current state")
                _, rules_txt = self._relevant_rules(ws, sheet, final_text)
                plan = self._plan(ws, final_text, rules_txt, role=Role.ESCALATE,
                                  extra=f"Changes so far (git diff):\n{ws.diff()[-8000:]}\n"
                                        "The previous plan stalled. Find what was missed.")
                messages = self._editor_messages(plan, final_text, rules_txt, progress=ws.diff())
                stalls = 0
            else:
                messages.append({"role": "user", "content":
                                 f"Tests still failing after your changes:\n{final_text}\nContinue."})
        res.patches = [p.__dict__ for p in tb.patches]
        return current

    # ---------- bulk migration: one call per file, in parallel ----------

    def _bulk_targets(self, ws: Workspace, plan: dict) -> list[str]:
        planned = [st.get("file", "") for st in plan.get("steps", []) if isinstance(st, dict)]
        if plan.get("dependency_changes") and ws.project:
            planned += [m for m in ws.project.manifests if "requirements" in m or m == "pyproject.toml"][:2]
        with_sites = {site.split(":", 1)[0] for sites in self._rule_hits.values() for site in sites}
        out: list[str] = []
        for f in planned + sorted(with_sites):
            f = norm_path(f or "")
            if not f or f in out or is_test_file(f):
                continue
            if not (f.endswith(".py") or "requirements" in f or f in ("pyproject.toml", "setup.py", "setup.cfg")):
                continue
            if ws.sb.exists(f):
                out.append(f)
        return out[:BULK_MAX_FILES]

    def _bulk_migrate(self, ws: Workspace, plan: dict, sheet: RuleSheet, tb: ToolBox) -> int:
        s = self.spec
        targets = self._bulk_targets(ws, plan)
        by_id = {r.id: r for r in sheet.rules}

        def one(path: str) -> tuple[str, str, str] | None:
            current = ws.sb.read_file(path)
            n_lines = len(current.splitlines())
            if n_lines > BULK_MAX_LINES:
                return None
            ids = [rid for rid, sites in self._rule_hits.items()
                   if any(x.startswith(f"{path}:") for x in sites)]
            ids += [rid for rid, sites in self._rule_hits.items() if not sites][:10]
            rules = "\n".join(f"[{rid}] {by_id[rid].old} → {by_id[rid].new}"
                              f"{(' — ' + by_id[rid].note[:140]) if by_id[rid].note else ''}"
                              for rid in dict.fromkeys(ids) if rid in by_id)[:9000]
            steps = [st for st in plan.get("steps", []) if isinstance(st, dict) and norm_path(st.get("file", "")) == path]
            deps = plan.get("dependency_changes") or []
            msgs = [{"role": "system", "content": BULK_SYSTEM.format(
                        lib=s.lib, from_v=self.from_v, to_v=self.to_v, spec=s.target_spec,
                        rules=rules or "(no specific rules; use your knowledge of the migration)")},
                    {"role": "user", "content":
                        f"Planned changes for this file: {json.dumps(steps)}\n"
                        + (f"Dependency changes in the plan: {json.dumps(deps)}\n" if deps and not path.endswith('.py') else "")
                        + f"\nFile `{path}`:\n```\n{current}\n```"}]
            budget = min(16000, int(len(current) / 2.5) + 1000)

            def check(text: str) -> tuple[str | None, str]:
                new = _code_block(text)
                if new is None:
                    return None, "no code block in the reply"
                if new.strip() == current.strip():
                    return None, "unchanged"
                if path.endswith(".py"):
                    try:
                        ast.parse(new)
                    except SyntaxError as e:
                        return None, f"syntax error at line {e.lineno}"
                if n_lines >= 20 and len(new.splitlines()) < 0.6 * n_lines:
                    return None, f"looks truncated ({len(new.splitlines())} of {n_lines} lines)"
                return new, ""

            r = self.llm.chat(Role.EDIT, msgs, run=self.run_id, max_tokens=budget, thinking=False, temperature=0.1)
            new, why = check(r.content)
            if new is None and why != "unchanged":
                # One retry, with the problem spelled out; partial files are the usual failure.
                msgs = msgs + [{"role": "assistant", "content": r.content[-4000:]},
                               {"role": "user", "content": f"That reply was unusable ({why}). Return the ENTIRE "
                                f"file, all {n_lines} lines with the migrations applied, in one code block."}]
                r = self.llm.chat(Role.EDIT, msgs, run=self.run_id, max_tokens=budget, thinking=False, temperature=0.0)
                new, why = check(r.content)
            if new is None:
                self.ev.log(f"bulk rewrite of {path} skipped: {why}")
                return None
            return path, current, new

        results = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            for fut in [pool.submit(one, p) for p in targets]:
                try:
                    out = fut.result()
                except (LLMError, OSError) as e:
                    self.ev.log(f"bulk rewrite failed: {e}")
                    out = None
                if out:
                    results.append(out)
        for path, current, new in results:
            msg = tb.t_rewrite_file(path, new, rule="bulk")
            if not msg.startswith("OK"):
                self.ev.log(f"bulk rewrite of {path}: {msg}")
        return sum(1 for p in tb.patches if p.rule == "bulk")

    def _editor_messages(self, plan: dict, failures: str, rules_txt: str, progress: str = "") -> list[dict]:
        s = self.spec
        system = EDIT_SYSTEM.format(lib=s.lib, spec=s.target_spec, from_v=self.from_v, to_v=self.to_v,
                                    rules=rules_txt or "(no rules matched; use search_docs when unsure)")
        compact_plan = {k: plan.get(k) for k in ("diagnosis", "dependency_changes", "steps") if plan.get(k)}
        user = f"Migration plan from the planner:\n{json.dumps(compact_plan, separators=(',', ':'))[:7000]}\n\n"
        if progress:
            user += (f"Changes already made (git diff, keep the good parts):\n{progress[-6000:]}\n\n")
        user += f"Current failures:\n{failures}\n\nStart by reading the files you need to change."
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def _write_summary(self, ws: Workspace, res: RunResult, rep: VerifyReport, sheet: RuleSheet) -> str:
        cited = sorted({rid.strip() for p in res.patches for rid in re.split(r"[,\s]+", p.get("rule") or "") if rid.strip()})
        by_id = {r.id: r for r in sheet.rules}
        refs = "\n".join(f"- {rid}: {by_id[rid].old} → {by_id[rid].new} ({by_id[rid].url}"
                         f"{'#' + by_id[rid].section if by_id[rid].section else ''})"
                         for rid in cited if rid in by_id)
        msgs = [{"role": "system", "content": "Write a concise pull-request description in GitHub markdown."},
                {"role": "user", "content":
                    f"Upgrade {self.spec.lib} {res.from_version} → {res.to_version}.\n"
                    f"Result: {res.headline}\nVerification: {json.dumps(rep.as_dict())}\n"
                    f"Pin changes: {json.dumps(res.pin_changes)}\n"
                    f"Migration rules applied (cite these):\n{refs or '(none tagged)'}\n"
                    f"Diff:\n{ws.diff()[:12000]}\n\n"
                    "Sections: Summary (2-3 sentences), Changes (table: file | change | source rule link), "
                    "Verification (bullet list from the checks), Notes (behaviour changes reviewers should check). "
                    "End with: '_Opened by Greenlight · Nemotron on Nebius Token Factory_'."}]
        try:
            return self.llm.chat(Role.WRITE, msgs, run=self.run_id, max_tokens=2500).content
        except (LLMError, BudgetExceeded) as e:
            return f"(summary unavailable: {e})"


def _parse_plan(text: str) -> dict | None:
    """Parse the planner's JSON. If it was cut off mid-way, keep every complete step before the cut."""
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else ""
        raw = raw.rsplit("```", 1)[0]
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    # Truncated: cut back to the last complete step object inside "steps" and close the JSON.
    i = raw.find('"steps"')
    if i < 0:
        return None
    for end in range(len(raw) - 1, i, -1):
        if raw[end] != "}":
            continue
        try:
            data = json.loads(raw[: end + 1] + "]}")
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("steps"):
            data["truncated"] = True
            return data
    return None


def _code_block(text: str) -> str | None:
    """The body of the last fenced code block, or None."""
    blocks = re.findall(r"```[a-zA-Z0-9_+-]*\n(.*?)```", text or "", flags=re.S)
    if not blocks:
        return None
    body = blocks[-1]
    return body if body.endswith("\n") else body + "\n"


def _editor_tiers(editor: str) -> list:
    """Editor models, cheapest first. Past the last tier, stalls are handled by an Ultra re-plan."""
    from .models import LIGHTNING, SUPER, ULTRA
    return {"cascade": [LIGHTNING, SUPER], "lightning": [LIGHTNING], "super": [SUPER], "ultra": [ULTRA],
            "super-first": [SUPER]}[editor]


def _failure_signature(run: TestRun) -> frozenset:
    sigs = {g.signature for g in group_failures(run)} if (run.failed or run.collection_error) else set()
    return frozenset(sigs | {f"failed={len(run.failed)}"})


def _assistant_msg(r) -> dict:
    m = {"role": "assistant", "content": r.content or ""}
    if r.tool_calls:
        m["tool_calls"] = [{"id": tc["id"], "type": "function",
                            "function": {"name": tc["function"]["name"],
                                         "arguments": tc["function"].get("arguments") or "{}"}}
                           for tc in r.tool_calls]
    return m


def _drop_stale_reads(messages: list[dict], args_json: str) -> None:
    """After a file changes, earlier read_file copies of it are wrong; replace them with a stub."""
    try:
        path = norm_path(json.loads(args_json).get("path", ""))
    except (json.JSONDecodeError, AttributeError):
        return
    if not path:
        return
    prefix = f"{READ_MARK}{path} ("
    for m in messages:
        if m.get("role") == "tool" and (m.get("content") or "").startswith(prefix):
            m["content"] = f"{READ_MARK}{path}: (outdated copy removed; the file has changed since. Re-read it if needed.)"


def _compact_tool_args(assistant_msg: dict) -> None:
    """Once a write has executed, the model doesn't need the full file it sent sitting in history."""
    for tc in assistant_msg.get("tool_calls") or []:
        fn = tc["function"]
        if fn["name"] not in ("rewrite_file", "apply_patch"):
            continue
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            continue
        if fn["name"] == "rewrite_file" and len(args.get("content", "")) > 300:
            args["content"] = f"<{len(args['content'].splitlines())} lines written; re-read the file to see it>"
        for k in ("search", "replace"):
            if len(args.get(k, "")) > 600:
                args[k] = args[k][:250] + " … " + args[k][-250:]
        fn["arguments"] = json.dumps(args)


def _msg_chars(m: dict) -> int:
    n = len(m.get("content") or "")
    for tc in m.get("tool_calls") or []:
        n += len(tc["function"].get("arguments") or "")
    return n


def _trim_history(messages: list[dict], budget_chars: int = 40_000) -> list[dict]:
    """Shrink old tool outputs once the conversation grows, keeping the recent ones intact."""
    total = sum(_msg_chars(m) for m in messages)
    if total <= budget_chars:
        return messages
    out = [dict(m) for m in messages]
    for m in out[2:-6]:
        if m["role"] == "tool" and len(m.get("content") or "") > 400:
            total -= len(m["content"]) - 300
            m["content"] = m["content"][:300] + "\n… (older output trimmed)"
            if total <= budget_chars:
                break
    return out


def _shq(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"
