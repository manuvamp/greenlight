// Pure selectors: every panel of the run view is derived from the (possibly partial) event list,
// so seeking, instant mode and live streaming all share one code path.

import { MODELS, modelFor } from "../models";
import type { ModelInfo } from "../models";
import type {
  PatchEvent, PinChange, PlanEvent, ProjectEvent, ResultEvent, RunEvent, RunStartEvent,
  RunStatus, SourceEvent, StageEvent, TestsEvent, VerifyEvent,
} from "../types";

// ---------------- stages ----------------

export const PIPELINE = ["prepare", "baseline", "bump", "research", "plan", "fix", "verify", "pr"] as const;
export type PipelineStep = (typeof PIPELINE)[number];
export type NodeState = "pending" | "active" | "done" | "failed";

export const STEP_LABEL: Record<PipelineStep, string> = {
  prepare: "Prepare", baseline: "Baseline", bump: "Bump", research: "Research",
  plan: "Plan", fix: "Fix", verify: "Verify", pr: "PR",
};

const EXTRA_LABEL: Record<string, string> = { migrate: "Migrate", escalate: "Escalate" };

export function stageLabel(name: string): string {
  return STEP_LABEL[name as PipelineStep] ?? EXTRA_LABEL[name] ?? name.charAt(0).toUpperCase() + name.slice(1);
}

/** Stages that render inside another pipeline node. */
const NODE_OF: Record<string, PipelineStep> = { migrate: "fix" };

/** Rule ids worth showing as chips ("R12"), not placeholders like "bulk". */
export function ruleChips(rule: string | undefined): string[] {
  return (rule ?? "").split(/\s+/).filter((r) => /^[A-Za-z]{0,3}\d+[a-z]?$/.test(r));
}

export interface StageNode {
  key: PipelineStep;
  label: string;
  state: NodeState;
  note: string | null;
  t: number | null;
}

// ---------------- tests ----------------

export type MeterState = "idle" | "green" | "red" | "partial" | "import-error";

export interface TestPoint {
  seq: number;
  t: number;
  label: string;
  passed: number;
  total: number;
  state: MeterState;
  summary: string;
}

export interface Meter {
  passed: number;
  total: number;
  state: MeterState;
  label: string;
  seq: number | null;
}

// ---------------- models ----------------

export interface ModelRow {
  info: ModelInfo;
  calls: number;
  tokensIn: number;
  tokensOut: number;
  usd: number;
  latency: number;
  roles: string[];
  thinking: boolean;
  lastSeq: number | null;
}

// ---------------- feed ----------------

export type FeedTone = "ok" | "err" | "warn" | "muted" | "accent" | "info";
export type FeedIcon =
  | "stage" | "read_file" | "apply_patch" | "rewrite_file" | "run_tests" | "search_docs"
  | "reinstall" | "finish" | "tool" | "tests" | "log" | "llm" | "tavily" | "pins" | "escalate" | "verify";

export interface FeedItem {
  id: number;
  t: number;
  icon: FeedIcon;
  tone: FeedTone;
  title: string;
  detail: string | null;
  added?: number;
  removed?: number;
  chips?: string[];
}

// ---------------- full view ----------------

export type ViewStatus = "pending" | "running" | RunStatus;

export interface RunView {
  run: RunStartEvent | null;
  project: ProjectEvent | null;
  status: ViewStatus;
  stages: StageNode[];
  iterations: number;
  escalations: number;
  fromVersion: string | null;
  toVersion: string | null;
  tests: TestPoint[];
  meter: Meter;
  baselineTotal: number | null;
  models: ModelRow[];
  llmCalls: number;
  usd: number;
  tokensIn: number;
  tokensOut: number;
  sources: SourceEvent[];
  rulesCount: number | null;
  tavilyCredits: number;
  tavilyOps: number;
  researchCached: boolean;
  plans: PlanEvent[];
  feed: FeedItem[];
  patches: PatchEvent[];
  pins: PinChange[];
  verify: VerifyEvent | null;
  result: ResultEvent | null;
  lastT: number;
}

const VERSION_RE = /==\s*([^\s,:;]+)/;

function meterOf(e: TestsEvent, baselineTotal: number | null): Omit<Meter, "label" | "seq"> {
  const total = baselineTotal ?? e.of ?? e.total;
  if (e.collection_error) return { passed: 0, total: Math.max(total, 1), state: "import-error" };
  const passed = Math.min(e.kept ?? e.passed, total || e.passed);
  const state: MeterState = total > 0 && passed >= total ? "green" : passed === 0 ? "red" : "partial";
  return { passed, total, state };
}

