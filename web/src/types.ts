// Event and API shapes for Greenlight. Mirrors greenlight/events.py emitters and server/app.py.
// Every run event has seq, t (seconds since start) and type.

export type RunStatus = "green" | "partial" | "failed" | "error" | "noop";
export type StageName = "prepare" | "baseline" | "bump" | "research" | "plan" | "migrate" | "fix" | "escalate" | (string & {});
export type StageStatus = "start" | "done" | "fail";
export type LlmRole = "plan" | "escalate" | "edit" | "triage" | "digest" | "write";

interface EventBase {
  seq: number;
  t: number;
}

export interface TestCounts {
  passed: number;
  failed: number;
  skipped: number;
  total: number;
  collection_error: boolean;
}

export interface RunStartEvent extends EventBase {
  type: "run";
  run_id: string;
  source: string;
  ref: string | null;
  lib: string;
  to_major: number;
  spec?: string;
  executor?: string;
  model_override?: string | null;
  use_research?: boolean;
}

export interface StageEvent extends EventBase {
  type: "stage";
  name: StageName;
  status: StageStatus;
  detail?: string;
}

export interface LogEvent extends EventBase {
  type: "log";
  msg: string;
  level: string;
}

export interface ProjectEvent extends EventBase {
  type: "project";
  manifests: string[];
  python: string;
  test_cmd: string;
}

export interface TestsEvent extends EventBase, TestCounts {
  type: "tests";
  label: string; // baseline | after bump | fix | selected
  summary: string;
  kept?: number;
  of?: number;
}

export interface PinChange {
  file: string;
  before: string;
  after: string;
}

export interface PinsEvent extends EventBase {
  type: "pins";
  changes: PinChange[];
}

export interface SourceEvent extends EventBase {
  type: "source";
  url: string;
  title: string;
  cached?: boolean;
  score?: number | null;
  via?: string;
  query?: string;
}

export interface TavilyEvent extends EventBase {
  type: "tavily";
  op: "search" | "extract";
  query?: string;
  urls?: string[];
  domains?: string[];
  credits: number;
  n?: number;
  ok?: number;
  failed?: number;
}

export interface RulesEvent extends EventBase {
  type: "rules";
  count: number;
  sources: unknown[];
  lib?: string;
  dropped_ungrounded?: number;
}

export interface LlmEvent extends EventBase {
  type: "llm";
  role: LlmRole;
  model: string;
  model_label: string;
  thinking: boolean;
  tokens_in: number;
  tokens_out: number;
  usd: number;
  latency_s: number;
  ok?: boolean;
  note?: string;
}

export interface PlanStep {
  file: string;
  change: string;
  rules: string[];
  why: string;
}

export interface PlanEvent extends EventBase {
  type: "plan";
  diagnosis: string;
  dependency_changes: string[];
  steps: PlanStep[];
  risks: string[];
  escalation: boolean;
}

export interface ToolEvent extends EventBase {
  type: "tool";
  name: string;
  brief: string;
  result_brief: string;
}

export interface PatchEvent extends EventBase {
  type: "patch";
  path: string;
  rule: string;
  search?: string;
  replace?: string;
  rewrite?: boolean;
  diff?: string;
  added: number;
  removed: number;
}

export interface VerifyCheck {
  name: string;
  ok: boolean;
  detail: string;
  severity: "error" | "warn" | string;
}

export interface VerifyEvent extends EventBase {
  type: "verify";
  passed: boolean;
  checks: VerifyCheck[];
}

export interface ResultEvent extends EventBase {
  type: "result";
  status: RunStatus;
  headline: string;
  run_id?: string;
  lib?: string;
  from_version?: string | null;
  to_version?: string | null;
  baseline?: TestCounts | null;
  final?: TestCounts | null;
  diff?: string;
  summary?: string;
  usd?: number;
  seconds?: number;
  iterations?: number;
  escalations?: number;
  pin_changes?: PinChange[];
  verify?: { passed: boolean; checks: VerifyCheck[] } | null;
}

export type RunEvent =
  | RunStartEvent
  | StageEvent
  | LogEvent
  | ProjectEvent
  | TestsEvent
  | PinsEvent
  | SourceEvent
  | TavilyEvent
  | RulesEvent
  | LlmEvent
  | PlanEvent
  | ToolEvent
  | PatchEvent
  | VerifyEvent
  | ResultEvent;

export type RunEventType = RunEvent["type"];

export const EVENT_TYPES: ReadonlySet<string> = new Set<RunEventType>([
  "run", "stage", "log", "project", "tests", "pins", "source", "tavily",
  "rules", "llm", "plan", "tool", "patch", "verify", "result",
]);

// ---------------- API ----------------

export interface Health {
  ok: boolean;
  live: boolean;
  executor: string;
  spent_usd: number;
  replays: number;
}

export interface ReplayMeta {
  id: string;
  lib: string | null;
  to_major: number | null;
  source: string | null;
  ref: string | null;
  status: RunStatus | null;
  headline: string | null;
  from_version: string | null;
  to_version: string | null;
  usd: number | null;
  seconds: number | null;
  events: number;
}

export interface ScoreRow {
  case: string;
  lib: string;
  status: string;
  headline: string;
  usd: number;
  seconds: number;
  iterations: number;
  escalations: number;
  from_version: string | null;
  to_version: string | null;
  baseline: Partial<TestCounts> | null;
  final: Partial<TestCounts> | null;
}

export interface Scoreboard {
  tag?: string;
  cases: number;
  green?: number;
  partial?: number;
  failed?: number;
  errors?: number;
  green_rate?: number;
  median_usd_green?: number | null;
  median_seconds_green?: number | null;
  total_usd?: number;
  by_role_usd?: Record<string, number>;
  rows: ScoreRow[];
}

export interface CaseInfo {
  id: string;
  repo: string;
  sha: string | null;
  lib: string;
  to: number;
}
