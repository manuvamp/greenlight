import { memo } from "react";
import type { SourceEvent } from "../../types";
import { domainOf } from "../../format";
import { Icon } from "../Icon";
import { Empty, Panel } from "../ui";

export const ResearchPanel = memo(function ResearchPanel({
  sources, rulesCount, credits, ops, cached, active,
}: {
  sources: SourceEvent[];
  rulesCount: number | null;
  credits: number;
  ops: number;
  cached: boolean;
  active: boolean;
}) {
  return (
    <Panel title="Research" icon="book" className="research-panel" aside={<>{cached && <span className="mono muted-2">rule sheet cached</span>}<span className="tavily-badge">Tavily</span></>}>
      <div className="research-stats">
        <div className="rs">
          <span className="rs-val mono">{rulesCount ?? "—"}</span>
          <span className="rs-lab">rules</span>
        </div>
        <div className="rs">
          <span className="rs-val mono">{sources.length}</span>
          <span className="rs-lab">sources</span>
        </div>
        <div className="rs">
          <span className="rs-val mono">{credits}</span>
          <span className="rs-lab">{ops ? `credits · ${ops} calls` : "Tavily credits"}</span>
        </div>
      </div>
      {sources.length === 0 ? (
        active ? (
          <div className="source-list">
            {[0, 1, 2].map((i) => (
              <div className="source-card is-loading" key={i}>
                <span className="skeleton" style={{ width: "70%", height: 12 }} />
                <span className="skeleton" style={{ width: "40%", height: 10 }} />
              </div>
            ))}
          </div>
        ) : (
          <Empty icon="search" title="No sources yet">Tavily finds the official migration guide once the bump breaks the tests.</Empty>
        )
      ) : (
        <div className="source-list">
          {sources.map((s) => (
            <a key={s.url} className="source-card" href={s.url} target="_blank" rel="noreferrer noopener">
              <span className="source-fav mono" aria-hidden="true">{domainOf(s.url).charAt(0).toUpperCase()}</span>
              <div className="source-main">
                <div className="source-title">{s.title || s.url}</div>
                <div className="source-domain mono">
                  {domainOf(s.url)}
                  {s.via === "lookup" && <span className="source-via">· search_docs</span>}
                </div>
              </div>
              <Icon name="external" size={13} className="source-ext" />
            </a>
          ))}
        </div>
      )}
    </Panel>
  );
});
