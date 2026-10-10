import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { ReplayMeta, Scoreboard, ScoreRow, TestCounts } from "../types";
import { fmtDuration, fmtPct, fmtUsd } from "../format";
import { modelFor } from "../models";
import { Icon } from "../components/Icon";
import { Empty, ErrorBox, Panel, Skeleton, StatusPill } from "../components/ui";

function TestsCell({ t, of }: { t: Partial<TestCounts> | null; of?: number }) {
  if (!t || t.total == null) return <span className="muted-2">—</span>;
  const total = of ?? t.total ?? 0;
  const passed = t.collection_error ? 0 : t.passed ?? 0;
  const ratio = total ? passed / total : 0;
  return (
    <span className="tcell" title={t.collection_error ? "collection error" : `${passed} of ${total} pass`}>
      <span className="tcell-bar">
        <span className={`tcell-fill ${ratio >= 1 ? "ok" : ratio > 0 ? "warn" : "err"}`} style={{ width: `${Math.max(ratio * 100, 4)}%` }} />
      </span>
      <span className="mono">{t.collection_error ? "import err" : `${passed}/${total}`}</span>
    </span>
  );
}

function matchReplay(row: ScoreRow, replays: ReplayMeta[]): ReplayMeta | undefined {
  return replays.find((r) => r.id === row.case) ?? replays.find((r) => r.id.startsWith(`${row.case}-`));
}

function RoleChart({ byRole }: { byRole: Record<string, number> }) {
  const items = Object.entries(byRole)
    .map(([k, usd]) => {
      const [role, ...rest] = k.split(":");
      const label = rest.join(":") || role;
      return { role, label, usd, color: modelFor(label)?.color ?? "var(--text-3)" };
    })
    .sort((a, b) => b.usd - a.usd);
  const max = Math.max(...items.map((i) => i.usd), 0.000001);
  const total = items.reduce((a, i) => a + i.usd, 0);
  if (!items.length) return <Empty icon="route" title="No model calls recorded" />;
  return (
    <div className="rolechart">
      {items.map((i) => (
        <div key={`${i.role}:${i.label}`} className="rc-row">
          <div className="rc-lab">
            <span className="rc-role mono">{i.role}</span>
            <span className="rc-model">{i.label}</span>
          </div>
          <div className="rc-track">
            <span className="rc-fill" style={{ width: `${(i.usd / max) * 100}%`, background: i.color }} />
          </div>
          <div className="rc-val mono">
            {fmtUsd(i.usd)} <span className="muted-2">{total ? `${Math.round((i.usd / total) * 100)}%` : ""}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

export function ScoreboardPage() {
  const [board, setBoard] = useState<Scoreboard | null>(null);
  const [replays, setReplays] = useState<ReplayMeta[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Scoreboard · Greenlight";
    api.scoreboard().then(setBoard).catch((e: unknown) => setErr(e instanceof Error ? e.message : String(e)));
    api.replays().then(setReplays).catch(() => setReplays([]));
  }, []);

  const rows = useMemo(() => {
    const order: Record<string, number> = { green: 0, partial: 1, failed: 2, error: 3 };
    return [...(board?.rows ?? [])].sort((a, b) => (order[a.status] ?? 9) - (order[b.status] ?? 9) || a.case.localeCompare(b.case));
  }, [board]);

  return (
    <div className="container page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Scoreboard</h1>
          <p className="page-sub">
            Real public repositories pinned to an old major version, each prechecked: baseline green, bump red.
            {board?.tag && <> Latest eval: <span className="mono">{board.tag}</span>.</>}
          </p>
        </div>
      </div>

      {err ? (
        <ErrorBox title="Couldn't load the scoreboard">{err}</ErrorBox>
      ) : board == null ? (
        <div className="stat-grid">
          {[0, 1, 2, 3].map((i) => <div key={i} className="stat-card"><Skeleton w="50%" h={28} /><Skeleton w="70%" h={12} /></div>)}
        </div>
      ) : board.cases === 0 ? (
        <div className="panel">
          <Empty icon="trophy" title="No eval results yet">
            Run <code className="mono">python evals/run.py</code> to score Greenlight on the eval set. Meanwhile, the{" "}
            <Link to="/">recorded replays</Link> show complete runs.
          </Empty>
        </div>
      ) : (
        <>
          <div className="stat-grid">
            <div className="stat-card stat-hero">
              <span className="stat-val mono accent">{fmtPct(board.green_rate)}</span>
              <span className="stat-lab">green rate</span>
              <div className="outcome-bar">
                {(["green", "partial", "failed", "errors"] as const).map((k) => {
                  const n = board[k] ?? 0;
                  return n ? <span key={k} className={`ob-${k}`} style={{ flex: n }} title={`${k}: ${n}`} /> : null;
                })}
              </div>
              <div className="outcome-legend mono">
                <span><i className="ob-green" />{board.green ?? 0} green</span>
                <span><i className="ob-partial" />{board.partial ?? 0} partial</span>
                <span><i className="ob-failed" />{board.failed ?? 0} failed</span>
                {(board.errors ?? 0) > 0 && <span><i className="ob-errors" />{board.errors} error</span>}
              </div>
            </div>
            <div className="stat-card">
              <span className="stat-val mono">{fmtUsd(board.median_usd_green)}</span>
              <span className="stat-lab">median cost per green upgrade</span>
            </div>
            <div className="stat-card">
              <span className="stat-val mono">{fmtDuration(board.median_seconds_green)}</span>
              <span className="stat-lab">median time per green upgrade</span>
            </div>
            <div className="stat-card">
              <span className="stat-val mono">{fmtUsd(board.total_usd)}</span>
              <span className="stat-lab">total spent · {board.cases} cases</span>
            </div>
          </div>

          <div className="score-layout">
            <Panel title="Cases" icon="listChecks" className="score-table-panel" bodyClass="flush">
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Case</th>
                      <th>Upgrade</th>
                      <th>Status</th>
                      <th>Baseline → final</th>
                      <th className="num">Iter</th>
                      <th className="num">Esc</th>
                      <th className="num">Cost</th>
                      <th className="num">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => {
                      const rp = matchReplay(r, replays);
                      return (
                        <tr key={r.case}>
                          <td>
                            <div className="case-cell">
                              {rp ? (
                                <Link to={`/replay/${encodeURIComponent(rp.id)}`} className="case-link">
                                  {r.case} <Icon name="play" size={10} />
                                </Link>
                              ) : (
                                <span className="case-name">{r.case}</span>
                              )}
                              <span className="case-headline" title={r.headline}>{r.headline}</span>
                            </div>
                          </td>
                          <td className="mono nowrap">
                            {r.lib} <span className="muted-2">{r.from_version || "?"} → {r.to_version || "?"}</span>
                          </td>
                          <td><StatusPill status={r.status} size="sm" /></td>
                          <td>
                            <div className="tests-pair">
                              <TestsCell t={r.baseline} />
                              <Icon name="arrowRight" size={12} className="muted-2" />
                              <TestsCell t={r.final} of={r.baseline?.total} />
                            </div>
                          </td>
                          <td className="num mono">{r.iterations ?? "—"}</td>
                          <td className="num mono">{r.escalations ? <span className="esc-badge">{r.escalations}</span> : "0"}</td>
                          <td className="num mono">{fmtUsd(r.usd)}</td>
                          <td className="num mono">{fmtDuration(r.seconds)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Panel>
            <Panel title="Cost by role and model" icon="route" className="score-chart-panel">
              <RoleChart byRole={board.by_role_usd ?? {}} />
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
