# Greenlight eval: eval-nemotron

editor=super-first model=routed research=on precheck=False

| case | lib | status | baseline | final | iters | esc | $ | s | headline |
|---|---|---|---|---|---|---|---|---|---|
| bdantic | pydantic | failed | 43/44 | 15/44 | 4 | 1 | 0.640 | 838 | 15/43 baseline tests pass; verification failed |
| blocklib | pydantic | green | 40/40 | 40/40 | 2 | 0 | 0.197 | 196 | pydantic 1.10.26 → 2.14.0: all 40 baseline tests pass |
| boardgamebuilder | pydantic | failed | 95/96 | 39/96 | 3 | 0 | 0.638 | 345 | 39/95 baseline tests pass; verification failed |
| clidantic | pydantic | failed | 23/34 | 10/34 | 5 | 1 | 0.638 | 374 | 10/23 baseline tests pass; verification failed |
| engorgio | pydantic | partial | 55/55 | 48/55 | 5 | 1 | 0.372 | 289 | 48/55 baseline tests pass after migration |
| essential-sqlalchemy | sqlalchemy | failed | 26/26 | 0/18 | 2 | 0 | 0.376 | 1076 | 0/26 baseline tests pass; verification failed |
| kubedeployer | pydantic | green | 36/42 | 36/42 | 4 | 2 | 0.372 | 292 | pydantic 1.10.2 → 2.14.0: all 36 baseline tests pass |
| noteql | sqlalchemy | failed | 11/11 | 0/11 | 3 | 2 | 0.450 | 340 | 0/11 baseline tests pass; verification failed |
| nsopy | numpy | green | 26/33 | 26/33 | 0 | 0 | 0.011 | 37 | numpy 1.26.4 → 2.4.6: all 26 baseline tests pass |
| pydantic-vault | pydantic | failed | 43/43 | 34/43 | 5 | 1 | 0.640 | 401 | 34/43 baseline tests pass; verification failed |
| queueing-tool | numpy | error | 27/54 | / | 3 | 0 | 0.614 | 360 | PermissionError: [Errno 13] Permission denied: 'C:\\Users\\cocat\\.greenlight\\ledger.lock |
| terka | sqlalchemy | green | 33/33 | 33/33 | 0 | 0 | 0.085 | 119 | sqlalchemy 1.4.0 → 2.0.54: all 33 baseline tests pass |

**green 4/11** (rate 36%) · median $0.1412 · median 157.2s · total $5.0328
