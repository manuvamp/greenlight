"""Baseline -> bump -> red, with no model calls. Checks the executor + workspace plumbing."""

from __future__ import annotations

import sys
import time

from greenlight.config import load_env

load_env()

from greenlight.executor import get_executor  # noqa: E402
from greenlight.workspace import Workspace  # noqa: E402

src = sys.argv[1] if len(sys.argv) > 1 else "examples/pydantic-v1-shop"
lib, spec = (sys.argv[2], sys.argv[3]) if len(sys.argv) > 3 else ("pydantic", ">=2,<3")

ex = get_executor("docker")
t0 = time.monotonic()
with ex.open() as sb:
    ws = Workspace(sb)
    if src.startswith(("http://", "https://")):
        ws.clone(src)
    else:
        ws.upload(src)
    p = ws.detect()
    print("manifests:", p.manifests, "| python:", p.python)
    print("install:", p.install_cmds)
    r = ws.install()
    print("install ok:", r.ok, f"{time.monotonic() - t0:.0f}s")
    if not r.ok:
        print(r.output[-3000:])
        sys.exit(1)
    print(lib, "before:", ws.installed_version(lib))
    base = ws.run_tests()
    print("BASELINE:", base.summary(), f"{base.duration_s:.1f}s")
    if base.collection_error:
        print(base.collection_error[-2000:])

    print("bump:", ws.bump(lib, spec))
    r = ws.install()
    print("re-install ok:", r.ok)
    if not r.ok:
        print(r.output[-3000:])
    print(lib, "after:", ws.installed_version(lib))
    after = ws.run_tests()
    print("AFTER BUMP:", after.summary())
    if after.collection_error:
        print("collection error tail:\n", after.collection_error[-2500:])
    for k, v in list(after.failures.items())[:6]:
        print(" -", k, "|", v.splitlines()[0][:160] if v else "")
    print(f"total {time.monotonic() - t0:.0f}s")
