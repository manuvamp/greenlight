import { memo, useEffect, useRef, useState } from "react";
import type { FeedIcon, FeedItem } from "../../run/derive";
import { fmtClock } from "../../format";
import { Icon } from "../Icon";
import type { IconName } from "../Icon";
import { Panel } from "../ui";

const ICON: Record<FeedIcon, IconName> = {
  stage: "chevronRight",
  read_file: "file",
  apply_patch: "pencil",
  rewrite_file: "fileEdit",
  run_tests: "flask",
  search_docs: "search",
  reinstall: "refresh",
  finish: "flag",
  tool: "wrench",
  tests: "flask",
  log: "terminal",
  llm: "sparkles",
  tavily: "search",
  pins: "pin",
  escalate: "zap",
  verify: "shield",
};

function Row({ item }: { item: FeedItem }) {
  const chips = item.chips ?? [];
  const shown = chips.slice(0, 3);
  const extra = chips.length - shown.length;
  return (
    <li className={`feed-row tone-${item.tone} kind-${item.icon}`}>
      <span className="feed-t mono">{fmtClock(item.t)}</span>
      <span className="feed-icon"><Icon name={ICON[item.icon]} size={13} /></span>
      <div className="feed-main">
        <div className="feed-title">
          <span className={item.icon === "apply_patch" || item.icon === "rewrite_file" || item.icon === "read_file" ? "mono" : ""}>{item.title}</span>
          {item.added != null && (
            <span className="feed-diffstat mono">
              <span className="add">+{item.added}</span>
              <span className="del">−{item.removed ?? 0}</span>
            </span>
          )}
          {shown.map((c) => (
            <span key={c} className="rule-chip mono">{c}</span>
          ))}
          {extra > 0 && <span className="rule-chip rule-more mono">+{extra}</span>}
        </div>
        {item.detail && <div className="feed-detail">{item.detail}</div>}
      </div>
    </li>
  );
}

export const ActivityFeed = memo(function ActivityFeed({ items }: { items: FeedItem[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [stick, setStick] = useState(true);

  useEffect(() => {
    const el = ref.current;
    if (el && stick) el.scrollTop = el.scrollHeight;
  }, [items.length, stick]);

  return (
    <Panel
      title="Activity"
      icon="terminal"
      className="feed-panel"
      bodyClass="feed-body"
      aside={
        <span className="mono muted-2">
          {items.length} events
          {!stick && (
            <button className="link-btn" onClick={() => setStick(true)}>· follow</button>
          )}
        </span>
      }
    >
      <div
        className="feed-scroll"
        ref={ref}
        onScroll={(e) => {
          const el = e.currentTarget;
          const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
          if (atBottom !== stick) setStick(atBottom);
        }}
      >
        {items.length === 0 ? (
          <div className="feed-empty mono">waiting for the sandbox…</div>
        ) : (
          <ul className="feed">
            {items.map((it) => <Row key={it.id} item={it} />)}
          </ul>
        )}
      </div>
    </Panel>
  );
});
