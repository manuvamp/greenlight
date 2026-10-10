"""Where repo code runs. Never on the host.

The interface follows Token Factory Sandboxes: run one command against a filesystem state,
save that state as a checkpoint, and start new sandboxes from a checkpoint (to branch parallel
fix attempts). The Docker executor implements the same thing locally.
"""

from __future__ import annotations

import shlex
from abc import ABC, abstractmethod
from dataclasses import dataclass

# Command output kept per stream. Test logs can be huge; the tail holds the summary.
MAX_STREAM_CHARS = 200_000


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    @property
    def output(self) -> str:
        return (self.stdout + ("\n" + self.stderr if self.stderr else "")).strip()


def clip(text: str, limit: int = MAX_STREAM_CHARS) -> str:
    if len(text) <= limit:
        return text
    head = limit // 4
    return text[:head] + f"\n... [{len(text) - limit} chars clipped] ...\n" + text[-(limit - head):]


class Sandbox(ABC):
    """One isolated filesystem + shell. `workdir` is where the repo lives."""

    workdir = "/repo"

    @abstractmethod
    def run(self, command: str, *, timeout: int = 600, cwd: str | None = None,
            env: dict[str, str] | None = None) -> ExecResult: ...

    @abstractmethod
    def read_file(self, path: str) -> str: ...

    @abstractmethod
    def write_file(self, path: str, content: str | bytes) -> None: ...

    @abstractmethod
    def checkpoint(self, name: str) -> str:
        """Save the current filesystem; returns an id that `Executor.open` accepts."""

    @abstractmethod
    def close(self) -> None: ...

    def path(self, p: str) -> str:
        """Absolute paths are kept; relative ones are inside the repo."""
        return p if p.startswith("/") else f"{self.workdir}/{p}"

    def exists(self, rel: str) -> bool:
        return self.run(f"test -e {shlex.quote(self.path(rel))}", timeout=30).exit_code == 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class Executor(ABC):
    name: str

    @abstractmethod
    def open(self, checkpoint: str | None = None) -> Sandbox:
        """A new sandbox from the toolchain image, or from a saved checkpoint."""

    def cleanup(self) -> None:
        """Remove checkpoints this executor created (no-op where the backend expires them)."""
