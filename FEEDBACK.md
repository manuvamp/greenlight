# Feedback: Nebius Token Factory, Sandboxes and NVIDIA Nemotron

These are notes from building Greenlight, written down as things happened. Each item has what we saw, why it mattered, and a concrete suggestion.

## Nebius Token Factory

### 1. You can't set a spending cap, but you must keep a card on file *(highest impact)*
- **What we saw:** Onboarding requires a bank card. Billing is postpaid: once free credit runs out, the balance goes negative and the card is charged. There is no hard spending limit or budget alert in the console, and the card can't be removed.
- **Why it matters:** For hackathon builders and anyone running autonomous agent loops, this is the scariest part of the platform. A bug in an agent loop could charge the card overnight. We had to build our own crash-safe budget ledger. It prices every call before sending it and refuses calls that would cross a cap. We'd much rather have used a platform feature.
- **Suggestion:**
  - A per-project or per-key hard cap ("stop serving at $X").
  - Email alerts at 50%, 80% and 100% of credits.
  - A "credits-only" mode that rejects requests once free credit runs out instead of charging the card.

### 2. Usage and billing data lag behind real usage
- **What we saw:** Hours after our first API calls, the Usage page still said "No usage" and the trial credit showed the full $1.00.
- **Why it matters:** Builders can't check what they've actually spent, which makes the missing cap worse.
- **Suggestion:** Near-real-time usage, or at least a "last updated" timestamp. Also a usage API (`GET /v1/usage`) so tools can reconcile against it automatically.

### 3. Prices are hard to find for a specific model
- **What we saw:**
  - The Model catalog page shows context length and precision, but not prices.
  - The Organization → Prices page lists about 200 rows, and we couldn't find Nemotron in the first page.
  - In the end we read prices from the "Model endpoints" cards.
- **Suggestion:** Show $/1M in and out on the catalog and on each model card. Also make prices queryable from `/v1/models`, so routers and budget guards can stay in sync without hardcoding them.

### 4. The Nemotron reasoning toggle isn't documented
- **What we saw:** Nemotron 3 thinks by default. To turn it off we needed `extra_body={"chat_template_kwargs": {"enable_thinking": false}}`, which we only learned from other hackathon repos.
  - With thinking on and a modest `max_tokens`, `content` can come back empty: every token went to reasoning.
- **Suggestion:** Document the toggle on each Nemotron model page with an example. Also consider a first-class `reasoning: {enabled, budget}` parameter, and return `finish_reason: "length"` together with a clear hint when reasoning used up the whole budget.

### 5. Model IDs are inconsistent across docs
- **What we saw:** The cookbook lists Nano as `nvidia/nvidia-nemotron-3-nano-30b-a3b`, but `/v1/models` returns `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`. The Lightning ID uses an underscore (`Nemotron-3_5-Lightning`) while the display name uses a dot.
- **Suggestion:** Make IDs case-insensitive, or add aliases, and generate the cookbook from the live catalog.

### 6. No documented discount for repeated prompt prefixes
- **What we saw:** Agent loops resend a long, identical prefix every turn (system prompt, plan, file contents). We measured 93% of a run's cost going to editor input tokens. The docs mention KV and context caching in the inference engine, but nothing about pricing for cached tokens.
- **Suggestion:** Bill cached prefix tokens at a discount and report `cached_tokens` in `usage`. That would make multi-step agents on Token Factory much cheaper.

### 7. The promo-code form sometimes doesn't load
- **What we saw:** The first time we opened the `nebius.com/promo-code` page, the embedded HubSpot form never rendered and only the newsletter form showed. A reload fixed it.
- **Suggestion:** Show a fallback link, or a "having trouble?" message.

## Token Factory Sandboxes
- **Positive:** The docs are excellent: explicit lifecycle, result-image rules, a "try two fixes and keep the passing branch" cookbook. Immutable images plus checkpoints are exactly the right model for coding agents.
- **Friction:**
  - Access is gated behind a beta form, a Microsoft Form linked from the console. Hackathon tracks that explicitly name Sandboxes ("agents that write, run, and test code") would benefit from automatic access for registered participants.
  - There's no JavaScript SDK. Python and REST only.
  - The quickstart uses `Contree()` with environment variables, while the SDK reference shows `ContreeSync(config|base_url, token)`. One canonical constructor would help.

## NVIDIA Nemotron models (our measurements)
- **Nemotron 3 Ultra:** an excellent planner. Fast for its size (the endpoint page says about 520 tok/s), and its JSON plans were consistently usable.
- **Nemotron 3 Super:** a reliable tool-calling editor. It recovered from failed patches on its own and produced idiomatic pydantic v2 code (`RootModel`, `model_validator(mode="after")`, `pydantic-settings`).
- **Nemotron 3.5 Lightning:** remarkable price and speed ($0.06/$0.24 per 1M, about 300 tok/s). It was ideal for digesting docs (348 grounded migration rules from the pydantic guide for under $0.01). As an autonomous code editor it stalled where Super succeeded, so we route it to digestion and writing tasks.
- **Degenerate loops:** With Ultra as the editor, it repeated identical `read_file`/`search_docs` calls. We added a repeat guard in our tool layer. Documenting recommended agent-loop settings (temperature, repetition handling) would help.

## Tavily
- Domain-restricted search (`include_domains`) plus `extract` in markdown is a perfect fit for finding official migration guides. The credits coupon (`BBDEVPOST`) worked instantly.
