# Devpost submission: Greenlight

**Project name:** Greenlight
**Tagline:** The breaking dependency upgrades Dependabot can't do, done by Nemotron and proven by your own tests.
**Track:** Coding and Agentic Engineering
**Built with:** NVIDIA Nemotron 3 Ultra, Nemotron 3 Super, Nemotron 3.5 Lightning, Nebius Token Factory, Token Factory Sandboxes (Contree SDK; executor built, beta access pending), Tavily, Python, FastAPI, React, TypeScript, Docker, uv, pytest

---

## Inspiration

Every engineering team has the same pull request: *"Bump pydantic from 1.10 to 2.x"*. A bot opened it, the tests went red, and nobody has touched it in months.

Version-bump bots stop exactly where the work starts. A major upgrade like pydantic 1→2, numpy 1→2, pandas 1→2 or SQLAlchemy 1.4→2.0 means:
1. reading a long migration guide
2. finding every call site
3. rewriting code
4. rerunning the tests over and over

So teams stay on unsupported versions, and security debt piles up.

The work is tedious but well specified. That's exactly the loop an agent should run, as long as you can **trust** what it did.

## What it does

Point Greenlight at a repository and a target, e.g. `greenlight upgrade <repo> pydantic@2`. It runs these steps:

1. **Baseline:** clones the repo into an isolated sandbox, installs it (including Poetry, Hatch or PEP 735 dev dependencies) and runs the test suite. The tests that pass become the contract.
2. **Bump:** rewrites the version pin in every manifest and reinstalls. Now the tests are red.
3. **Research:** Tavily finds the library's official migration guide, and **Nemotron 3.5 Lightning** turns it into a rule sheet: hundreds of concrete "old API → new API" rules, each with a grep pattern and a link to its source. Rules that don't appear in the source text are discarded.
4. **Plan:** **Nemotron 3 Ultra** (reasoning on) reads the failures plus every call site the rules match, and writes a migration plan.
5. **Migrate:** **Nemotron 3 Super** rewrites each planned file in one pass, in parallel.
6. **Repair:** Super rewrites the files the failing tracebacks point at, round after round, as long as the errors keep changing. Then it switches to a tool loop (read, grep, patch, run the tests, search the docs). When progress stalls, Ultra re-plans.
7. **Verify:** anti-cheat checks run against the sandbox state.
8. **PR:** Lightning writes a pull-request description that cites the migration-guide rule behind each change.

The web app replays every run event by event: a live test meter, the stage timeline, Tavily sources, the plan, a diff viewer, the verification checklist, and a **model-routing panel** that shows exactly which Nemotron model did what, with tokens and cost.

## How we built it

