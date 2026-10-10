import { EVENT_TYPES } from "./types";
import type { CaseInfo, Health, ReplayMeta, RunEvent, Scoreboard } from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function detailOf(res: Response): Promise<string> {
  try {
    const body: unknown = await res.json();
    if (body && typeof body === "object" && "detail" in body) {
      const d = (body as { detail: unknown }).detail;
      if (typeof d === "string") return d;
      return JSON.stringify(d);
    }
  } catch {
    /* not JSON */
  }
  return res.statusText || `HTTP ${res.status}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, "Can't reach the Greenlight server.");
  }
  if (!res.ok) throw new ApiError(res.status, await detailOf(res));
  return (await res.json()) as T;
}

/** Keep only well-formed events of known types, ordered by seq. */
export function normalizeEvents(raw: unknown): RunEvent[] {
  if (!Array.isArray(raw)) return [];
  const out: RunEvent[] = [];
  for (const e of raw) {
    if (isEvent(e)) out.push(e);
  }
  return out.sort((a, b) => a.seq - b.seq);
}

export function isEvent(e: unknown): e is RunEvent {
  if (!e || typeof e !== "object") return false;
  const o = e as Record<string, unknown>;
  return typeof o.type === "string" && EVENT_TYPES.has(o.type) && typeof o.seq === "number" && typeof o.t === "number";
}

export const api = {
  health: () => request<Health>("/api/health"),
  replays: () => request<ReplayMeta[]>("/api/replays"),
  replay: async (id: string) => normalizeEvents(await request<unknown>(`/api/replays/${encodeURIComponent(id)}`)),
  scoreboard: () => request<Scoreboard>("/api/scoreboard"),
  cases: () => request<CaseInfo[]>("/api/cases"),
  startRun: (body: { case: string; code: string }) =>
    request<{ run_id: string }>("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  streamUrl: (runId: string) => `/api/runs/${encodeURIComponent(runId)}/stream`,
};
