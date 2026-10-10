import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, api } from "../api";
import type { CaseInfo, Health } from "../types";
import { repoName, shortSha } from "../format";
import { Icon } from "../components/Icon";
import { Empty, ErrorBox, Skeleton } from "../components/ui";

const EXAMPLE: CaseInfo = { id: "example", repo: "examples/pydantic-v1-shop", sha: null, lib: "pydantic", to: 2 };

function errorTitle(status: number): string {
  switch (status) {
    case 403: return "Live runs are off on this deployment";
    case 401: return "That access code didn't work";
    case 409: return "A live run is already in progress";
    case 429: return "Today's live-run limit is reached";
    case 404: return "Unknown case";
    case 0: return "Server unreachable";
    default: return "Couldn't start the run";
  }
}

export function TryPage({ health }: { health: Health | null }) {
  const navigate = useNavigate();
  const [cases, setCases] = useState<CaseInfo[] | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<string>("example");
  const [code, setCode] = useState("");
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<{ status: number; detail: string } | null>(null);

  useEffect(() => {
    document.title = "Try it live · Greenlight";
    api.cases().then(setCases).catch((e: unknown) => setLoadErr(e instanceof Error ? e.message : String(e)));
  }, []);

  const all = useMemo(() => [EXAMPLE, ...(cases ?? [])], [cases]);
  const groups = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const m = new Map<string, CaseInfo[]>();
    for (const c of all) {
      if (q && !`${c.id} ${c.repo} ${c.lib}`.toLowerCase().includes(q)) continue;
      const k = `${c.lib} → ${c.to}`;
      m.set(k, [...(m.get(k) ?? []), c]);
    }
    return [...m.entries()];
  }, [all, filter]);
  const chosen = all.find((c) => c.id === selected);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setBusy(true);
    setErr(null);
    try {
      const { run_id } = await api.startRun({ case: selected, code });
      navigate(`/live/${encodeURIComponent(run_id)}`);
    } catch (ex: unknown) {
      if (ex instanceof ApiError) setErr({ status: ex.status, detail: ex.message });
      else setErr({ status: 0, detail: ex instanceof Error ? ex.message : String(ex) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container page try-page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Try it live</h1>
          <p className="page-sub">
            Pick a repository from the eval set and watch Greenlight upgrade it in real time. Live runs spend real tokens,
            so they need an access code and run one at a time.
          </p>
        </div>
      </div>

      {health && !health.live && (
        <div className="notice">
          <Icon name="info" size={16} />
          <span>
            Live runs are switched off on this deployment. You can still submit to see the response, or{" "}
            <Link to="/">watch a recorded replay</Link>: same agent, same events, zero cost.
          </span>
        </div>
      )}

      <form className="try-layout" onSubmit={submit}>
        <section className="panel try-cases">
          <header className="panel-head">
            <h2 className="panel-title"><Icon name="layers" size={15} /> Choose a case</h2>
            <input
              className="input input-sm"
              placeholder="Filter…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              aria-label="filter cases"
            />
          </header>
          <div className="panel-body">
            {loadErr && <ErrorBox title="Couldn't load the eval cases">{loadErr}</ErrorBox>}
            {cases == null && !loadErr ? (
              <div className="case-grid">{[0, 1, 2, 3].map((i) => <div key={i} className="case-opt"><Skeleton w="60%" /><Skeleton w="40%" h={10} /></div>)}</div>
            ) : groups.length === 0 ? (
              <Empty icon="search" title="No matching cases" />
            ) : (
              groups.map(([g, list]) => (
                <div key={g} className="case-group">
                  <div className="case-group-title mono">{g}</div>
                  <div className="case-grid">
                    {list.map((c) => (
                      <label key={c.id} className={`case-opt${selected === c.id ? " is-on" : ""}`}>
                        <input type="radio" name="case" value={c.id} checked={selected === c.id} onChange={() => setSelected(c.id)} />
                        <span className="case-radio" />
                        <span className="case-opt-main">
                          <span className="case-opt-name">{c.id === "example" ? "Bundled example" : c.id}</span>
                          <span className="case-opt-repo mono">{repoName(c.repo)}{c.sha ? ` @ ${shortSha(c.sha)}` : ""}</span>
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        <aside className="panel try-side">
          <header className="panel-head">
            <h2 className="panel-title"><Icon name="rocket" size={15} /> Start run</h2>
          </header>
          <div className="panel-body try-form">
            <div className="field">
              <span className="field-lab">Case</span>
              <div className="field-static">
                {chosen ? (
                  <>
                    <b>{chosen.id === "example" ? "Bundled example" : chosen.id}</b>
                    <span className="mono muted-2">{chosen.lib} → {chosen.to}.x</span>
                  </>
                ) : (
                  <span className="muted-2">none selected</span>
                )}
              </div>
            </div>
            <label className="field">
              <span className="field-lab">Access code</span>
              <input
                className="input"
                type="password"
                autoComplete="off"
                placeholder="••••••••"
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </label>
            <button className="btn btn-primary btn-block" type="submit" disabled={busy || !selected}>
              {busy ? <span className="spinner" /> : <Icon name="play" size={14} />}
              {busy ? "Starting…" : "Run upgrade"}
            </button>
            <ul className="try-facts">
              <li><Icon name="lock" size={13} /> Sandboxed: the repo runs in an isolated {health?.executor ?? "container"}.</li>
              <li><Icon name="zap" size={13} /> Budget guard caps spend per run.</li>
              <li><Icon name="clock" size={13} /> Typical run: 2 to 6 minutes.</li>
            </ul>
            {err && (
              <ErrorBox
                title={errorTitle(err.status)}
                action={
                  err.status === 403 || err.status === 429 || err.status === 409 ? (
                    <Link to="/" className="btn btn-ghost btn-sm">Watch a replay instead <Icon name="arrowRight" size={13} /></Link>
                  ) : undefined
                }
              >
                {err.detail}
              </ErrorBox>
            )}
          </div>
        </aside>
      </form>
    </div>
  );
}
