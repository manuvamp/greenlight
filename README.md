# Greenlight

**The breaking dependency upgrades that Dependabot can't do.**

Greenlight reads the official migration guide, rewrites your code for the new major version, and runs your own test suite in a sandbox until it passes. Then it proves the result wasn't faked, and opens a PR that cites a source for every change.

All of it runs on **NVIDIA Nemotron models served by Nebius Token Factory**, with **Tavily** for research.

> Built for the [Nebius × NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/), Coding & Agentic Engineering track. MIT licensed.

```
$ greenlight upgrade https://github.com/org/repo pydantic@2

  ✓ prepare   python 3.11, deps installed
  ✓ baseline  pydantic==1.10.13 · 13 passed
  ✓ bump      pydantic==2.14.0  · 0 passed (import error)
  ✓ research  348 rules from the official migration guide (Tavily → Nemotron 3.5 Lightning)
  ✓ plan      17 steps (Nemotron 3 Ultra)
  ✓ migrate   3 files rewritten in parallel (Nemotron 3 Super)
  ✓ fix       13/13 baseline tests pass
  ■ GREEN     pydantic 1.10.13 → 2.14.0 · all anti-cheat checks pass · $0.04 · 64s
```

## Why

Version-bump bots open the PR and stop there. Major upgrades such as pydantic 1→2, numpy 1→2, pandas 1→2 and SQLAlchemy 1.4→2.0 break the code, so those PRs sit red for months. Teams stay on unsupported versions and pile up security debt.

Fixing one is tedious but well specified:
1. Read the migration guide.
2. Find every call site.
3. Change it.
4. Run the tests.
5. Repeat.

That's exactly the loop an agent should run, as long as you can **trust** the result.

## How it works

| Stage | What happens | Model |
|---|---|---|
| **Baseline** | Clone at a pinned commit into an isolated sandbox, install (including Poetry/Hatch/PEP 735 dev dependencies), run the tests. The passing set is the contract. | none |
| **Bump** | Rewrite the version pin in every manifest (requirements, `setup.py`, `setup.cfg`, `pyproject`/Poetry), reinstall, rerun the tests. Now they're red. | none |
| **Research** | Tavily searches the library's official docs and extracts the migration guide. Lightning turns it into a **rule sheet** of old API → new API, each rule with a grep pattern and a source URL. Rules not grounded in the source text are dropped. The sheet is cached. | Nemotron 3.5 Lightning |
| **Plan** | Ultra gets the grouped failures plus every call site the rules match, and writes a structured plan: files, rule ids, dependency changes and risks. | Nemotron 3 Ultra (reasoning on) |
| **Migrate** | Super rewrites each planned file in one pass, **in parallel**. Each rewrite is syntax-checked and size-checked before it's written. | Nemotron 3 Super |
| **Repair** | A tool loop (`read_file`, `grep`, `apply_patch`, `rewrite_file`, `run_tests`, `search_docs`, `reinstall`) fixes whatever still fails. When progress stalls, **Ultra re-plans** from the current diff. | Super, plus Ultra on escalation |
| **Verify** | Anti-cheat checks against the real sandbox state (below). | none |
| **PR** | A PR description with a change table that cites the migration-guide rule behind each edit. | Nemotron 3.5 Lightning |

### Trust: a green suite only counts if it was earned

Agents under pressure delete tests, skip them, pin the old version back, or hide errors. Greenlight enforces these rules **in the tool layer**, and verifies them afterwards from the sandbox, not from what the model claims:

- every test that passed at baseline still passes
- the target major version is actually installed
- the upgrade pin is still in the manifests (rolling it back is refused at edit time)
- tests are the contract: a test file may be edited only to follow a renamed/moved API it uses directly
  (e.g. `from pydantic import BaseSettings`). Every assertion, `pytest.raises`, test function and marker
  must survive (an edit that deletes or weakens one is refused at edit time and re-audited from git)