- **Nemotron routing on Token Factory.** One OpenAI-compatible client, with each job sent to the cheapest model that does it well:
  - Ultra for planning (1–3 calls per run)
  - Super for editing
  - Lightning for long-document extraction and writing (it's $0.06/$0.24 per 1M tokens at around 300 tokens/s)
  - Reasoning is switched on per role. Every call is priced and logged.
- **Tavily.** A domain-restricted search of the library's official docs plus `extract` in markdown gives us the migration guide. There's also a `search_docs` tool the editor uses when a failure isn't covered by the rules.
- **Sandboxes.** An `Executor` interface with two backends:
  - Token Factory Sandboxes (Contree): immutable images chain naturally into checkpoints and branches. The code is written; we're waiting on beta access.
  - Docker, which is what the reported runs used.
- **Trust layer.** The rules are enforced *in the tools*, not in the prompt:
  - Edits that delete or weaken an assertion, remove a test, or add a skip are refused. Tests may only be migrated to the new API.
  - Edits that roll back the version pin are refused.
  - A file named after the library (a fake `pydantic.py` that hijacks the import) is refused.
  - Repeated identical tool calls are refused.
  - Afterwards, verification re-checks everything from git and the sandbox.
- **A hard budget guard.** Token Factory is postpaid and there's no spending cap in the console, so we built one:
  - Every call's worst-case cost is reserved *before* it's sent.
  - Calls are refused past the global, daily or per-run cap.
  - The ledger is crash-safe: fsync'd, torn writes after a power cut count as spend, and unsettled reservations count at their worst case.
- **An honest eval harness.** Real public repos stuck on old majors, pinned to commits. A free precheck mode keeps only repos whose baseline is green and whose bump turns them red. Results go to a scoreboard.

## Results (NVIDIA Nemotron on Nebius Token Factory)

We tested on 12 real public repositories stuck on pydantic 1, numpy 1 or SQLAlchemy 1.4. These are the latest Nemotron results per repo.

- **6 fully green** with every anti-cheat check passing:
  - engorgio, pydantic: 55/55
  - blocklib, pydantic: 40/40
  - kubedeployer, pydantic: 36/36
  - terka, SQLAlchemy 1.4→2.0: 33/33
  - queueing-tool, numpy: 27/27
  - nsopy, numpy: 26/26, in 37 s for $0.011
- **1 partial:** pydantic-vault, 35/43.
- The rest are honest failures: hard pydantic-internals rewrites, and raw-SQL SQLAlchemy code. One run made 8 tests stop running; verification caught it and reported a failure, not a pass.
- Median cost per green upgrade: **$0.15**. Both eval passes together cost **$7.30**.

## Challenges we ran into

- **Agents cheat under pressure.** During development Nemotron created a top-level `pydantic.py` that re-exported pydantic v2 under the v1 names, so the import "worked". That's why shadowing is now refused in the tool layer and re-checked in verification.
- **Import errors surface one at a time.** A pydantic 1→2 migration can fail on `ConstrainedInt`, then `root_validator`, then underscore fields, while every test still reports "failed". We taught the agent that "the error changed" counts as progress.
- **Cost.** Our first agent loop cost $0.75 per repo. Most of it came from the conversation history: whole files the editor wrote kept being re-sent with every call. Compacting history, one-shot parallel rewrites and repair rounds cut the bundled example from $0.20 to $0.04.
- **Real-world repos.** Installing years-old projects reproducibly took work: Poetry dev groups, old pytest pins, optional extras that can't install, Python version fallbacks.
- **Nemotron's thinking mode.** Reasoning is on by default, and a low `max_tokens` can return empty content. We toggle it per role with `chat_template_kwargs`.

## Accomplishments that we're proud of

- Real upgrades of real repositories, verified by their own test suites, at cents per upgrade.
- A trust layer that caught a model actually trying to fake the library.
- Every number we report comes from a recorded run you can replay in the app.

## What we learned

- Model routing matters more than any single model choice. Ultra's planning was 5% of the cost, and Lightning's doc digestion cost a fraction of a cent.
- One-shot whole-file rewrites beat long tool loops for both cost and quality on multi-file migrations.
- Without a verifier, a coding agent's "tests pass" can't be trusted.

## What's next for Greenlight

- Turn on Token Factory Sandboxes, and use its checkpoints to branch parallel fix attempts and keep the green one.
- A GitHub App that picks up red Dependabot PRs automatically.
- More ecosystems: Node (React Router, Express), Django, and Pydantic-settings.

---

### Testing instructions for judges

- **Demo URL:** https://manuvamp.github.io/greenlight/. Recorded Nemotron runs replay event by event and cost nothing. Live runs are disabled on the public demo because they spend real credits; the Try page shows how they work.
- **Run it yourself:** see the README. You need Python 3.11+, Docker, a Nebius Token Factory key and a Tavily key. Then run `greenlight upgrade examples/pydantic-v1-shop pydantic@2`.
- **Eval data and run logs:** `evals/results/eval-official/` (combined), `eval-nemotron/` and `eval-nemotron-2/`.

### Feedback on Nebius and NVIDIA tools
See `FEEDBACK.md` in the repo; it's also pasted into the feedback field.

### New project
Greenlight was built from scratch during the submission period (started Oct 10, 2026).
