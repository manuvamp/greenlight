"""Nebius Token Factory Sandboxes (Contree) executor.

Every command is one Sandboxes operation that starts from an immutable image and, unless the
command fails to return one, saves a new image. The sandbox simply follows that chain of images,
so `checkpoint()` is free (it is the current image UUID) and branching parallel fix attempts is
just starting several sandboxes from the same UUID.
"""

from __future__ import annotations

import json
import os
import time
from datetime import timedelta

from ..budget import default_home
from .base import ExecResult, Executor, Sandbox, clip

BASE_OCI = "docker://docker.io/library/python:3.12-slim"
TOOLCHAIN_SETUP = (
    "set -e; apt-get update -qq && apt-get install -y -qq --no-install-recommends git build-essential "
    "ca-certificates >/dev/null && rm -rf /var/lib/apt/lists/*; pip install -q uv==0.11.19; "
    "UV_PYTHON_INSTALL_DIR=/opt/uv-python uv python install 3.9 3.10 3.11 3.12; "
    "git config --global user.email greenlight@agent.local; git config --global user.name Greenlight; "
    "git config --global advice.detachedHead false; mkdir -p /repo"
)
ENV = {"UV_PYTHON_INSTALL_DIR": "/opt/uv-python", "UV_LINK_MODE": "copy", "UV_CACHE_DIR": "/root/.cache/uv"}
OUTPUT_LIMIT = 4 * 1024 * 1024


def _text(x) -> str:
    if x is None:
        return ""
    if isinstance(x, bytes):
        return x.decode(errors="replace")
    if hasattr(x, "read"):
        data = x.read()
        return data.decode(errors="replace") if isinstance(data, bytes) else str(data)
    return str(x)


class ContreeSandbox(Sandbox):
    def __init__(self, executor: "ContreeExecutor", image):
        self.ex = executor
        self.image = image
        self.ops = 0

    def run(self, command: str, *, timeout: int = 600, cwd: str | None = None,
            env: dict[str, str] | None = None) -> ExecResult:
        t0 = time.monotonic()
        files = None
        if len(command) > 6000:
            files = {"/tmp/gl-cmd.sh": command.encode()}
            command = "bash /tmp/gl-cmd.sh"
        try:
            res = self.image.run(
                shell=command, cwd=cwd or self.workdir, env={**ENV, **(env or {})},
                timeout=timedelta(seconds=timeout), disposable=False, files=files,
                truncate_output_at=OUTPUT_LIMIT,
            ).wait()
        except Exception as e:  # operation-level failure: state stays at the last good image
            return ExecResult(125, "", f"sandbox operation failed: {type(e).__name__}: {e}",
                              time.monotonic() - t0, timed_out="Timed" in type(e).__name__)
        self.ops += 1
        if getattr(res, "uuid", None):
            self.image = res
        code = res.exit_code if res.exit_code is not None else 125
        return ExecResult(code, clip(_text(res.stdout)), clip(_text(res.stderr)), time.monotonic() - t0,
                          timed_out=code == 124)

    def read_file(self, path: str) -> str:
        try:
            return self.image.read(self.path(path)).decode(errors="replace")
        except Exception as e:
            raise FileNotFoundError(path) from e

    def write_file(self, path: str, content: str | bytes) -> None:
        data = content.encode() if isinstance(content, str) else content
        full = self.path(path)
        res = self.image.run(shell=f"mkdir -p \"$(dirname '{full}')\"", files={full: data},
                             disposable=False, timeout=timedelta(seconds=120)).wait()
        if res.exit_code not in (0, None) or not getattr(res, "uuid", None):
            raise OSError(f"write {path} failed: {_text(res.stderr)}")
        self.image = res
        self.ops += 1

    def checkpoint(self, name: str) -> str:
        return str(self.image.uuid)

    def close(self) -> None:
        pass  # images are immutable and expire server-side


class ContreeExecutor(Executor):
    name = "contree"

    def __init__(self):
        from contree_sdk import ContreeSync

        base_url = os.environ.get("NEBIUS_SANDBOX_URL", "https://api.tokenfactory.nebius.com/sandboxes")
        self.client = ContreeSync(base_url=base_url, token=os.environ["NEBIUS_API_KEY"])
        self.state_file = default_home() / "contree.json"
        self._toolchain = None

    def toolchain(self):
        if self._toolchain is not None:
            return self._toolchain
        state = json.loads(self.state_file.read_text()) if self.state_file.exists() else {}
        if state.get("toolchain"):
            try:
                self._toolchain = self.client.images.use(state["toolchain"], strict=True)
                return self._toolchain
            except Exception:
                pass
        base = self.client.images.oci(BASE_OCI, timeout=900)
        res = base.run(shell=TOOLCHAIN_SETUP, disposable=False, timeout=timedelta(minutes=20)).wait()
        if res.exit_code != 0 or not res.uuid:
            raise RuntimeError(f"toolchain setup failed: {_text(res.stderr)[-2000:]}")
        state["toolchain"] = str(res.uuid)
        self.state_file.write_text(json.dumps(state))
        self._toolchain = res
        return res

    def open(self, checkpoint: str | None = None) -> ContreeSandbox:
        img = self.client.images.use(checkpoint, strict=True) if checkpoint else self.toolchain()
        return ContreeSandbox(self, img)