- no module named after the library (a fake `pydantic.py` that hijacks the import is refused)
- the test count didn't drop, and no test is newly skipped
- no compatibility shims (e.g. `pydantic.v1`)
- no new `type: ignore` / `noqa` / bare `except: pass` (reported)

The tool layer also refuses repeated identical calls, which stops the loops agents fall into.

### Cost safety: it can't run up your bill

Token Factory is postpaid, so we built a **hard budget guard**. Every call's worst-case cost is reserved *before* it's sent, priced from the live per-token rates. Calls that would cross the global, daily or per-run cap are refused.

The ledger is crash-safe:
- every write is fsync'd
- a torn line after a power cut counts *as spend*
- an unsettled reservation counts at its worst case

So a crash can only make the guard stricter. Run `greenlight budget` to see spend against the caps.

## How we use NVIDIA Nemotron on Nebius Token Factory

We route each job to the cheapest model that does it well. Every call goes through one OpenAI-compatible client pointed at `https://api.tokenfactory.nebius.com/v1/`:

| Model (Token Factory ID) | Role | Why |
|---|---|---|
| `nvidia/Nemotron-3-Ultra-550b-a55b` | Planner, and re-planner when stuck | Best reasoning, called 1–3× per run, with reasoning on |
| `nvidia/nemotron-3-super-120b-a12b` | Code editor (bulk migration plus tool loop) | Reliable tool calling and idiomatic code at about a third of Ultra's price |
| `nvidia/Nemotron-3_5-Lightning` | Turns migration guides into rule sheets, writes PR text | $0.06/$0.24 per 1M tokens at ~300 tok/s, ideal for long-document extraction |

- Reasoning is turned on per role (`chat_template_kwargs.enable_thinking`).
- Every call is logged with tokens, $ and latency, and shown live in the UI's routing panel.

**Where Token Factory sped us up:**
- One API key gave us every Nemotron tier, so we could move each role between models with a one-line change.
- Ultra's speed (~520 tok/s) made reasoning-heavy planning cheap enough to run on every upgrade.

**Token Factory Sandboxes:**
- `greenlight/executor/contree.py` runs every command as a Sandboxes operation, chaining immutable images, so checkpoints and branches are free.
- Beta access was requested on Oct 10. Until it's granted, the same `Executor` interface runs on local Docker (`executor/docker.py`).

## Results (all on NVIDIA Nemotron via Nebius Token Factory)

**Eval set:** 12 real public repositories stuck on an old major version.
- Each repo is pinned to a commit.
- Each one passed a free precheck: its tests pass at baseline and break after the bump. Repos whose old environment can't even be installed were dropped from the set, and that is stated here rather than hidden.
- The table shows the **most recent Nemotron result for every repo**. Pass 1 ran all 12. Pass 2 re-ran five of them after harness fixes: shorter tracebacks, a lock race, and longer repair rounds.
- Data: `evals/results/eval-official/` (combined), `eval-nemotron/` (pass 1) and `eval-nemotron-2/` (pass 2).

