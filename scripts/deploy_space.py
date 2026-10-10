"""Deploy the Greenlight web demo to a Hugging Face Space (Docker SDK, free CPU).

  HF_TOKEN=... python scripts/deploy_space.py [--public]

Creates (or updates) the Space `<user>/greenlight`, private by default, and uploads only what the
demo image needs: the Dockerfile, the agent package, the server, the web app source, the
replays and the official scoreboard. No secrets: live runs stay off on the Space.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]

SPACE_README = """---
title: Greenlight
emoji: 🟢
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Breaking dependency upgrades by NVIDIA Nemotron, proven by tests
---

# Greenlight: live demo

Recorded upgrade runs on **NVIDIA Nemotron via Nebius Token Factory**, replayed event by event, plus the
eval scoreboard. Source and docs: https://github.com/manuvamp/greenlight
"""

INCLUDE = [
    "Dockerfile", ".dockerignore", "pyproject.toml", "LICENSE",
    "greenlight/**", "server/**", "web/src/**", "web/public/**", "web/index.html",
    "web/package.json", "web/package-lock.json", "web/tsconfig.json", "web/vite.config.ts",
    "replays/**", "examples/**", "evals/dataset.toml", "evals/results/eval-nemotron/scoreboard.json",
]
EXCLUDE = ["**/__pycache__/**", "**/*.pyc", "web/node_modules/**", "web/dist/**"]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--public", action="store_true", help="make the Space public (default private)")
    p.add_argument("--name", default="greenlight")
    a = p.parse_args()
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("HF_TOKEN is not set", file=sys.stderr)
        return 2
    api = HfApi(token=token)
    user = api.whoami()["name"]
    repo_id = f"{user}/{a.name}"
    api.create_repo(repo_id, repo_type="space", space_sdk="docker", private=not a.public, exist_ok=True)
    api.update_repo_settings(repo_id, repo_type="space", private=not a.public)
    # The Space README (with the YAML header) replaces the project README inside the Space repo.
    api.upload_file(path_or_fileobj=SPACE_README.encode(), path_in_repo="README.md",
                    repo_id=repo_id, repo_type="space")
    api.upload_folder(folder_path=str(ROOT), repo_id=repo_id, repo_type="space",
                      allow_patterns=INCLUDE, ignore_patterns=EXCLUDE,
                      commit_message="Deploy Greenlight demo")
    print(f"https://huggingface.co/spaces/{repo_id}  (private={not a.public})")
    print(f"app URL once built: https://{user.replace('_', '-').lower()}-{a.name}.hf.space")
    return 0


if __name__ == "__main__":
    sys.exit(main())
