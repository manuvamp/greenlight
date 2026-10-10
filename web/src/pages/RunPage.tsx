import { useEffect, useMemo, useRef } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { deriveRun } from "../run/derive";
import type { RunView } from "../run/derive";
import { parseSpeed, useRunEvents } from "../run/useRunEvents";
import type { RunSource } from "../run/useRunEvents";
import { fmtDuration, fmtUsd, repoName, repoUrl, shortSha } from "../format";
import { Icon } from "../components/Icon";
import { ErrorBox, LibVersions, StatusPill } from "../components/ui";
import { PlaybackBar } from "../components/run/Playback";
import { StageTimeline } from "../components/run/StageTimeline";
import { TestMeter } from "../components/run/TestMeter";
import { ModelRouting } from "../components/run/ModelRouting";
import { ResearchPanel } from "../components/run/ResearchPanel";
import { PlanPanel } from "../components/run/PlanPanel";
import { ActivityFeed } from "../components/run/ActivityFeed";
import { ChangesPanel } from "../components/run/ChangesPanel";
import { VerifyPanel } from "../components/run/VerifyPanel";
import { PrPanel } from "../components/run/PrPanel";

function FinalBanner({ v }: { v: RunView }) {
  const r = v.result;
  if (!r) return null;
  const fin = r.final;
  const finText = fin
    ? fin.collection_error
      ? "tests fail to import"
      : `${fin.passed}/${v.baselineTotal ?? fin.total} tests pass`
    : null;
  const mark = r.status === "green" ? "✓" : r.status === "partial" ? "◐" : r.status === "noop" ? "•" : "✗";
  const versions = v.fromVersion || v.toVersion ? `${r.lib ?? v.run?.lib ?? ""} ${v.fromVersion ?? "?"} → ${v.toVersion ?? "?"}` : r.headline;
  return (
    <div className={`final-banner fb-${r.status}`} role="status">
      <span className="fb-mark">{mark}</span>
      <span className="fb-status">{r.status.toUpperCase()}</span>
      <span className="fb-text">
        <span className="mono">{versions}</span>
        {finText && <>, {finText}</>}
        {r.status !== "green" && r.headline && <span className="fb-headline"> · {r.headline}</span>}
      </span>
      <span className="fb-stats mono">
        <span>{fmtUsd(r.usd ?? v.usd)}</span>
        <span>{fmtDuration(r.seconds ?? v.lastT)}</span>
        {r.iterations != null && <span>{r.iterations} iter</span>}
        {(r.escalations ?? 0) > 0 && <span className="fb-esc">{r.escalations} escalation{r.escalations === 1 ? "" : "s"}</span>}
      </span>
    </div>
  );
}

