"""Find the official migration guide with Tavily and turn it into a rule sheet with Nemotron.

A rule sheet is a list of concrete API changes (old -> new), each with a grep pattern to find
call sites and the URL + section it came from, so every edit in the PR can cite its source.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from tavily import TavilyClient

from .budget import Budget, default_home
from .events import EventLog
from .llm import LLM
from .models import Role

OFFICIAL_DOMAINS = {
    "pydantic": ["docs.pydantic.dev", "pydantic.dev"],
    "numpy": ["numpy.org"],
    "pandas": ["pandas.pydata.org"],
    "sqlalchemy": ["docs.sqlalchemy.org"],
    "marshmallow": ["marshmallow.readthedocs.io"],
    "flask": ["flask.palletsprojects.com"],
    "werkzeug": ["werkzeug.palletsprojects.com"],
    "httpx": ["www.python-httpx.org"],
}

DIGEST_CHUNK_CHARS = 30_000
MAX_PAGES = 3


@dataclass
class Rule:
    id: str
    old: str
    new: str
    grep: str = ""
    note: str = ""
    url: str = ""
    section: str = ""


@dataclass
class RuleSheet:
    lib: str
    from_major: int
    to_major: int
    sources: list[dict] = field(default_factory=list)  # {url, title}
    rules: list[Rule] = field(default_factory=list)

    def to_json(self) -> dict:
        return {"lib": self.lib, "from_major": self.from_major, "to_major": self.to_major,
                "sources": self.sources, "rules": [asdict(r) for r in self.rules]}

    @classmethod
    def from_json(cls, d: dict) -> "RuleSheet":
        return cls(d["lib"], d["from_major"], d["to_major"], d.get("sources", []),
                   [Rule(**r) for r in d.get("rules", [])])

    def compact(self, ids: set[str] | None = None) -> str:
        """Rules as short lines for prompts."""
        lines = []
        for r in self.rules:
            if ids is not None and r.id not in ids:
                continue
            note = f" — {r.note}" if r.note else ""
            lines.append(f"[{r.id}] {r.old}  →  {r.new}{note}")
        return "\n".join(lines)


DIGEST_SYSTEM = """You turn a library migration guide into a precise rule sheet for an automated code migrator.
Extract EVERY concrete code-level change a user must make when upgrading {lib} from {fr}.x to {to}.x:
renamed/removed functions, methods, attributes, config keys, decorators, arguments, import paths,
changed defaults or behaviour that breaks tests. Skip marketing, performance notes and internals.