function tidyResult(brief: string): { ok: boolean; refused: boolean; text: string } {
  const refused = /^refused/i.test(brief);
  const err = /^error/i.test(brief);
  return { ok: !refused && !err, refused, text: brief.replace(/\s*Closest current text:\s*$/i, "") };
}

export function deriveRun(events: RunEvent[]): RunView {
  let run: RunStartEvent | null = null;
  let project: ProjectEvent | null = null;
  let verify: VerifyEvent | null = null;
  let result: ResultEvent | null = null;
  const stageEvents: StageEvent[] = [];
  const tests: TestPoint[] = [];
  let baselineTotal: number | null = null;
  let meter: Meter = { passed: 0, total: 0, state: "idle", label: "waiting for baseline", seq: null };
  const modelMap = new Map<string, ModelRow>();
  let usd = 0;
  let tokensIn = 0;
  let tokensOut = 0;
  let llmCalls = 0;
  const sources: SourceEvent[] = [];
  const seenUrls = new Set<string>();
  let rulesCount: number | null = null;
  let tavilyCredits = 0;
  let tavilyOps = 0;
  let researchCached = false;
  const plans: PlanEvent[] = [];
  const feed: FeedItem[] = [];
  const patches: PatchEvent[] = [];
  let pins: PinChange[] = [];
  let pendingPatchIdx: number | null = null;
  let writeStarted = false;
  let lastT = 0;

  for (const e of events) {
    lastT = Math.max(lastT, e.t);
    switch (e.type) {
      case "run":
        run = e;
        break;
      case "project":
        project = e;
        break;
      case "stage": {
        stageEvents.push(e);
        if (e.name === "escalate") {
          feed.push({ id: e.seq, t: e.t, icon: "escalate", tone: "warn", title: "Escalated", detail: e.detail ?? null });
        } else if (e.status === "start") {
          feed.push({ id: e.seq, t: e.t, icon: "stage", tone: "accent", title: stageLabel(e.name), detail: e.detail ?? null });
        } else if (e.status === "fail") {
          feed.push({ id: e.seq, t: e.t, icon: "stage", tone: "err", title: `${stageLabel(e.name)} failed`, detail: e.detail ?? null });
        }
        if (e.name === "research" && e.status === "done" && rulesCount == null && e.detail) {
          const m = e.detail.match(/(\d+)\s+rules?/);
          if (m) rulesCount = Number(m[1]);
        }
        break;
      }
      case "log":
        feed.push({
          id: e.seq, t: e.t, icon: "log",
          tone: e.level === "error" ? "err" : e.level === "warn" || e.level === "warning" ? "warn" : "muted",
          title: e.msg, detail: null,
        });
        if (/from cache/i.test(e.msg)) researchCached = true;
        break;
      case "tests": {
        if (e.label === "baseline" && baselineTotal == null) baselineTotal = e.total;
        const m = meterOf(e, baselineTotal);
        const point: TestPoint = { seq: e.seq, t: e.t, label: e.label, passed: m.passed, total: m.total, state: m.state, summary: e.summary };
        if (e.label !== "selected") {
          tests.push(point);
          meter = { ...m, seq: e.seq, label: e.label };
        }
        feed.push({
          id: e.seq, t: e.t, icon: "tests",
          tone: m.state === "green" ? "ok" : m.state === "partial" ? "warn" : "err",
          title: m.state === "import-error" ? `Tests · import error` : `Tests · ${m.passed}/${m.total} pass`,
          detail: `${e.label} · ${e.summary}`,
        });
        break;
      }
      case "pins":
        pins = e.changes;
        feed.push({
          id: e.seq, t: e.t, icon: "pins", tone: "info", title: "Pin bumped",
          detail: e.changes.map((c) => `${c.file}: ${c.before} → ${c.after}`).join(" · "),
        });
        break;
      case "source":
        if (!seenUrls.has(e.url)) {
          seenUrls.add(e.url);
          sources.push(e);
        }
        if (e.cached) researchCached = true;
        break;
      case "tavily":
        tavilyCredits += e.credits || 0;
        tavilyOps += 1;
        feed.push({
          id: e.seq, t: e.t, icon: "tavily", tone: "info",
          title: e.op === "search" ? "Tavily search" : "Tavily extract",
          detail: e.op === "search" ? (e.query ?? null) : `${e.urls?.length ?? 0} pages`,
          chips: [`${e.credits} cr`],
        });
        break;
      case "rules":
        rulesCount = e.count;
        break;
      case "llm": {
        llmCalls += 1;
        usd += e.usd || 0;
        tokensIn += e.tokens_in || 0;
        tokensOut += e.tokens_out || 0;
        const info = modelFor(e.model_label || e.model) ?? {
          key: "nano" as const, label: e.model_label || e.model, short: e.model_label || e.model, size: "",
          job: "", usdIn: 0, usdOut: 0, color: "var(--text-3)", match: /$^/,
        };
        const key = modelFor(e.model_label || e.model)?.key ?? `x:${e.model}`;
        const row = modelMap.get(key) ?? {
          info, calls: 0, tokensIn: 0, tokensOut: 0, usd: 0, latency: 0, roles: [], thinking: false, lastSeq: null,
        };
        row.calls += 1;
        row.tokensIn += e.tokens_in || 0;
        row.tokensOut += e.tokens_out || 0;
        row.usd += e.usd || 0;
        row.latency += e.latency_s || 0;
        row.thinking = row.thinking || e.thinking;
        row.lastSeq = e.seq;
        if (!row.roles.includes(e.role)) row.roles.push(e.role);
        modelMap.set(key, row);
        if (e.role === "write") writeStarted = true;
        if (e.role !== "edit") {
          feed.push({
            id: e.seq, t: e.t, icon: "llm", tone: "accent",
            title: `${e.model_label} · ${e.role === "write" ? "wrote the PR" : e.role === "plan" ? "planned" : e.role}`,
            detail: `${e.tokens_in.toLocaleString()} → ${e.tokens_out.toLocaleString()} tok${e.thinking ? " · thinking" : ""}`,
          });
        }
        break;
      }
      case "plan":
        plans.push(e);
        break;
      case "patch": {
        patches.push(e);
        feed.push({
          id: e.seq, t: e.t, icon: e.rewrite ? "rewrite_file" : "apply_patch", tone: "ok",
          title: e.path, detail: null, added: e.added, removed: e.removed,
          chips: e.rule === "bulk" ? ["bulk"] : ruleChips(e.rule),
        });
        pendingPatchIdx = feed.length - 1;
        break;
      }
      case "tool": {
        const r = tidyResult(e.result_brief || "");
        const isEdit = e.name === "apply_patch" || e.name === "rewrite_file";
        if (isEdit && r.ok && pendingPatchIdx != null) {
          // The patch event already describes this edit; fold the tool confirmation into it.
          pendingPatchIdx = null;
          break;
        }
        pendingPatchIdx = null;
        if (e.name === "run_tests") break; // the tests event right before it carries the numbers
        const known: FeedIcon[] = ["read_file", "apply_patch", "rewrite_file", "run_tests", "search_docs", "reinstall", "finish"];
        const icon: FeedIcon = (known as string[]).includes(e.name) ? (e.name as FeedIcon) : "tool";
        let title = e.name.replace(/_/g, " ");
        let detail: string | null = e.brief || null;
        let tone: FeedTone = "muted";
        if (e.name === "read_file") {
          title = r.text.replace(/^FILE\s+/i, "") || e.brief;
          detail = null;
        } else if (e.name === "finish") {
          title = "Editor finished";
          detail = null;
          tone = "ok";
        } else if (!r.ok) {
          tone = r.refused ? "warn" : "err";
          title = `${e.name.replace(/_/g, " ")} ${r.refused ? "refused" : "missed"}`;
          detail = `${e.brief ? e.brief.split(" ")[0] + " · " : ""}${r.text.replace(/^ERROR:\s*/i, "")}`;
        } else if (e.name === "reinstall") {
          title = "Reinstalled deps";
          detail = r.text.replace(/^OK:\s*/i, "");
        } else {
          detail = [e.brief, r.text].filter(Boolean).join(" → ") || null;
        }
        feed.push({ id: e.seq, t: e.t, icon, tone, title, detail });
        break;
      }
      case "verify":
        verify = e;
        feed.push({
          id: e.seq, t: e.t, icon: "verify", tone: e.passed ? "ok" : "err",
          title: e.passed ? "Verification passed" : "Verification failed",
          detail: `${e.checks.filter((c) => c.ok).length}/${e.checks.length} anti-cheat checks`,
        });
        break;
      case "result":
        result = e;
        if (!verify && e.verify && Array.isArray(e.verify.checks)) {
          verify = { type: "verify", seq: e.seq, t: e.t, passed: e.verify.passed, checks: e.verify.checks };
        }
        break;
    }
  }

  // ----- versions -----
  let fromVersion = result?.from_version ?? null;
  let toVersion = result?.to_version ?? null;
  for (const s of stageEvents) {
    if (s.status !== "done" || !s.detail) continue;
    const m = s.detail.match(VERSION_RE);
    if (!m) continue;
    if (s.name === "baseline" && !fromVersion) fromVersion = m[1];
    if (s.name === "bump" && !toVersion) toVersion = m[1];
  }

  // ----- stage nodes -----
  const stageState = new Map<string, { state: NodeState; t: number; detail?: string }>();
  let iterations = 0;
  let escalations = 0;
  for (const s of stageEvents) {
    if (s.name === "escalate") {
      escalations += 1;
      continue;
    }
    if (s.name === "fix" && s.status === "start") iterations += 1;
    const state: NodeState = s.status === "start" ? "active" : s.status === "done" ? "done" : "failed";
    stageState.set(NODE_OF[s.name] ?? s.name, { state, t: s.t, detail: s.detail });
  }

  const status: ViewStatus = result ? result.status : events.length ? "running" : "pending";
  const terminalBad = result != null && (result.status === "failed" || result.status === "error");

  const fixDone = stageState.get("fix")?.state === "done";
  const nodes: StageNode[] = PIPELINE.map((key) => {
    let state: NodeState = "pending";
    let t: number | null = null;
    const s = stageState.get(key);
    if (s) {
      state = s.state;
      t = s.t;
    }
    if (key === "verify") {
      if (verify) {
        state = verify.passed ? "done" : "failed";
        t = verify.t;
      } else if (fixDone && !result) state = "active";
    }
    if (key === "pr") {
      if (result?.summary) {
        state = "done";
        t = result.t;
      } else if ((verify?.passed || writeStarted) && !result) state = "active";
    }
    if (result && state === "active") state = terminalBad || result.status === "partial" ? "failed" : "done";
    return { key, label: STEP_LABEL[key], state, note: null, t };
  });

  // Notes under each node, short and factual.
  const testsBy = (label: string) => [...tests].reverse().find((p) => p.label === label);
  const note = (key: PipelineStep, text: string | null) => {
    const n = nodes.find((x) => x.key === key);
    if (n && text) n.note = text;
  };
  if (project) note("prepare", `python ${project.python}`);
  const base = testsBy("baseline");
  if (base) note("baseline", `${base.passed}/${base.total} pass`);
  const bumped = testsBy("after bump");
  if (bumped) note("bump", bumped.state === "import-error" ? "import error" : `${bumped.passed}/${bumped.total} pass`);
  else if (toVersion && stageState.get("bump")) note("bump", `→ ${toVersion}`);
  if (rulesCount != null || sources.length) note("research", `${rulesCount ?? "…"} rules · ${sources.length} src`);
  const lastPlan = plans[plans.length - 1];
  if (lastPlan) note("plan", `${lastPlan.steps.length} steps`);
  if (iterations || stageState.has("fix")) {
    const lastFix = testsBy("fix");
    note("fix", `${iterations ? `iter ${iterations}` : "migrate"}${lastFix ? ` · ${lastFix.passed}/${lastFix.total}` : ""}`);
  }
  if (verify) note("verify", `${verify.checks.filter((c) => c.ok).length}/${verify.checks.length} checks`);
  if (result?.summary) note("pr", "written");
  else if (nodes[7].state === "active") note("pr", "writing…");

  // ----- models: always show the full lineup, in routing order -----
  const models: ModelRow[] = MODELS.map(
    (info) =>
      modelMap.get(info.key) ?? { info, calls: 0, tokensIn: 0, tokensOut: 0, usd: 0, latency: 0, roles: [], thinking: false, lastSeq: null },
  );
  for (const [k, row] of modelMap) if (k.startsWith("x:")) models.push(row);

  return {
    run, project, status, stages: nodes, iterations, escalations, fromVersion, toVersion,
    tests, meter, baselineTotal, models, llmCalls,
    usd: result?.usd ?? usd, tokensIn, tokensOut,
    sources, rulesCount, tavilyCredits, tavilyOps, researchCached,
    plans, feed, patches, pins: result?.pin_changes?.length ? result.pin_changes : pins,
    verify, result, lastT,
  };
}
