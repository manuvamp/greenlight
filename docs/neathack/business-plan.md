# Greenlight: business plan

Inputs and their sources: [`business-inputs.md`](business-inputs.md). Unit costs are measured from real runs, not guessed.

## The business in one paragraph
Greenlight Cloud is a GitHub App that turns red "bump to the next major version" PRs into green ones: it migrates the
code, proves the project's own tests pass, and opens a PR that cites the migration guide. Teams pay a flat monthly fee
and only pay overage for upgrades that end green. Open-source repos get a free tier, which is the acquisition funnel.

## Pricing
| Plan | Price | Included |
|---|---|---|
| Open source | $0 | public repos, 5 runs / month |
| Team | $99 / month | 10 private repos, 25 runs / month |
| Business | $499 / month | unlimited repos, 150 runs / month, SSO, audit log |
| Overage | $6 per green PR | failed runs are free |

Blended revenue per paying team (85% Team, 15% Business): **$159 / month**.

## Costs
**Per upgrade run: ≈ $0.57.** LLM $0.50 (Nemotron on Nebius Token Factory: $0.04 small repo, $0.45–0.75 real repo,
measured), sandbox compute $0.02, web research $0.05 (rule sheets are cached per library and version).
Assuming teams use 60% of their included runs, COGS is ≈ $15 per paying team per month → **≈ 90% gross margin**.

**Fixed:** $500 / month (hosting, observability, CI, tools), plus a $4,000 / month founder salary from month 7.

## Revenue and runway (starting cash $15,000, no outside funding)
Growth: 3 paying teams in month 1, +40% / month to month 6, +20% to month 12, +10% after; 3% monthly churn.

| month | paying teams | MRR | COGS | fixed costs | net | cash |
|---|---|---|---|---|---|---|
| 1 | 3 | $477 | $45 | $500 | −$68 | $14,932 |
| 3 | 6 | $954 | $90 | $500 | $364 | $15,372 |
| 6 | 14 | $2,226 | $209 | $500 | $1,517 | $18,482 |
| 7 | 16 | $2,544 | $239 | $4,500 | −$2,195 | $16,286 |
| 9 | 22 | $3,498 | $329 | $4,500 | −$1,331 | $13,192 |
| 11 | 30 | $4,770 | $449 | $4,500 | −$179 | $12,114 |
| 12 | 34 | $5,406 | $509 | $4,500 | $397 | $12,511 |
| 18 | 51 | $8,109 | $763 | $4,500 | $2,846 | $23,249 |
| 24 | 75 | $11,925 | $1,122 | $4,500 | $6,303 | $51,703 |

- **Runway:** cash never drops below ~$12,100 (month 11), so the plan is fully funded. Even at zero revenue the fixed
  costs alone give 30 months of runway before the salary starts, and ~3 months after.
- **Break-even with a founder salary:** month 12 (34 paying teams).
- **Biggest risk:** the green rate on real repos (6/12 green on Nemotron today, 11/12 with stronger stand-in models).
  Every point of green rate is revenue, because customers only pay overage for green PRs. Tracing every run in neatlogs
  and fixing what the traces show is how that rate goes up; see [`EVIDENCE.md`](EVIDENCE.md).
- **What would change the plan:** LLM cost per run is the main COGS lever. The neatHack fix already cut input tokens
  ~24% on the measured pair.