Return JSON: {{"rules": [{{"old": str, "new": str, "grep": str, "note": str, "section": str}}]}}
- old/new: short code-like forms, e.g. "Field(regex=...)" -> "Field(pattern=...)".
- grep: a POSIX extended regex that finds the OLD usage in source code (e.g. "regex[[:space:]]*="), or "" if not greppable.
- note: one short sentence with any gotcha (argument order, semantics change). Empty if none.
- section: the heading in the guide this came from.
Be exhaustive but never invent changes that are not in the text, and never repeat a rule.
At most 60 rules for this excerpt; if there are more, keep the ones most likely to break code."""


class Researcher:
    def __init__(self, llm: LLM, events: EventLog, run: str, budget: Budget | None = None,
                 cache_dir: Path | None = None):
        key = os.environ.get("TAVILY_API_KEY")
        if not key:
            raise RuntimeError("TAVILY_API_KEY is not set")
        self.tavily = TavilyClient(api_key=key)
        self.llm = llm
        self.ev = events
        self.run = run
        self.budget = budget or llm.budget
        self.cache_dir = cache_dir or (default_home() / "rules")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ---------- Tavily, metered ----------

    def _search(self, query: str, *, domains: list[str] | None = None, depth: str = "basic",
                max_results: int = 5) -> list[dict]:
        credits = 2 if depth == "advanced" else 1
        res = self.budget.reserve(run=self.run, kind="tavily", label=f"search:{query[:60]}", credits=credits)
        try:
            out = self.tavily.search(query, search_depth=depth, max_results=max_results,
                                     include_domains=domains or None)
        except Exception:
            res.settle(credits=credits, error=True)
            raise
        res.settle(credits=credits)
        self.ev.emit("tavily", op="search", query=query, domains=domains or [], credits=credits,
                     n=len(out.get("results", [])))
        return out.get("results", [])

    def _extract(self, urls: list[str]) -> list[dict]:
        credits = max(1, -(-len(urls) // 5))
        res = self.budget.reserve(run=self.run, kind="tavily", label=f"extract:{len(urls)}", credits=credits)
        try:
            out = self.tavily.extract(urls=urls, extract_depth="basic", format="markdown")
        except Exception:
            res.settle(credits=credits, error=True)
            raise
        res.settle(credits=credits)
        self.ev.emit("tavily", op="extract", urls=urls, credits=credits,
                     ok=len(out.get("results", [])), failed=len(out.get("failed_results", [])))
        return out.get("results", [])

    # ---------- rule sheet ----------

    def rule_sheet(self, lib: str, from_major: int, to_major: int) -> RuleSheet:
        cache = self.cache_dir / f"{lib.lower()}-{from_major}-{to_major}.json"
        if cache.exists():
            sheet = RuleSheet.from_json(json.loads(cache.read_text(encoding="utf-8")))
            for s in sheet.sources:
                self.ev.emit("source", url=s["url"], title=s.get("title", ""), cached=True)
            self.ev.log(f"rule sheet for {lib} {from_major}→{to_major} from cache ({len(sheet.rules)} rules)")
            return sheet

        query = f"{lib} {from_major}.x to {to_major}.0 migration guide breaking changes"
        hits = self._search(query, domains=OFFICIAL_DOMAINS.get(lib.lower()), depth="advanced")
        if not hits:
            hits = self._search(query, depth="advanced")
        pages = self._pick_pages(hits, lib, to_major)
        for p in pages:
            self.ev.emit("source", url=p["url"], title=p.get("title", ""), score=p.get("score"))
        extracted = self._extract([p["url"] for p in pages])
        titles = {p["url"]: p.get("title", "") for p in pages}

        sheet = RuleSheet(lib, from_major, to_major)
        seen: set[str] = set()
        dropped = 0
        for doc in extracted:
            url = doc.get("url", "")
            text = doc.get("raw_content") or ""
            if not text.strip():
                continue
            sheet.sources.append({"url": url, "title": titles.get(url, "")})
            for chunk in _chunks(text, DIGEST_CHUNK_CHARS):
                for r in self._digest(lib, from_major, to_major, chunk):
                    old = r.get("old", "").strip()
                    key = re.sub(r"[^a-z0-9_]", "", old.lower())
                    if not key or key in seen:
                        continue
                    if not _grounded(old, chunk):
                        dropped += 1
                        continue
                    seen.add(key)
                    sheet.rules.append(Rule(
                        id=f"R{len(sheet.rules) + 1}", old=r.get("old", ""), new=r.get("new", ""),
                        grep=_safe_regex(r.get("grep", "")), note=r.get("note", ""), url=url,
                        section=r.get("section", ""),
                    ))
        cache.write_text(json.dumps(sheet.to_json(), indent=2), encoding="utf-8")
        self.ev.emit("rules", lib=lib, count=len(sheet.rules), dropped_ungrounded=dropped, sources=sheet.sources)
        return sheet

    @staticmethod
    def _pick_pages(hits: list[dict], lib: str, to_major: int) -> list[dict]:
        def score(h: dict) -> float:
            u = (h.get("url", "") + " " + h.get("title", "")).lower()
            s = h.get("score", 0.0)
            if "migrat" in u:
                s += 1.0
            if f"{to_major}.0" in u or f"v{to_major}" in u or f"{to_major}_0" in u:
                s += 0.5
            if any(d in u for d in OFFICIAL_DOMAINS.get(lib.lower(), [])):
                s += 0.5
            return s
        ranked = sorted(hits, key=score, reverse=True)
        return ranked[:MAX_PAGES]

    def _digest(self, lib: str, fr: int, to: int, text: str, depth: int = 0) -> list[dict]:
        msgs = [
            {"role": "system", "content": DIGEST_SYSTEM.format(lib=lib, fr=fr, to=to)},
            {"role": "user", "content": text},
        ]
        r = self.llm.chat(Role.DIGEST, msgs, run=self.run, max_tokens=12000, json_mode=True)
        try:
            data = r.json()
        except json.JSONDecodeError:
            data = None
        if data is None or r.finish_reason == "length":
            # Output cut off: split the chunk and digest each half, rather than lose its rules.
            if depth < 2 and len(text) > 4000:
                mid = len(text) // 2
                cut = text.rfind("\n#", 0, mid)
                cut = cut if cut > len(text) // 4 else mid
                return self._digest(lib, fr, to, text[:cut], depth + 1) + \
                    self._digest(lib, fr, to, text[cut:], depth + 1)
            return []
        rules = data.get("rules", []) if isinstance(data, dict) else []
        return [x for x in rules if isinstance(x, dict)]

    # ---------- ad-hoc lookups (editor tool) ----------

    def lookup(self, lib: str, query: str) -> str:
        """Search docs for one specific problem; returns short cited snippets for the editor."""
        official = OFFICIAL_DOMAINS.get(lib.lower())
        domains = official + ["github.com", "stackoverflow.com"] if official else None
        hits = self._search(f"{lib} {query}", domains=domains, max_results=5)
        out = []
        for h in hits:
            self.ev.emit("source", url=h.get("url", ""), title=h.get("title", ""), via="lookup", query=query)
            out.append(f"- {h.get('title', '')} ({h.get('url', '')})\n  {(h.get('content') or '')[:700]}")
        return "\n".join(out) or "no results"


def _chunks(text: str, size: int) -> list[str]:
    if len(text) <= size:
        return [text]
    parts, cur = [], []
    n = 0
    for para in re.split(r"(?m)^(?=#{1,3} )", text):  # split on markdown headings
        if n + len(para) > size and cur:
            parts.append("".join(cur))
            cur, n = [], 0
        cur.append(para)
        n += len(para)
    if cur:
        parts.append("".join(cur))
    return parts


_GENERIC = {"config", "class", "model", "models", "field", "fields", "method", "removed", "renamed",
             "deprecated", "none", "true", "false", "self", "cls", "value", "values", "type", "types",
             "the", "and", "use", "with", "from", "import", "default", "setting", "attribute"}


def _grounded(old: str, source: str) -> bool:
    """A rule counts only if a specific identifier from its OLD form appears in the source text."""
    idents = [i for i in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", old) if i.lower() not in _GENERIC]
    if not idents:
        return False
    src = source.lower()
    return any(i.lower() in src for i in idents)


def _safe_regex(pattern: str) -> str:
    """Keep only grep patterns Python's re can compile (a proxy for sanity)."""
    if not pattern:
        return ""
    try:
        re.compile(pattern.replace("[[:space:]]", r"\s"))
        return pattern
    except re.error:
        return ""
