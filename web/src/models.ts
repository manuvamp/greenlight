// The Nemotron lineup Greenlight routes between (mirrors greenlight/models.py).
// Prices are USD per 1M tokens on Nebius Token Factory.

export interface ModelInfo {
  key: "ultra" | "super" | "lightning" | "nano";
  label: string;
  short: string;
  size: string;
  job: string;
  usdIn: number;
  usdOut: number;
  color: string;
  match: RegExp;
}

export const MODELS: ModelInfo[] = [
  {
    key: "ultra", label: "Nemotron 3 Ultra", short: "Ultra", size: "550B · A55B",
    job: "Plans the migration, re-plans on escalation", usdIn: 1.0, usdOut: 3.0,
    color: "var(--m-ultra)", match: /ultra/i,
  },
  {
    key: "super", label: "Nemotron 3 Super", short: "Super", size: "120B · A12B",
    job: "Edits code in a tool loop", usdIn: 0.3, usdOut: 0.9,
    color: "var(--m-super)", match: /super/i,
  },
  {
    key: "lightning", label: "Nemotron 3.5 Lightning", short: "Lightning", size: "fast tier",
    job: "Digests guides, writes the PR", usdIn: 0.06, usdOut: 0.24,
    color: "var(--m-lightning)", match: /lightning/i,
  },
  {
    key: "nano", label: "Nemotron 3 Nano", short: "Nano", size: "30B · A3B",
    job: "Triage of test logs", usdIn: 0.06, usdOut: 0.24,
    color: "var(--m-nano)", match: /nano/i,
  },
];

export function modelFor(labelOrId: string): ModelInfo | undefined {
  return MODELS.find((m) => m.match.test(labelOrId));
}

export const ROLE_LABEL: Record<string, string> = {
  plan: "plan",
  escalate: "escalate",
  edit: "edit",
  triage: "triage",
  digest: "digest",
  write: "write PR",
};
