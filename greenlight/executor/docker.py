"""Local Docker executor: a long-lived container per sandbox, `docker commit` for checkpoints."""

from __future__ import annotations

import base64
import shlex
import subprocess
import time
import uuid

from .base import ExecResult, Executor, Sandbox, clip

RUNNER_IMAGE = "greenlight-runner:latest"


def _docker(*args: str, timeout: int = 120, input: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, timeout=timeout, input=input)


class DockerSandbox(Sandbox):
    def __init__(self, executor: "DockerExecutor", image: str):
        self.executor = executor
        self.name = f"greenlight-{uuid.uuid4().hex[:10]}"
        p = _docker("run", "-d", "--name", self.name, "--label", "greenlight=1",
                    "--memory", executor.memory, "--cpus", str(executor.cpus),
                    "-w", self.workdir, image, "sleep", "infinity")
        if p.returncode != 0:
            raise RuntimeError(f"docker run failed: {p.stderr.decode(errors='replace')}")
        self.closed = False

    def run(self, command: str, *, timeout: int = 600, cwd: str | None = None,
            env: dict[str, str] | None = None) -> ExecResult:
        if len(command) > 6000:
            # Windows caps a command line at ~32k chars: ship long scripts as a file instead.
            script = f"/tmp/gl-cmd-{uuid.uuid4().hex[:8]}.sh"
            self.write_file(script, command)
            command = f"bash {script}; rc=$?; rm -f {script}; exit $rc"
        args = ["exec", "-w", cwd or self.workdir]
        for k, v in (env or {}).items():
            args += ["-e", f"{k}={v}"]
        # `timeout` inside the container kills the command itself, not just our wait.
        args += [self.name, "timeout", "-k", "5", str(timeout), "bash", "-lc", command]
        t0 = time.monotonic()
        try:
            p = _docker(*args, timeout=timeout + 30)
        except subprocess.TimeoutExpired as e:
            return ExecResult(124, clip((e.stdout or b"").decode(errors="replace")),
                              clip((e.stderr or b"").decode(errors="replace")),
                              time.monotonic() - t0, timed_out=True)
        dur = time.monotonic() - t0
        return ExecResult(p.returncode, clip(p.stdout.decode(errors="replace")),
                          clip(p.stderr.decode(errors="replace")), dur, timed_out=p.returncode == 124)

    def read_file(self, path: str) -> str:
        r = self.run(f"cat {shlex.quote(self.path(path))}", timeout=30)
        if r.exit_code != 0:
            raise FileNotFoundError(path)
        return r.stdout

    def write_file(self, path: str, content: str | bytes) -> None:
        full = self.path(path)
        raw = content.encode() if isinstance(content, str) else content
        data = base64.b64encode(raw).decode()
        p = _docker("exec", "-i", self.name, "bash", "-c",
                    f"mkdir -p \"$(dirname {shlex.quote(full)})\" && base64 -d > {shlex.quote(full)}",
                    input=data.encode(), timeout=60)
        if p.returncode != 0:
            raise OSError(f"write {path} failed: {p.stderr.decode(errors='replace')}")

    def checkpoint(self, name: str) -> str:
        tag = f"greenlight-ckpt:{name}-{uuid.uuid4().hex[:6]}"
        p = _docker("commit", self.name, tag, timeout=600)
        if p.returncode != 0:
            raise RuntimeError(f"docker commit failed: {p.stderr.decode(errors='replace')}")
        self.executor.checkpoints.append(tag)
        return tag

    def close(self) -> None:
        if not self.closed:
            _docker("rm", "-f", self.name, timeout=60)
            self.closed = True


class DockerExecutor(Executor):
    name = "docker"

    def __init__(self, image: str = RUNNER_IMAGE, memory: str = "4g", cpus: float = 4):
        self.image = image
        self.memory = memory
        self.cpus = cpus
        self.checkpoints: list[str] = []

    def open(self, checkpoint: str | None = None) -> DockerSandbox:
        return DockerSandbox(self, checkpoint or self.image)

    def cleanup(self) -> None:
        for tag in self.checkpoints:
            _docker("rmi", "-f", tag, timeout=120)
        self.checkpoints.clear()
