import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { ReplayMeta, RunEvent, Scoreboard } from "../types";
import { deriveRun } from "../run/derive";
import type { RunView } from "../run/derive";
import { fmtDuration, fmtPct, fmtUsd, plural, repoName } from "../format";
import { Icon } from "../components/Icon";
import type { IconName } from "../components/Icon";
import { Empty, ErrorBox, LibVersions, Skeleton, StatusPill } from "../components/ui";

const STEPS: { icon: IconName; title: string; text: string; tag?: string }[] = [
  { icon: "package", title: "Sandbox", text: "Clone the repo into a sandbox and run its tests. Baseline: green." },
  { icon: "arrowUp", title: "Bump", text: "Move the pin to the next major. The tests go red." },
  { icon: "search", title: "Research", text: "Read the official migration guide into a rule sheet with sources.", tag: "Tavily" },
  { icon: "sparkles", title: "Plan", text: "Map every failure to a rule and a file.", tag: "Nemotron 3 Ultra" },
  { icon: "wrench", title: "Fix", text: "Edit with tools until the tests pass again.", tag: "Nemotron 3 Super" },
  { icon: "shield", title: "Verify", text: "No test edits, no skips, pin kept, no compat shims." },
  { icon: "pr", title: "PR", text: "Write the pull request, every change cited.", tag: "Nemotron 3.5 Lightning" },
];

function ReplayCard({ r }: { r: ReplayMeta }) {
  return (
    <Link to={`/replay/${encodeURIComponent(r.id)}`} className={`replay-card rc-${r.status ?? "none"}`}>
      <div className="rc-top">
        <LibVersions lib={r.lib} from={r.from_version} to={r.to_version} toMajor={r.to_major} />
        <StatusPill status={r.status ?? "pending"} size="sm" />
      </div>
      <div className="rc-repo">{repoName(r.source)}</div>
      <div className="rc-headline">{r.headline ?? "Recorded run"}</div>
      <div className="rc-foot mono">
        <span><Icon name="zap" size={12} /> {fmtUsd(r.usd)}</span>
        <span><Icon name="clock" size={12} /> {fmtDuration(r.seconds)}</span>
        <span className="rc-events">{r.events} events</span>
        <span className="rc-go">Watch <Icon name="arrowRight" size={12} /></span>
      </div>
    </Link>
  );
}

function HeroRun({ meta, view }: { meta: ReplayMeta; view: RunView }) {
  const stage = (k: string) => view.stages.find((s) => s.key === k);
  const modelOf = (role: string) => view.models.find((m) => m.roles.includes(role))?.info.short;
  const rows: { k: string; label: string; note: string; tone: "ok" | "err" | "info"; who?: string }[] = [
    { k: "baseline", label: "baseline", note: stage("baseline")?.note ?? "", tone: "ok" },
    { k: "bump", label: "bump", note: stage("bump")?.note ?? "", tone: "err" },
    { k: "research", label: "research", note: stage("research")?.note ?? "", tone: "info", who: "Tavily" },
    { k: "plan", label: "plan", note: stage("plan")?.note ?? "", tone: "info", who: modelOf("plan") },
    ...(stage("migrate")?.state === "done" || stage("migrate")?.state === "failed"
      ? [{ k: "migrate", label: "migrate", note: stage("migrate")?.note ?? "", tone: "info" as const, who: modelOf("edit") }]
      : []),
    { k: "fix", label: "fix", note: stage("fix")?.state === "skipped" ? "not needed" : stage("fix")?.note ?? "", tone: view.result?.status === "green" ? "ok" : "err", who: modelOf("edit") },
    { k: "verify", label: "verify", note: stage("verify")?.note ?? "", tone: view.verify?.passed ? "ok" : "err" },
    { k: "pr", label: "pull request", note: stage("pr")?.note ?? "", tone: "ok", who: modelOf("write") },
  ];
  return (
    <Link to={`/replay/${encodeURIComponent(meta.id)}`} className="hero-run" aria-label="Watch this replay">
      <div className="hr-chrome">
        <span className="hr-dots"><i /><i /><i /></span>
        <span className="hr-title mono">greenlight upgrade {view.run?.lib ?? meta.lib} --to {view.run?.to_major ?? meta.to_major}</span>
      </div>
      <div className="hr-body mono">
        <div className="hr-repo">
          <span className="muted-2">repo</span> {repoName(meta.source)}
        </div>
        {rows.map((r, i) => (
          <div key={r.k} className={`hr-row hr-${r.tone}`} style={{ animationDelay: `${0.25 + i * 0.32}s` }}>
            <span className="hr-mark">{r.tone === "ok" ? "✓" : r.tone === "err" ? "✗" : "›"}</span>
            <span className="hr-label">{r.label}</span>
            <span className="hr-note">{r.note}</span>
            {r.who && <span className="hr-who">{r.who}</span>}
          </div>
        ))}
        {view.result && (
          <div className={`hr-result hr-res-${view.result.status}`} style={{ animationDelay: `${0.25 + rows.length * 0.32}s` }}>
            {view.result.status.toUpperCase()} · {fmtUsd(view.result.usd)} · {fmtDuration(view.result.seconds)}
          </div>
        )}
      </div>
    </Link>
  );
}

