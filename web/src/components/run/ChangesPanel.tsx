import { memo, useEffect, useMemo, useState } from "react";
import type { PatchEvent, PinChange } from "../../types";
import { parseDiff, patchLines, rawDiffLines } from "../../run/diff";
import type { DiffFile, DiffLine } from "../../run/diff";
import { fmtClock } from "../../format";
import { ruleChips } from "../../run/derive";
import { Icon } from "../Icon";
import { Empty, Panel } from "../ui";

function DiffStatBlocks({ added, removed }: { added: number; removed: number }) {
  const total = added + removed;
  const blocks = 5;
  const g = total ? Math.round((added / total) * blocks) : 0;
  return (
    <span className="statblocks" aria-hidden="true">
      {Array.from({ length: blocks }, (_, i) => (
        <span key={i} className={i < g ? "sb-add" : total ? "sb-del" : "sb-none"} />
      ))}
    </span>
  );
}

function Lines({ lines, numbered }: { lines: DiffLine[]; numbered: boolean }) {
  return (
    <div className="diff-table mono" role="table">
      {lines.map((l, i) =>
        l.kind === "hunk" ? (
          <div key={i} className="dl dl-hunk" role="row">
            {numbered && <span className="dl-no" />}
            {numbered && <span className="dl-no" />}
            <span className="dl-sign" />
            <span className="dl-code">{l.text}</span>
          </div>
        ) : (
          <div key={i} className={`dl dl-${l.kind}`} role="row">
            {numbered && <span className="dl-no">{l.oldNo ?? ""}</span>}
            {numbered && <span className="dl-no">{l.newNo ?? ""}</span>}
            <span className="dl-sign">{l.kind === "add" ? "+" : l.kind === "del" ? "−" : l.kind === "note" ? "\\" : ""}</span>
            <span className="dl-code">{l.text || " "}</span>
          </div>
        ),
      )}
    </div>
  );
}

const STATUS_LABEL: Record<DiffFile["status"], string> = {
  modified: "modified", added: "added", deleted: "deleted", renamed: "renamed",
};

function FileBlock({ file, defaultOpen }: { file: DiffFile; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`diff-file${open ? " is-open" : ""}`}>
      <button className="diff-file-head" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <Icon name="chevronRight" size={14} className="diff-chev" />
        <span className="diff-path mono">
          {file.oldPath && file.status === "renamed" ? `${file.oldPath} → ${file.path}` : file.path}
        </span>
        {file.status !== "modified" && <span className={`fs-badge fs-${file.status}`}>{STATUS_LABEL[file.status]}</span>}
        <span className="diff-file-stat mono">
          {file.binary ? (
            <span className="muted-2">binary</span>
          ) : (
            <>
              <span className="add">+{file.added}</span>
              <span className="del">−{file.removed}</span>
              <DiffStatBlocks added={file.added} removed={file.removed} />
            </>
          )}
        </span>
      </button>
      {open &&
        (file.binary ? (
          <div className="diff-binary">Binary file not shown.</div>
        ) : (
          <Lines lines={file.lines} numbered />
        ))}
    </div>
  );
}

export function DiffViewer({ diff }: { diff: string }) {
  const files = useMemo(() => parseDiff(diff), [diff]);
  const added = files.reduce((a, f) => a + f.added, 0);
  const removed = files.reduce((a, f) => a + f.removed, 0);
  if (!files.length) return <Empty icon="file" title="Empty diff">The agent finished without changing any files.</Empty>;
  return (
    <div className="diff">
      <div className="diff-summary mono">
        <span>{files.length} {files.length === 1 ? "file" : "files"} changed</span>
        <span className="add">+{added}</span>
        <span className="del">−{removed}</span>
      </div>
      {files.map((f, i) => (
        <FileBlock key={`${f.path}-${i}`} file={f} defaultOpen={!f.binary && (files.length <= 6 || i < 4) && f.lines.length < 600} />
      ))}
    </div>
  );
}

function PatchCard({ p, index, defaultOpen }: { p: PatchEvent; index: number; defaultOpen: boolean }) {
  const [userOpen, setUserOpen] = useState<boolean | null>(null);
  const open = userOpen ?? defaultOpen;
  const setOpen = (f: (o: boolean) => boolean) => setUserOpen(f(open));
  const lines = useMemo(
    () => (p.rewrite && p.diff ? rawDiffLines(p.diff) : patchLines(p.search, p.replace)),
    [p],
  );
  const rules = ruleChips(p.rule);
  return (
    <div className={`diff-file patch-card${open ? " is-open" : ""}`}>
      <button className="diff-file-head" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <Icon name="chevronRight" size={14} className="diff-chev" />
        <span className="patch-idx mono">#{index + 1}</span>
        <span className="diff-path mono">{p.path}</span>
        {p.rewrite && <span className="fs-badge">{p.rule === "bulk" ? "bulk rewrite" : "rewrite"}</span>}
        <span className="patch-rules">
          {rules.slice(0, 4).map((r) => <span key={r} className="rule-chip mono">{r}</span>)}
          {rules.length > 4 && <span className="rule-chip rule-more mono">+{rules.length - 4}</span>}
        </span>
        <span className="diff-file-stat mono">
          <span className="add">+{p.added}</span>
          <span className="del">−{p.removed}</span>
          <span className="muted-2">{fmtClock(p.t)}</span>
        </span>
      </button>
      {open && <Lines lines={lines.length > 160 ? lines.slice(0, 160) : lines} numbered={false} />}
    </div>
  );
}

export const ChangesPanel = memo(function ChangesPanel({
  patches, diff, pins,
}: { patches: PatchEvent[]; diff: string | null; pins: PinChange[] }) {
  const [tab, setTab] = useState<"diff" | "patches">(diff ? "diff" : "patches");
  useEffect(() => {
    setTab(diff ? "diff" : "patches");
  }, [diff]);

  const recent = useMemo(() => [...patches].reverse(), [patches]);

  return (
    <Panel
      title="Changes"
      icon="branch"
      className="changes-panel"
      aside={
        <div className="seg seg-sm">
          <button className={`seg-btn${tab === "diff" ? " is-on" : ""}`} disabled={!diff} onClick={() => setTab("diff")}>
            Final diff
          </button>
          <button className={`seg-btn${tab === "patches" ? " is-on" : ""}`} onClick={() => setTab("patches")}>
            Patch log <span className="seg-count">{patches.length}</span>
          </button>
        </div>
      }
    >
      {pins.length > 0 && (
        <div className="pins">
          {pins.map((p) => (
            <div key={p.file + p.after} className="pin mono">
              <Icon name="pin" size={13} />
              <span className="pin-file">{p.file}</span>
              <span className="pin-before">{p.before}</span>
              <Icon name="arrowRight" size={12} />
              <span className="pin-after">{p.after}</span>
            </div>
          ))}
        </div>
      )}
      {tab === "diff" && diff ? (
        <DiffViewer diff={diff} />
      ) : patches.length === 0 ? (
        <Empty icon="pencil" title="No edits yet">Nemotron 3 Super's patches stream in here as it edits the code.</Empty>
      ) : (
        <div className="diff">
          <div className="diff-summary mono">
            <span>{patches.length} {patches.length === 1 ? "patch" : "patches"} · newest first</span>
          </div>
          {recent.slice(0, 40).map((p, i) => (
            <PatchCard key={p.seq} p={p} index={patches.length - 1 - i} defaultOpen={i < 3} />
          ))}
        </div>
      )}
    </Panel>
  );
});
