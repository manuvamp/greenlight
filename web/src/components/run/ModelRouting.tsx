import { memo } from "react";
import type { ModelRow } from "../../run/derive";
import { fmtTokens, fmtUsd } from "../../format";
import { ROLE_LABEL } from "../../models";
import { Panel } from "../ui";

export const ModelRouting = memo(function ModelRouting({
  models, usd, calls, tokensIn, tokensOut, activeSeq, running,
}: {
  models: ModelRow[];
  usd: number;
  calls: number;
  tokensIn: number;
  tokensOut: number;
  activeSeq: number | null;
  running: boolean;
}) {
  const totalUsd = models.reduce((a, m) => a + m.usd, 0);
  return (
    <Panel
      title="Model routing"
      icon="route"
      className="models-panel"
      aside={<span className="mono muted-2">Nebius Token Factory</span>}
    >
      <div className="models-totals">
        <div className="mt">
          <span className="mt-val mono">{fmtUsd(usd)}</span>
          <span className="mt-lab">spent</span>
        </div>
        <div className="mt">
          <span className="mt-val mono">{calls}</span>
          <span className="mt-lab">calls</span>
        </div>
        <div className="mt">
          <span className="mt-val mono">{fmtTokens(tokensIn)}</span>
          <span className="mt-lab">tokens in</span>
        </div>
        <div className="mt">
          <span className="mt-val mono">{fmtTokens(tokensOut)}</span>
          <span className="mt-lab">tokens out</span>
        </div>
      </div>

      <div className="share-stack" aria-label="share of cost by model">
        {totalUsd > 0 ? (
          models
            .filter((m) => m.usd > 0)
            .map((m) => (
              <span
                key={m.info.label}
                className="share-seg"
                style={{ width: `${(m.usd / totalUsd) * 100}%`, background: m.info.color }}
                title={`${m.info.label}: ${fmtUsd(m.usd)}`}
              />
            ))
        ) : (
          <span className="share-seg share-empty" style={{ width: "100%" }} />
        )}
      </div>

      <div className="model-rows">
        {models.map((m) => {
          const share = totalUsd > 0 ? m.usd / totalUsd : 0;
          const idle = m.calls === 0;
          const hot = running && activeSeq != null && m.lastSeq === activeSeq;
          return (
            <div key={m.info.label} className={`model-row${idle ? " is-idle" : ""}${hot ? " is-hot" : ""}`} style={{ ["--mc" as string]: m.info.color }}>
              <div className="mr-id">
                <span className="mr-swatch" />
                <div className="mr-names">
                  <div className="mr-name">
                    {m.info.label}
                    {m.thinking && <span className="mr-think" title="reasoning mode on">thinking</span>}
                  </div>
                  <div className="mr-roles">
                    {idle ? (
                      <span className="mr-standby">standby · {m.info.job.toLowerCase()}</span>
                    ) : (
                      m.roles.map((r) => (
                        <span key={r} className="role-chip">{ROLE_LABEL[r] ?? r}</span>
                      ))
                    )}
                  </div>
                </div>
              </div>
              <div className="mr-num mono">
                <span className="mr-calls">{m.calls}</span>
                <span className="mr-unit">calls</span>
              </div>
              <div className="mr-num mono mr-tok">
                <span>{fmtTokens(m.tokensIn)}<span className="mr-arrow">→</span>{fmtTokens(m.tokensOut)}</span>
                <span className="mr-unit">tokens</span>
              </div>
              <div className="mr-cost">
                <div className="mr-cost-top mono">
                  <span>{fmtUsd(m.usd)}</span>
                  <span className="mr-pct">{idle ? "" : `${Math.round(share * 100)}%`}</span>
                </div>
                <div className="mr-bar">
                  <span className="mr-bar-fill" style={{ width: `${share * 100}%` }} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
});