export function RunPage({ mode }: { mode: "replay" | "live" }) {
  const params = useParams();
  const [search] = useSearchParams();
  const id = mode === "replay" ? params.id ?? "" : params.runId ?? "";
  const source: RunSource = useMemo(
    () => (mode === "replay" ? { kind: "replay", id } : { kind: "live", runId: id }),
    [mode, id],
  );
  const pb = useRunEvents(source, parseSpeed(search.get("speed")) ?? 8);
  const v = useMemo(() => deriveRun(pb.events), [pb.events]);

  // keyboard: space = play/pause, r = restart
  const pbRef = useRef(pb);
  pbRef.current = pb;
  useEffect(() => {
    if (mode !== "replay") return;
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "BUTTON" || e.metaKey || e.ctrlKey) return;
      if (e.key === " ") {
        e.preventDefault();
        pbRef.current.toggle();
      } else if (e.key === "r" || e.key === "R") pbRef.current.restart();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mode]);

  useEffect(() => {
    const name = v.run ? `${v.run.lib} ${v.fromVersion ?? ""}→${v.toVersion ?? v.run.to_major} · ${repoName(v.run.source)}` : id;
    document.title = `${name} · Greenlight`;
  }, [v.run, v.fromVersion, v.toVersion, id]);

  const lastLlmSeq = useMemo(() => {
    for (let i = pb.events.length - 1; i >= 0; i--) if (pb.events[i].type === "llm") return pb.events[i].seq;
    return null;
  }, [pb.events]);

  if (pb.loadState === "error") {
    return (
      <div className="container page">
        <Link to="/" className="back-link"><Icon name="arrowRight" size={13} className="flip" /> All replays</Link>
        <ErrorBox
          title={mode === "replay" ? "Couldn't load this replay" : "Couldn't follow this live run"}
          action={<Link className="btn btn-ghost" to="/">Browse replays</Link>}
        >
          {pb.error}
        </ErrorBox>
      </div>
    );
  }

  const run = v.run;
  const running = !v.result && pb.events.length > 0;
  const stageActive = (k: string) => v.stages.find((s) => s.key === k)?.state === "active";
  const elapsed = v.result?.seconds != null && pb.ended ? v.result.seconds : pb.clock;
  const url = repoUrl(run?.source);
  const sha = shortSha(run?.ref);

  return (
    <div className="container page run-page">
      <div className="run-top">
        <Link to="/" className="back-link"><Icon name="arrowRight" size={13} className="flip" /> All replays</Link>
        <span className="run-id mono">{mode === "replay" ? `replay · ${id}` : `live · ${id}`}</span>
      </div>

      <header className="run-header">
        <div className="rh-left">
          <div className="rh-title">
            {pb.loadState === "loading" ? (
              <span className="skeleton" style={{ width: 260, height: 30 }} />
            ) : url ? (
              <a href={url} target="_blank" rel="noreferrer noopener" className="rh-repo">{repoName(run?.source)}</a>
            ) : (
              <span className="rh-repo">{repoName(run?.source)}</span>
            )}
            <StatusPill status={pb.loadState === "loading" ? "pending" : v.status} size="lg" />
          </div>
          <div className="rh-sub">
            <LibVersions lib={run?.lib} from={v.fromVersion} to={v.toVersion} toMajor={run?.to_major} />
            {sha && <span className="rh-meta mono"><Icon name="branch" size={13} /> {sha}</span>}
            {v.project && <span className="rh-meta mono">python {v.project.python}</span>}
            {run?.executor && <span className="rh-meta mono">{run.executor} sandbox</span>}
          </div>
        </div>
        <div className="rh-stats">
          <div className="rh-stat">
            <span className="rh-stat-lab"><Icon name="clock" size={13} /> Elapsed</span>
            <span className="rh-stat-val mono">{fmtDuration(elapsed)}</span>
          </div>
          <div className="rh-stat">
            <span className="rh-stat-lab"><Icon name="zap" size={13} /> Cost</span>
            <span className="rh-stat-val mono accent">{fmtUsd(v.usd)}</span>
          </div>
          <div className="rh-stat">
            <span className="rh-stat-lab"><Icon name="sparkles" size={13} /> LLM calls</span>
            <span className="rh-stat-val mono">{v.llmCalls}</span>
          </div>
        </div>
      </header>

      <PlaybackBar pb={pb} />

      <FinalBanner v={v} />

      <StageTimeline stages={v.stages} escalations={v.escalations} iterations={v.iterations} />

      <div className="run-grid">
        <div className="g-meter">
          <TestMeter meter={v.meter} history={v.tests} baselineTotal={v.baselineTotal} />
        </div>
        <div className="g-models">
          <ModelRouting
            models={v.models}
            usd={v.usd}
            calls={v.llmCalls}
            tokensIn={v.tokensIn}
            tokensOut={v.tokensOut}
            activeSeq={lastLlmSeq}
            running={running}
          />
        </div>
        <div className="g-research">
          <ResearchPanel
            sources={v.sources}
            rulesCount={v.rulesCount}
            credits={v.tavilyCredits}
            ops={v.tavilyOps}
            cached={v.researchCached}
            active={stageActive("research")}
          />
        </div>
        <div className="g-feed">
          <ActivityFeed items={v.feed} />
        </div>
        <div className="g-plan">
          <PlanPanel plans={v.plans} active={stageActive("plan")} />
        </div>
        <div className="g-changes">
          <ChangesPanel patches={v.patches} diff={v.result?.diff || null} pins={v.pins} />
        </div>
        <div className="g-verify">
          <VerifyPanel verify={v.verify} active={stageActive("verify")} />
        </div>
        <div className="g-pr">
          <PrPanel
            result={v.result}
            lib={run?.lib ?? null}
            fromVersion={v.fromVersion}
            toVersion={v.toVersion}
            writing={stageActive("pr")}
            branchName={`greenlight/${run?.lib ?? "upgrade"}-${run?.to_major ?? "next"}`}
          />
        </div>
      </div>
    </div>
  );
}
