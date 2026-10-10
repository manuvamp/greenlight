// Minimal unified-diff parser for `git diff` output.

export type DiffLineKind = "ctx" | "add" | "del" | "hunk" | "note";

export interface DiffLine {
  kind: DiffLineKind;
  text: string;
  oldNo: number | null;
  newNo: number | null;
}

export type FileStatus = "modified" | "added" | "deleted" | "renamed";

export interface DiffFile {
  path: string;
  oldPath: string | null;
  status: FileStatus;
  binary: boolean;
  lines: DiffLine[];
  added: number;
  removed: number;
}

const HUNK_RE = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$/;

function stripPrefix(p: string): string {
  return p.replace(/^"?[ab]\//, "").replace(/"$/, "").replace(/\t.*$/, "");
}

export function parseDiff(text: string): DiffFile[] {
  const files: DiffFile[] = [];
  let cur: DiffFile | null = null;
  let oldNo = 0;
  let newNo = 0;
  let inHunk = false;

  const start = (path: string, oldPath: string | null = null): DiffFile => {
    const f: DiffFile = { path, oldPath, status: "modified", binary: false, lines: [], added: 0, removed: 0 };
    files.push(f);
    inHunk = false;
    return f;
  };

  for (const line of text.replace(/\r\n/g, "\n").split("\n")) {
    if (line.startsWith("diff --git ")) {
      const m = line.match(/^diff --git (?:"?a\/(.+?)"?) (?:"?b\/(.+?)"?)$/);
      cur = start(m ? m[2] : line.slice(11), m ? m[1] : null);
      continue;
    }
    if (!cur && line.startsWith("--- ")) {
      cur = start(stripPrefix(line.slice(4)));
      continue;
    }
    if (!cur) continue;

    if (!inHunk) {
      if (line.startsWith("new file mode")) cur.status = "added";
      else if (line.startsWith("deleted file mode")) cur.status = "deleted";
      else if (line.startsWith("rename from ")) {
        cur.status = "renamed";
        cur.oldPath = line.slice(12);
      } else if (line.startsWith("rename to ")) cur.path = line.slice(10);
      else if (line.startsWith("Binary files ") || line.startsWith("GIT binary patch")) cur.binary = true;
      else if (line.startsWith("--- ")) {
        const p = line.slice(4);
        if (p === "/dev/null") cur.status = "added";
      } else if (line.startsWith("+++ ")) {
        const p = line.slice(4);
        if (p === "/dev/null") cur.status = "deleted";
        else cur.path = stripPrefix(p);
      }
    }

    const h = line.match(HUNK_RE);
    if (h) {
      inHunk = true;
      oldNo = Number(h[1]);
      newNo = Number(h[3]);
      cur.lines.push({ kind: "hunk", text: line, oldNo: null, newNo: null });
      continue;
    }
    if (!inHunk || cur.binary) continue;

    const c = line.charAt(0);
    if (c === "+") {
      cur.lines.push({ kind: "add", text: line.slice(1), oldNo: null, newNo: newNo++ });
      cur.added++;
    } else if (c === "-") {
      cur.lines.push({ kind: "del", text: line.slice(1), oldNo: oldNo++, newNo: null });
      cur.removed++;
    } else if (c === " ") {
      cur.lines.push({ kind: "ctx", text: line.slice(1), oldNo: oldNo++, newNo: newNo++ });
    } else if (c === "\\") {
      cur.lines.push({ kind: "note", text: line.slice(2), oldNo: null, newNo: null });
    } else if (line === "") {
      // trailing newline at end of the diff text
    } else {
      inHunk = false;
    }
  }
  return files;
}

/** search/replace patch -> diff lines (no line numbers known). */
export function patchLines(search: string | undefined, replace: string | undefined): DiffLine[] {
  const out: DiffLine[] = [];
  for (const l of (search ?? "").split("\n")) out.push({ kind: "del", text: l, oldNo: null, newNo: null });
  for (const l of (replace ?? "").split("\n")) out.push({ kind: "add", text: l, oldNo: null, newNo: null });
  return out;
}

/** Body of a unified diff without file headers (rewrite_file patches). */
export function rawDiffLines(diff: string): DiffLine[] {
  const files = parseDiff(diff);
  if (files.length && files[0].lines.length) return files.flatMap((f) => f.lines);
  return diff
    .split("\n")
    .filter((l) => !l.startsWith("--- ") && !l.startsWith("+++ "))
    .map((l): DiffLine => {
      const c = l.charAt(0);
      if (l.startsWith("@@")) return { kind: "hunk", text: l, oldNo: null, newNo: null };
      if (c === "+") return { kind: "add", text: l.slice(1), oldNo: null, newNo: null };
      if (c === "-") return { kind: "del", text: l.slice(1), oldNo: null, newNo: null };
      return { kind: "ctx", text: l.startsWith(" ") ? l.slice(1) : l, oldNo: null, newNo: null };
    });
}