| Repo | Upgrade | Result | Baseline tests passing after | Cost | Time | Pass |
|---|---|---|---|---|---|---|
| engorgio | pydantic 1.10 → 2.14 | ✅ green | 55/55 | $0.40 | 5m37s | 2 |
| blocklib | pydantic 1.10 → 2.14 | ✅ green | 40/40 | $0.20 | 3m16s | 1 |
| kubedeployer | pydantic 1.10 → 2.14 | ✅ green | 36/36 | $0.37 | 4m52s | 1 |
| terka | SQLAlchemy 1.4 → 2.0 | ✅ green | 33/33 | $0.09 | 1m59s | 1 |
| queueing-tool | numpy 1.26 → 2.4 | ✅ green | 27/27 | $0.11 | 3m59s | 2 |
| nsopy | numpy 1.26 → 2.4 | ✅ green | 26/26 | $0.01 | 37s | 1 |
| pydantic-vault | pydantic 1.10 → 2.14 | ◐ partial | 35/43 | $0.66 | 8m07s | 2 |
| boardgamebuilder | pydantic 1.10 → 2.14 | ✗ | 39/95 | $0.64 | 5m45s | 1 |
| bdantic | pydantic 1.10 → 2.14 | ✗ | 15/43 | $0.64 | 13m58s | 1 |
| clidantic | pydantic 1.10 → 2.14 | ✗ | 10/23 | $0.64 | 6m14s | 1 |
| noteql | SQLAlchemy 1.4 → 2.0 | ✗ | 0/11 | $0.46 | 6m12s | 2 |
| essential-sqlalchemy | SQLAlchemy 1.4 → 2.0 | ✗ | 0/26 | $0.64 | 8m45s | 2 |

**6 of 12 upgrades are fully green with every anti-cheat check passing, plus 1 partial.**
- Median cost per green upgrade: **$0.15**. Median time: **3m37s**.
- Both passes together cost **$7.30**. Super (editing) is about 95% of it; Ultra's planning is about 5%; Lightning's doc digestion and PR writing cost fractions of a cent.
- The failures are the hard cases:
  - Four repos stopped at the $0.75 per-run cap while still improving: three pydantic 1 repos built on removed internals (`ModelField`, `__root__` models, private attributes) and pydantic-vault.
  - Two SQLAlchemy 1.4 repos that execute raw SQL strings.
- **No failure is ever reported as a pass.** In pass 1, essential-sqlalchemy's edits made 8 tests stop running, and verification caught it.

**What we learned:**
- Nemotron 3 Super makes small, careful edits, one tool call per turn. Multi-file migrations take it many steps.
- One-shot whole-file rewrites (the *Migrate* stage) were the biggest single improvement. On the bundled example they cut cost from $0.20 to $0.04 and halved wall time.
- Import errors surface one at a time. So the *repair rounds* treat "the error changed" as progress, even before any test passes.
- To save credit, we developed the agent loop against cheaper stand-in models served through a local OpenAI-compatible proxy (`GREENLIGHT_BACKEND=standin`). Every number above is from Nemotron on Token Factory.

## Run it yourself

Requirements: Python 3.11+, Docker, a Nebius Token Factory API key, and a Tavily API key.

```bash
git clone https://github.com/manuvamp/greenlight && cd greenlight
uv venv && uv pip install -e ".[dev]"
cp .env.example .env            # add NEBIUS_API_KEY and TAVILY_API_KEY
docker build -t greenlight-runner runner/

# upgrade the bundled example project
greenlight upgrade examples/pydantic-v1-shop pydantic@2 --show-diff

# or any public repo at a commit
greenlight upgrade https://github.com/org/repo pydantic@2 --ref <sha>

greenlight budget               # spend against the caps
python evals/run.py --precheck  # validate the eval set without model calls ($0)
python evals/run.py             # full eval → evals/results/<tag>/scoreboard.json
```

To run the web app:

```bash
cd web && npm install && npm run build && cd ..
uvicorn server.app:app --port 8080
```

Replays are always available. Live runs need `GREENLIGHT_LIVE=1` and `GREENLIGHT_ACCESS_CODE`.

## Repository layout

```
greenlight/   agent: orchestrator, model router + budget guard, research, tools, verify, workspace, executors
server/       FastAPI: replays, live runs (SSE), scoreboard, static UI
web/          React UI: run view, model-routing panel, diff viewer, scoreboard
evals/        dataset + runner + results
examples/     a small pydantic v1 project for demos
runner/       sandbox toolchain image (git, uv, Python 3.9–3.12)
```

## Feedback

See [FEEDBACK.md](FEEDBACK.md) for notes on Token Factory, Sandboxes and Nemotron.

## License

MIT