export function Home() {
  const [replays, setReplays] = useState<ReplayMeta[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [board, setBoard] = useState<Scoreboard | null>(null);
  const [heroEvents, setHeroEvents] = useState<RunEvent[] | null>(null);

  useEffect(() => {
    document.title = "Greenlight · breaking upgrades, proven by your tests";
    api.replays().then(setReplays).catch((e: unknown) => setErr(e instanceof Error ? e.message : String(e)));
    api.scoreboard().then(setBoard).catch(() => setBoard(null));
  }, []);

  const featured = useMemo(() => {
    if (!replays?.length) return null;
    return replays.find((r) => r.status === "green") ?? replays[0];
  }, [replays]);

  useEffect(() => {
    if (!featured) return;
    api.replay(featured.id).then(setHeroEvents).catch(() => setHeroEvents(null));
  }, [featured]);

  const heroView = useMemo(() => (heroEvents ? deriveRun(heroEvents) : null), [heroEvents]);
  const hasBoard = board != null && board.cases > 0 && (board.green ?? 0) + (board.partial ?? 0) + (board.failed ?? 0) > 0;

  return (
    <div className="home">
      <section className="hero">
        <div className="hero-bg" aria-hidden="true" />
        <div className="container hero-inner">
          <div className="hero-copy">
            <div className="eyebrow">
              <span className="eyebrow-dot" /> Autonomous major-version upgrades
            </div>
            <h1 className="hero-title">Greenlight</h1>
            <p className="hero-tagline">
              The breaking upgrades Dependabot can't do. Read the migration guide, fix the code,{" "}
              <span className="accent">prove it with your tests.</span>
            </p>
            <div className="hero-libs mono">
              {["pydantic 1→2", "numpy 1→2", "pandas 1→2", "SQLAlchemy 1.4→2"].map((l) => (
                <span key={l} className="lib-chip">{l}</span>
              ))}
            </div>
            <div className="hero-ctas">
              {featured ? (
                <Link to={`/replay/${encodeURIComponent(featured.id)}`} className="btn btn-primary">
                  <Icon name="play" size={14} /> Watch a replay
                </Link>
              ) : (
                <a href="#replays" className="btn btn-primary"><Icon name="play" size={14} /> Watch a replay</a>
              )}
              <Link to="/try" className="btn btn-ghost">Try it live <Icon name="arrowRight" size={14} /></Link>
            </div>
            <div className="hero-sub">
              <span><b>NVIDIA Nemotron</b> on <b>Nebius Token Factory</b></span>
              <span className="sep">·</span>
              <span>Tavily research</span>
              <span className="sep">·</span>
              <span>sandboxed tests</span>
            </div>
          </div>
          <div className="hero-visual">
            {featured && heroView ? (
              <HeroRun meta={featured} view={heroView} />
            ) : (
              <div className="hero-run is-loading">
                <div className="hr-chrome"><span className="hr-dots"><i /><i /><i /></span></div>
                <div className="hr-body">
                  {[80, 64, 72, 58, 76, 62, 70].map((w, i) => <Skeleton key={i} w={`${w}%`} h={12} />)}
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {hasBoard && board && (
        <section className="container teaser">
          <div className="teaser-card">
            <div className="teaser-lead">
              <Icon name="trophy" size={18} />
              <div>
                <div className="teaser-title">Eval scoreboard</div>
                <div className="teaser-sub">{plural(board.cases, "real repo")} stuck on an old major{board.tag ? ` · ${board.tag}` : ""}</div>
              </div>
            </div>
            <div className="teaser-stats">
              <div className="ts"><span className="ts-val mono accent">{fmtPct(board.green_rate)}</span><span className="ts-lab">green rate</span></div>
              <div className="ts"><span className="ts-val mono">{fmtUsd(board.median_usd_green)}</span><span className="ts-lab">median cost</span></div>
              <div className="ts"><span className="ts-val mono">{fmtDuration(board.median_seconds_green)}</span><span className="ts-lab">median time</span></div>
            </div>
            <Link to="/scoreboard" className="btn btn-ghost btn-sm">Full scoreboard <Icon name="arrowRight" size={13} /></Link>
          </div>
        </section>
      )}

      <section className="container section" id="replays">
        <div className="section-head">
          <div>
            <h2 className="section-title">Recorded runs</h2>
            <p className="section-sub">Real runs, replayed event by event. Free to watch, no tokens spent.</p>
          </div>
          {replays && <span className="mono muted-2">{replays.length} {replays.length === 1 ? "replay" : "replays"}</span>}
        </div>
        {err ? (
          <ErrorBox title="Couldn't load replays">{err}</ErrorBox>
        ) : replays == null ? (
          <div className="replay-grid">
            {[0, 1, 2].map((i) => (
              <div key={i} className="replay-card is-loading">
                <Skeleton w="60%" h={16} />
                <Skeleton w="40%" h={12} />
                <Skeleton w="90%" h={12} />
              </div>
            ))}
          </div>
        ) : replays.length === 0 ? (
          <Empty icon="play" title="No replays recorded yet">Record a run with the CLI and drop the .jsonl into replays/.</Empty>
        ) : (
          <div className="replay-grid">
            {replays.map((r) => <ReplayCard key={r.id} r={r} />)}
          </div>
        )}
      </section>

      <section className="container section">
        <div className="section-head">
          <div>
            <h2 className="section-title">How it works</h2>
            <p className="section-sub">Seven steps from a red build to a reviewed pull request.</p>
          </div>
        </div>
        <ol className="how">
          {STEPS.map((s, i) => (
            <li key={s.title} className="how-step">
              <div className="how-icon"><Icon name={s.icon} size={18} /></div>
              <div className="how-num mono">{String(i + 1).padStart(2, "0")}</div>
              <div className="how-title">{s.title}</div>
              <div className="how-text">{s.text}</div>
              {s.tag && <div className="how-tag mono">{s.tag}</div>}
            </li>
          ))}
        </ol>
        <div className="how-foot">
          <Icon name="lock" size={13} /> A hard budget guard prices every model call before it runs.
        </div>
      </section>
    </div>
  );
}
