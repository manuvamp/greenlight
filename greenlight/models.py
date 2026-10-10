"""Nemotron models on Nebius Token Factory, their prices, and which job each one does.

Prices are USD per 1M tokens, read from tokenfactory.nebius.com/endpoints on 2026-10-10.
If Nebius changes them, update this table: the budget guard prices every call from it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class Model:
    id: str
    label: str
    usd_in_per_m: float
    usd_out_per_m: float

    def cost(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * self.usd_in_per_m + tokens_out * self.usd_out_per_m) / 1_000_000


ULTRA = Model("nvidia/Nemotron-3-Ultra-550b-a55b", "Nemotron 3 Ultra", 1.00, 3.00)
SUPER = Model("nvidia/nemotron-3-super-120b-a12b", "Nemotron 3 Super", 0.30, 0.90)
LIGHTNING = Model("nvidia/Nemotron-3_5-Lightning", "Nemotron 3.5 Lightning", 0.06, 0.24)
NANO = Model("nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "Nemotron 3 Nano", 0.06, 0.24)

ALL = {m.id: m for m in (ULTRA, SUPER, LIGHTNING, NANO)}


class Role(str, Enum):
    """What a call is for. The router maps each role to a model."""

    PLAN = "plan"          # read failures + migration rules, decide the edits
    ESCALATE = "escalate"  # re-plan after the editor stalls
    EDIT = "edit"          # tool-calling loop that changes code
    TRIAGE = "triage"      # condense test logs into grouped failures
    DIGEST = "digest"      # turn migration-guide pages into a rule sheet
    WRITE = "write"        # PR description, summaries


ROUTES: dict[Role, Model] = {
    Role.PLAN: ULTRA,
    Role.ESCALATE: ULTRA,
    Role.EDIT: SUPER,
    Role.TRIAGE: LIGHTNING,
    Role.DIGEST: LIGHTNING,
    Role.WRITE: LIGHTNING,
}

# Reasoning ("thinking") is on by default in Nemotron 3. Only the roles that need it keep it.
THINKING: dict[Role, bool] = {
    Role.PLAN: True,
    Role.ESCALATE: True,
    Role.EDIT: False,
    Role.TRIAGE: False,
    Role.DIGEST: False,
    Role.WRITE: False,
}


# Development stand-ins (GREENLIGHT_BACKEND=standin): free models of a similar tier, served by a local
# OpenAI-compatible proxy, so the agent loop can be iterated on without spending Token Factory credit.
# Every result that counts (eval scoreboard, replays, demo) is produced on the real Nemotron models.
STANDIN = {
    ULTRA.id: "claude-sonnet-5-5",
    SUPER.id: "claude-haiku-5-5",
    LIGHTNING.id: "gemini-3.1-flash-lite",
    NANO.id: "gemini-3.1-flash-lite",
}


def route(role: Role, override: str | None = None) -> Model:
    """Model for a role. `override` (a model id) forces one model, e.g. for the all-Ultra ablation."""
    if override:
        return ALL[override]
    return ROUTES[role]
