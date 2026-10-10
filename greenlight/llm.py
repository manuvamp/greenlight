"""Nemotron on Nebius Token Factory: routed, priced, and capped.

Every call:
  1. picks a model from the role (models.route),
  2. reserves its worst-case cost with the budget guard (refused if it would cross a cap),
  3. calls the OpenAI-compatible Token Factory API,
  4. settles the real cost from `usage` and emits a CallRecord for the routing panel.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

import openai
from openai import OpenAI

from .budget import Budget
from .models import ALL, THINKING, Model, Role, route

BASE_URL = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")

# Conservative token estimate for the pre-call reservation: ~3 chars per token
# (code and JSON tokenize denser than English prose).
CHARS_PER_TOKEN = 3


class LLMError(RuntimeError):
    pass


class LLMTruncated(LLMError):
    """The model hit max_tokens before producing an answer (usually all spent on reasoning)."""


@dataclass
class CallRecord:
    run: str
    role: str
    model: str
    thinking: bool
    tokens_in: int
    tokens_out: int
    usd: float
    latency_s: float
    ok: bool
    note: str = ""
    ts: float = field(default_factory=time.time)


@dataclass
class LLMResult:
    content: str
    tool_calls: list[dict]
    reasoning: str
    finish_reason: str
    record: CallRecord
    raw_message: dict

    def json(self) -> Any:
        """Parse `content` as JSON, tolerating a ```json fence."""
        text = self.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else ""
            text = text.rsplit("```", 1)[0]
        return json.loads(text)


def estimate_tokens(*parts: Any) -> int:
    chars = sum(len(p if isinstance(p, str) else json.dumps(p, default=str)) for p in parts if p)
    return chars // CHARS_PER_TOKEN + 16


class LLM:
    def __init__(
        self,
        budget: Budget | None = None,
        api_key: str | None = None,
        model_override: str | None = None,
        timeout: float = 180.0,
    ):
        key = api_key or os.environ.get("NEBIUS_API_KEY")
        if not key:
            raise LLMError("NEBIUS_API_KEY is not set")
        self.client = OpenAI(base_url=BASE_URL, api_key=key, timeout=timeout, max_retries=0)
        self.budget = budget or Budget()
        self.model_override = model_override
        self.listeners: list[Callable[[CallRecord], None]] = []

    def on_call(self, fn: Callable[[CallRecord], None]) -> None:
        self.listeners.append(fn)

    def _emit(self, rec: CallRecord) -> None:
        for fn in self.listeners:
            try:
                fn(rec)
            except Exception:
                pass

    def chat(
        self,
        role: Role,
        messages: list[dict],
        *,
        run: str,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        max_tokens: int = 2048,
        thinking: bool | None = None,
        temperature: float | None = None,
        json_mode: bool = False,
        retries: int = 2,
        model_id: str | None = None,
    ) -> LLMResult:
        model = route(role, self.model_override or model_id)
        think = THINKING[role] if thinking is None else thinking
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                return self._call_once(model, role, messages, run, tools, tool_choice,
                                       max_tokens, think, temperature, json_mode)
            except (openai.RateLimitError, openai.APIConnectionError, openai.InternalServerError) as e:
                last_err = e
                time.sleep(2 * (attempt + 1) ** 2)
        raise LLMError(f"{model.id} failed after {retries + 1} attempts: {last_err}")

    def _call_once(self, model: Model, role: Role, messages, run, tools, tool_choice,
                   max_tokens, think, temperature, json_mode) -> LLMResult:
        est_in = estimate_tokens(messages, tools)
        worst = model.cost(est_in, max_tokens)
        res = self.budget.reserve(run=run, kind="llm", label=f"{role.value}:{model.id}", usd=worst)

        kwargs: dict[str, Any] = {
            "model": model.id,
            "messages": messages,
            "max_tokens": max_tokens,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": think}},
        }
        if tools:
            kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice
        if temperature is not None:
            kwargs["temperature"] = temperature
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        t0 = time.monotonic()
        try:
            resp = self.client.chat.completions.create(**kwargs)
        except (openai.BadRequestError, openai.AuthenticationError,
                openai.PermissionDeniedError, openai.NotFoundError, openai.RateLimitError) as e:
            # Rejected before any generation: nothing was billed.
            res.settle(usd=0.0, model=model.id, error=type(e).__name__)
            self._emit(CallRecord(run, role.value, model.id, think, 0, 0, 0.0,
                                  time.monotonic() - t0, False, type(e).__name__))
            raise
        except Exception as e:
            # Unknown outcome (timeout, dropped connection): assume the worst case was billed.
            res.settle(usd=worst, model=model.id, error=type(e).__name__, assumed=True)
            self._emit(CallRecord(run, role.value, model.id, think, est_in, max_tokens, worst,
                                  time.monotonic() - t0, False, type(e).__name__))
            raise
        latency = time.monotonic() - t0

        usage = resp.usage
        tin = getattr(usage, "prompt_tokens", None) or est_in
        tout = getattr(usage, "completion_tokens", None)
        if tout is None:
            tout = max_tokens
        usd = model.cost(tin, tout)
        res.settle(usd=usd, model=model.id, tokens_in=tin, tokens_out=tout)

        choice = resp.choices[0]
        msg = choice.message
        msg_dict = msg.model_dump(exclude_none=True)
        content = msg.content or ""
        reasoning = msg_dict.get("reasoning_content") or msg_dict.get("reasoning") or ""
        tool_calls = [tc.model_dump() for tc in (msg.tool_calls or [])]
        finish = choice.finish_reason or ""

        rec = CallRecord(run, role.value, model.id, think, tin, tout, usd, latency, True, finish)
        self._emit(rec)

        if finish == "length" and not content.strip() and not tool_calls:
            raise LLMTruncated(
                f"{model.id} spent all {max_tokens} tokens without answering (thinking={think})"
            )
        return LLMResult(content, tool_calls, reasoning, finish, rec, msg_dict)


def record_to_dict(rec: CallRecord) -> dict:
    d = asdict(rec)
    d["model_label"] = ALL[rec.model].label if rec.model in ALL else rec.model
    return d
