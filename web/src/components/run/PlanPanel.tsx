import { memo, useEffect, useState } from "react";
import type { PlanEvent } from "../../types";
import { Icon } from "../Icon";
import { Empty, Panel } from "../ui";

export const PlanPanel = memo(function PlanPanel({ plans, active }: { plans: PlanEvent[]; active: boolean }) {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    setIdx(Math.max(0, plans.length - 1));
  }, [plans.length]);
  const plan = plans[idx];

  return (
    <Panel
      title="Plan"
      icon="sparkles"
      className="plan-panel"
      aside={
        plans.length > 1 ? (
          <div className="seg seg-sm">
            {plans.map((p, i) => (
              <button key={p.seq} className={`seg-btn${i === idx ? " is-on" : ""}`} onClick={() => setIdx(i)}>
                {p.escalation ? `Re-plan ${i}` : "Initial"}
              </button>
            ))}
          </div>
        ) : (
          <span className="mono muted-2">Nemotron 3 Ultra</span>
        )
      }
    >
      {!plan ? (
        active ? (
          <div className="plan-loading">
            <div className="thinking"><span /><span /><span /></div>
            <span>Nemotron 3 Ultra is reading the failures and the rule sheet…</span>
          </div>
        ) : (
          <Empty icon="sparkles" title="No plan yet">The planner writes a step-by-step migration plan from the rule sheet.</Empty>
        )
      ) : (
        <div className="plan">
          {plan.escalation && (
            <div className="plan-esc"><Icon name="zap" size={13} /> Escalation re-plan</div>
          )}
          <p className="plan-diag">{plan.diagnosis}</p>
          {plan.dependency_changes.length > 0 && (
            <div className="plan-deps">
              {plan.dependency_changes.map((d) => (
                <span key={d} className="dep-chip mono"><Icon name="package" size={12} /> {d}</span>
              ))}
            </div>
          )}
          <ol className="plan-steps">
            {plan.steps.map((s, i) => (
              <li key={i} className="plan-step">
                <span className="ps-num mono">{String(i + 1).padStart(2, "0")}</span>
                <div className="ps-main">
                  <div className="ps-head">
                    <span className="ps-file mono">{s.file}</span>
                    <span className="ps-rules">
                      {s.rules.map((r) => (
                        <span key={r} className="rule-chip mono">{r}</span>
                      ))}
                    </span>
                  </div>
                  <div className="ps-change">{s.change}</div>
                  {s.why && <div className="ps-why">{s.why}</div>}
                </div>
              </li>
            ))}
          </ol>
          {plan.risks.length > 0 && (
            <div className="plan-risks">
              <div className="plan-risks-title"><Icon name="alert" size={13} /> Risks</div>
              <ul>
                {plan.risks.map((r) => <li key={r}>{r}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
});
