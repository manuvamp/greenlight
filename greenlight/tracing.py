"""neatlogs tracing: every upgrade run becomes one trace.

    greenlight.upgrade (WORKFLOW)
      prepare / baseline / bump / research / fix (CHAIN)
        plan (AGENT), bulk_migrate (AGENT), editor turns -> LLM spans (wrapped OpenAI client)
        tool:<name> (TOOL), run_tests (TOOL), tavily search (RETRIEVER)
      verify (GUARDRAIL), pr_summary (AGENT)

Failed tool calls and red test runs are marked as errors on their span, so a trace shows where the
agent went wrong and what it did next. Off unless NEATLOGS_API_KEY is set; the agent behaves the same.
"""

from __future__ import annotations

import functools
import json
import os
from typing import Any, Callable

_on = False
last_trace_id = ""


def enabled() -> bool:
    return _on


def init(tags: list[str] | None = None) -> bool:
    global _on
    if _on or not os.environ.get("NEATLOGS_API_KEY"):
        return _on
    import neatlogs

    neatlogs.init(workflow_name="greenlight", tags=tags or ["greenlight"])
    _instrument()
    _on = True
    return True


def wrap_client(client):
    """LLM spans (model, tokens, latency, messages) for an OpenAI-compatible client."""
    if not _on:
        return client
    import neatlogs

    return neatlogs.wrap(client)


def flush() -> None:
    if _on:
        import neatlogs

        neatlogs.flush()


def _val(v: Any) -> Any:
    if isinstance(v, (str, int, float, bool)):
        return v if not isinstance(v, str) else v[:8000]
    return json.dumps(v, default=str)[:8000]


def _set(span, **attrs) -> None:
    for k, v in attrs.items():
        if v is not None:
            span.set_attribute(k, _val(v))


def _error(span, msg: str) -> None:
    from opentelemetry.trace import Status, StatusCode

    span.set_status(Status(StatusCode.ERROR, msg[:300]))
    _set(span, **{"greenlight.error": msg[:2000]})


def _wrap(owner: Any, attr: str, kind: str, name: str | Callable[..., str],
          inputs: Callable[..., Any] | None = None, outputs: Callable[[Any], Any] | None = None,
          failed: Callable[[Any], str | None] | None = None) -> None:
    import neatlogs

    orig = getattr(owner, attr)

    @functools.wraps(orig)
    def traced(*a, **kw):
        label = name(*a, **kw) if callable(name) else name
        with neatlogs.trace(label, kind=kind) as sp:
            if kind == "WORKFLOW":
                global last_trace_id
                last_trace_id = format(sp.get_span_context().trace_id, "032x")
                a[0].trace_id = last_trace_id  # the Upgrader; parallel eval cases each keep their own
            if inputs:
                _set(sp, **{"input.value": inputs(*a, **kw)})
            try:
                out = orig(*a, **kw)
            except Exception as e:
                _error(sp, f"{type(e).__name__}: {e}")
                raise
            if outputs:
                _set(sp, **{"output.value": outputs(out)})
            why = failed(out) if failed else None
            if why:
                _error(sp, why)
            return out

    setattr(owner, attr, traced)


def _tests(run) -> dict | None:
    if run is None:
        return None
    return {"passed": len(run.passed), "failed": len(run.failed), "total": len(run.results),
            "collection_error": bool(run.collection_error), "summary": run.summary()}


def _instrument() -> None:
    import contextvars
    from concurrent.futures import ThreadPoolExecutor

    from . import agent, research, tools, workspace

    class ContextPool(ThreadPoolExecutor):
        """Bulk-migrate workers keep the parent span, so their LLM calls land in the run's trace."""

        def submit(self, fn, /, *a, **kw):
            return super().submit(contextvars.copy_context().run, fn, *a, **kw)

    agent.ThreadPoolExecutor = ContextPool

    U = agent.Upgrader
    _wrap(U, "run", "WORKFLOW", "greenlight.upgrade",
          inputs=lambda self: {"source": self.spec.source, "lib": self.spec.lib,
                               "target": self.spec.target_spec, "backend": self.llm.backend,
                               "run_id": self.run_id},
          outputs=lambda r: {k: getattr(r, k) for k in ("status", "headline", "from_version", "to_version",
                                                         "baseline", "final", "iterations", "escalations",
                                                         "usd", "seconds")},
          failed=lambda r: None if r.status in ("green", "noop", "precheck-ok") else f"{r.status}: {r.headline}")
    _wrap(U, "_prepare", "CHAIN", "prepare")
    _wrap(U, "_baseline", "CHAIN", "baseline", outputs=_tests)
    _wrap(U, "_bump", "CHAIN", "bump", outputs=_tests)
    _wrap(U, "_research", "CHAIN", "research",
          outputs=lambda s: {"rules": len(s.rules), "sources": s.sources})
    _wrap(U, "_plan", "AGENT", "plan", outputs=lambda p: p)
    _wrap(U, "_fix", "CHAIN", "fix", outputs=_tests)
    _wrap(U, "_bulk_migrate", "AGENT", "bulk_migrate")
    _wrap(U, "_write_summary", "AGENT", "pr_summary", outputs=lambda s: s)
    _wrap(agent, "verify", "GUARDRAIL", "verify",
          outputs=lambda rep: rep.as_dict(),
          failed=lambda rep: None if rep.passed else "verification failed: " +
          "; ".join(c.name for c in rep.checks if not c.ok))
    _wrap(tools.ToolBox, "call", "TOOL", lambda self, name, args_json: f"tool:{name}",
          inputs=lambda self, name, args_json: args_json,
          outputs=lambda out: out,
          failed=lambda out: out.splitlines()[0][:300]
          if out and out.startswith(("ERROR", "REPEATED", "REFUSED")) else None)
    _wrap(workspace.Workspace, "run_tests", "TOOL", "run_tests",
          inputs=lambda self, select=None, **kw: {"select": select},
          outputs=_tests,
          failed=lambda r: r.summary() if (r.failed or r.collection_error) else None)
    _wrap(research.Researcher, "_search", "RETRIEVER", "tavily.search",
          inputs=lambda self, query, **kw: {"query": query, **kw},
          outputs=lambda hits: [h.get("url") for h in hits] if isinstance(hits, list) else hits)
