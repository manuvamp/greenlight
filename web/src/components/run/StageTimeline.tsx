import { memo } from "react";
import type { PipelineStep, StageNode } from "../../run/derive";
import { Icon } from "../Icon";
import type { IconName } from "../Icon";

const STEP_ICON: Record<PipelineStep, IconName> = {
  prepare: "package",
  baseline: "flask",
  bump: "arrowUp",
  research: "search",
  plan: "sparkles",
  migrate: "layers",
  fix: "wrench",
  verify: "shield",
  pr: "pr",
};

export const StageTimeline = memo(function StageTimeline({
  stages, escalations, iterations,
}: { stages: StageNode[]; escalations: number; iterations: number }) {
  const lastReached = stages.reduce((acc, s, i) => (s.state !== "pending" ? i : acc), -1);
  void iterations;
  return (
    <div className="timeline" role="list" aria-label="pipeline stages">
      <div className="timeline-track">
        <div
          className="timeline-fill"
          style={{ width: `${lastReached <= 0 ? 0 : (lastReached / (stages.length - 1)) * 100}%` }}
        />
      </div>
      {stages.map((s) => (
        <div key={s.key} className={`tl-node tl-${s.state}`} role="listitem" aria-label={`${s.label}: ${s.state}`}>
          <div className="tl-dot">
            {s.state === "done" ? (
              <Icon name="check" size={15} stroke={2.6} />
            ) : s.state === "skipped" ? (
              <Icon name="minus" size={15} stroke={2.2} />
            ) : s.state === "failed" ? (
              <Icon name="x" size={15} stroke={2.6} />
            ) : (
              <Icon name={STEP_ICON[s.key]} size={15} />
            )}
          </div>
          <div className="tl-label">
            {s.label}
            {s.key === "fix" && escalations > 0 && (
              <span className="tl-esc" title={`${escalations} escalation${escalations > 1 ? "s" : ""}`}>
                <Icon name="zap" size={10} stroke={2.4} /> {escalations}
              </span>
            )}
          </div>
          <div className="tl-note mono">
            {s.note ?? (s.state === "active" ? "running…" : s.state === "skipped" ? "skipped" : " ")}
          </div>
        </div>
      ))}
    </div>
  );
});
