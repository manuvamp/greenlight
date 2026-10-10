export function fmtUsd(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  if (v === 0) return "$0.00";
  if (v < 0.01) return `$${v.toFixed(4)}`;
  if (v < 0.1) return `$${v.toFixed(3)}`;
  return `$${v.toFixed(2)}`;
}

/** 151.3 -> "2m31s", 7.9 -> "7.9s", 42 -> "42s" */
export function fmtDuration(s: number | null | undefined): string {
  if (s == null || !Number.isFinite(s)) return "—";
  if (s < 10) return `${s.toFixed(1)}s`;
  if (s < 60) return `${Math.round(s)}s`;
  const total = Math.round(s);
  const m = Math.floor(total / 60);
  const sec = total % 60;
  if (m >= 60) return `${Math.floor(m / 60)}h${String(m % 60).padStart(2, "0")}m`;
  return `${m}m${String(sec).padStart(2, "0")}s`;
}

/** Playback clock: 151.3 -> "2:31" */
export function fmtClock(s: number): string {
  const total = Math.max(0, Math.floor(s));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export function fmtTokens(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(n < 10_000 ? 1 : 0)}k`;
  return `${(n / 1_000_000).toFixed(2)}M`;
}

export function fmtPct(v: number | null | undefined, digits = 0): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

/** "https://github.com/owner/repo.git" -> "owner/repo"; "examples/pydantic-v1-shop" -> "pydantic-v1-shop" */
export function repoName(source: string | null | undefined): string {
  if (!source) return "unknown repo";
  const s = source.replace(/\.git$/, "").replace(/[\\/]+$/, "");
  const gh = s.match(/github\.com[/:]([^/]+\/[^/]+)/i);
  if (gh) return gh[1];
  const parts = s.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] ?? s;
}

export function repoUrl(source: string | null | undefined): string | null {
  if (!source) return null;
  return /^https?:\/\//.test(source) ? source.replace(/\.git$/, "") : null;
}

export function domainOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function shortSha(ref: string | null | undefined): string | null {
  if (!ref) return null;
  return /^[0-9a-f]{7,40}$/i.test(ref) ? ref.slice(0, 7) : ref;
}

export function plural(n: number, word: string, pluralWord = `${word}s`): string {
  return `${n} ${n === 1 ? word : pluralWord}`;
}
