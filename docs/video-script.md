# Greenlight: demo video script (target 2:45, hard limit 3:00)

**Goal:** prove the four judging criteria with real footage of real runs on Nemotron.
- Technological Implementation: model routing, Token Factory, Tavily, sandboxed tests, the budget guard.
- Design: the polished run view.
- Impact: real open-source repos stuck on old versions.
- Idea: "read the guide, fix the code, prove it."

**Voice:** calm and confident, like a developer showing a tool they built. No hype words.

**Footage:** screen captures of the Greenlight web app (`/replay/<id>`). Every replay comes from a real run on NVIDIA Nemotron via Nebius Token Factory.

---

### 1. Hook (0:00–0:15)
**On screen:**
- A GitHub-style PR titled "Bump pydantic from 1.10 to 2.14", status red ✗ with 36 failing checks.
- Cut to the text "Dependabot opened it. Nobody merged it."

**VO:** "Every team has this pull request. The bot bumped a major version, the tests went red, and it's been sitting there for months, because fixing it means reading a migration guide and rewriting code by hand."

### 2. What Greenlight is (0:15–0:30)
**On screen:**
- The Greenlight home page hero, slow push-in.
- Overlay pipeline chips appear one by one: Baseline → Bump → Research → Plan → Migrate → Fix → Verify → PR.

**VO:** "Greenlight does that upgrade for you. It reads the official migration guide, rewrites your code, and runs your own test suite in a sandbox until it passes. Then it proves the result is real."

### 3. Real run: kubedeployer, pydantic 1 → 2 (0:30–1:25)
Replay `kubedeployer-pydantic-v2`, played at 8–16×. Callouts appear as each stage lands.

| Time | On screen (zoom on panel) | VO |
|---|---|---|
| 0:30 | Header plus Baseline: 36/36 green | "This is a real open-source repo, kubedeployer, pinned to pydantic 1. Baseline: thirty-six tests pass." |
| 0:38 | Bump: ring goes red, "import error" | "Bump to pydantic 2, and the whole suite fails to even import." |
| 0:45 | Research panel: pydantic.dev source cards, "348 rules" | "Greenlight searches the official docs with Tavily. Nemotron 3.5 Lightning turns the migration guide into hundreds of concrete rules, each one linked to its source." |
| 0:55 | Plan panel: Ultra, "thinking" | "Nemotron 3 Ultra reads the failures and every call site the rules match, and writes a migration plan." |
| 1:03 | Migrate node, then activity feed showing "rewrote … (bulk)" | "Nemotron 3 Super rewrites each file in one pass, in parallel. Then it repairs whatever still fails, using tools: read, grep, patch, run the tests." |
| 1:13 | Test ring climbs back to 36/36, green banner | "Thirty-six out of thirty-six. Green." |

### 4. Trust: it can't fake a pass (1:25–1:50)
**On screen:**
- Verify panel, checks ticking ✓ one by one: baseline tests still pass; pydantic 2.x installed; pin kept; no module shadows pydantic; test edits are API-only; no new skips; no v1 shim.
- Quick inset of the guard message: "REFUSED: … would shadow the real pydantic package."

**VO:** "Agents under pressure cheat. They skip tests, pin the old version back, or fake the library. We caught Nemotron doing exactly that in development, creating a fake pydantic module. So Greenlight enforces the rules in the tool layer, then re-checks everything from the sandbox, not from what the model claims."

### 5. Routing and cost (1:50–2:15)
**On screen:**
- Model routing panel, zoomed. The bars: Ultra (plan), Super (edit), Lightning (digest, PR).
- Overlay: "$0.37 for this upgrade", then "nsopy · numpy 1 → 2 · 37 s · $0.011".

**VO:** "Each job goes to the cheapest Nemotron model that does it well: Ultra to plan, Super to edit, Lightning to read docs and write the PR. All on Nebius Token Factory. This upgrade cost thirty-seven cents. A numpy upgrade took thirty-seven seconds and one cent. And a hard budget guard prices every call before it's sent, so an agent loop can never run up your bill."

### 6. Honest results (2:15–2:35)
**On screen:**
- Scoreboard page: 12 real repos; green, partial and failed badges; per-repo tests and cost.
- Highlight terka (SQLAlchemy 1.4 → 2.0, 33/33) and blocklib (40/40).

**VO:** "We tested on real repositories stuck on pydantic, numpy and SQLAlchemy. Six of twelve upgrades fully green on Nemotron, and every failure is reported as a failure, never as a pass."

### 7. PR and close (2:35–2:50)
**On screen:**
- PR panel: the rendered description with the change table and rule citations.
- End card: "Greenlight · NVIDIA Nemotron on Nebius Token Factory · Tavily · open source (MIT)", plus the GitHub URL.

**VO:** "And it opens the pull request, with every change linked to the rule in the official guide. Greenlight: the upgrades your bot can't do."

---

## Production notes
- Capture at 1920×1080. Use the app's playback controls; a speed of 8× fits most stages.
- Keep the replay header's cost and elapsed counters visible; they're the proof.
- The music bed is low, with no lyrics. Ducked under the VO.
- Captions are burned in at the bottom. Judges often watch muted.
- **Check the numbers before export:** kubedeployer 36/36 at $0.372; nsopy 37 s at $0.011; terka 33/33; blocklib 40/40; scoreboard 6 green of 12.
