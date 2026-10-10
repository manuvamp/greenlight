"""Print the latest (or a given) run result: checks, cost by role, diff."""

import collections
import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
paths = [a for a in sys.argv[1:] if not a.startswith("--")]
f = paths[0] if paths else max(glob.glob("runs/*.result.json"), key=os.path.getmtime)
d = json.load(open(f, encoding="utf-8"))
print(f"{f}\n{d['status'].upper()}: {d['headline']}  ({d['seconds']}s, ${d['usd']}, {d['iterations']} it, {d['escalations']} esc)")
for c in d.get("verify", {}).get("checks", []):
    print(("  OK " if c["ok"] else "  XX "), f"{c['severity']:5s}", c["name"], "|", c["detail"][:150])
agg = collections.defaultdict(lambda: [0, 0, 0, 0.0])
for c in d["calls"]:
    a = agg[f"{c['role']:9s} {c['model_label']}"]
    a[0] += 1; a[1] += c["tokens_in"]; a[2] += c["tokens_out"]; a[3] += c["usd"]
for k, v in agg.items():
    print(f"  {k:36s} calls={v[0]:3d} in={v[1]:7d} out={v[2]:6d} ${v[3]:.4f}")
if "--diff" in sys.argv:
    print(d["diff"])
if "--summary" in sys.argv:
    print(d.get("summary", ""))
