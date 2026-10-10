"""Load settings from the environment and the nearest .env file."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv


def load_env() -> None:
    # Windows consoles default to cp1252; model output contains characters it can't print.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    path = find_dotenv(usecwd=True) or str(Path(__file__).resolve().parents[1] / ".env")
    load_dotenv(path, override=False)
