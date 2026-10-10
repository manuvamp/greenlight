import { memo, useMemo } from "react";
import { Marked } from "marked";
import type { ResultEvent } from "../../types";
import { Icon, Logo } from "../Icon";
import { Panel } from "../ui";

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// LLM-written markdown: render raw HTML as text and only allow http(s)/relative links.
const md = new Marked({
  gfm: true,
  breaks: false,
  renderer: {
    html({ text }) {
      return escapeHtml(text);
    },
    link({ href, title, tokens }) {
      const label = this.parser.parseInline(tokens);
      if (!/^(https?:|#|\/)/i.test(href)) return label;
      const t = title ? ` title="${escapeHtml(title)}"` : "";
      return `<a href="${escapeHtml(href)}"${t} target="_blank" rel="noreferrer noopener">${label}</a>`;
    },
    image({ text }) {
      return escapeHtml(text);
    },
  },
});

export const PrPanel = memo(function PrPanel({
  result, lib, fromVersion, toVersion, writing, branchName,
}: {
  result: ResultEvent | null;
  lib: string | null;
  fromVersion: string | null;
  toVersion: string | null;
  writing: boolean;
  branchName: string;
}) {
  const html = useMemo(() => (result?.summary ? (md.parse(result.summary, { async: false }) as string) : ""), [result?.summary]);
  const title = `Upgrade ${lib ?? "dependency"} ${fromVersion ?? ""} → ${toVersion ?? "next major"}`.replace(/\s+/g, " ");
  const ok = result?.status === "green";

  return (
    <Panel title="Pull request" icon="pr" className="pr-panel" aside={<span className="mono muted-2">Nemotron 3.5 Lightning</span>}>
      <div className="pr-card">
        <div className="pr-head">
          <div className="pr-title">
            {title}
            {result && <span className="pr-num">#1</span>}
          </div>
          <div className="pr-meta">
            <span className={`pr-state ${result ? (ok ? "pr-open" : "pr-draft") : "pr-pending"}`}>
              <Icon name="pr" size={13} />
              {result ? (ok ? "Open" : "Draft") : writing ? "Writing" : "Pending"}
            </span>
            <span className="pr-sub">
              <b>greenlight-bot</b> wants to merge into <code>main</code> from <code>{branchName}</code>
            </span>
          </div>
        </div>
        <div className="pr-comment">
          <div className="pr-avatar"><Logo size={30} /></div>
          <div className="pr-bubble">
            <div className="pr-bubble-head">
              <b>greenlight-bot</b>
              <span className="pr-bot">bot</span>
              <span className="muted-2">commented</span>
            </div>
            <div className="pr-bubble-body">
              {html ? (
                <div className="markdown" dangerouslySetInnerHTML={{ __html: html }} />
              ) : (
                <div className="pr-placeholder">
                  {writing ? (
                    <>
                      <div className="thinking"><span /><span /><span /></div>
                      <span>Nemotron 3.5 Lightning is writing the description…</span>
                    </>
                  ) : result ? (
                    <span>{result.headline}</span>
                  ) : (
                    <span>The PR description is written once verification passes.</span>
                  )}
                  {!result && (
                    <div className="pr-skel">
                      <span className="skeleton" style={{ width: "40%", height: 14 }} />
                      <span className="skeleton" style={{ width: "92%", height: 10 }} />
                      <span className="skeleton" style={{ width: "86%", height: 10 }} />
                      <span className="skeleton" style={{ width: "64%", height: 10 }} />
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </Panel>
  );
});
