# Greenlight: business inputs (for cfo.ai)

Every per-run cost below comes from measured runs (`~/.greenlight/ledger.jsonl`, `evals/results/`); prices, fixed costs, growth and cash are planning assumptions.

## Product
Greenlight Cloud: a GitHub App that opens **verified** dependency-upgrade PRs. Point it at a repo and a
major version (`pydantic@2`, `sqlalchemy@2`, ...). It bumps the pin, migrates the code until the project's
own test suite passes again, refuses to weaken tests, and opens a PR with the diff, the rules it applied and
the before/after test results. You only pay for runs that end green.

Who buys: engineering teams with Python services stuck on an old major version (Dependabot opens the bump PR,
CI goes red, nobody has time to fix it). Buyer: engineering manager / platform lead.

## Pricing
| Plan | Price | Included |
|---|---|---|
| Open source | $0 | public repos, 5 upgrade runs / month |
| Team | $99 / month | 10 private repos, 25 upgrade runs / month |
| Business | $499 / month | unlimited repos, 150 runs / month, SSO, audit log |
| Overage | $6 per green PR | runs that don't end green are free |

## Unit costs (per upgrade run)
| Item | Cost | Source |
|---|---|---|
| LLM (Nemotron on Nebius Token Factory) | $0.04 small repo, $0.45–0.75 real repo, **$0.50 average** | eval ledger |
| Sandbox compute (Docker on EC2, ~8 min of a c6i.large) | $0.02 | AWS on-demand price |
| Web research (Tavily, rule sheets cached per library/version) | $0.05 | 8 credits, cached after first run |
| **Total COGS per run** | **≈ $0.57** | |

Team plan at full use: 25 runs × $0.57 = $14.25 COGS on $99 → **86% gross margin**.

## Fixed monthly costs
| Item | Cost |
|---|---|
| Hosting (API, queue, DB, GitHub App) | $250 |
| Observability (neatlogs Pro), CI, tools | $200 |
| Domain, email, misc | $50 |
| Founder salary (from month 7) | $4,000 |

## Growth assumptions
- Launch on GitHub Marketplace + Hacker News in month 1; OSS plan as the funnel.
- Paying teams: 3 in month 1, +40% month over month to month 6, +20% after.
- Plan mix: 85% Team, 15% Business. Logo churn 3% / month.

## Cash
- Starting cash: $15,000 (planning assumption). No outside funding assumed.
