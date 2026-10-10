# Greenlight eval: eval-nemotron-2

editor=super-first model=routed research=on precheck=False

| case | lib | status | baseline | final | iters | esc | $ | s | headline |
|---|---|---|---|---|---|---|---|---|---|
| engorgio | pydantic | green | 55/55 | 55/55 | 3 | 1 | 0.400 | 337 | pydantic 1.10.26 → 2.14.0: all 55 baseline tests pass |
| essential-sqlalchemy | sqlalchemy | failed | 26/26 | 0/3 | 5 | 0 | 0.643 | 525 | 0/26 baseline tests pass; verification failed |
| noteql | sqlalchemy | failed | 11/11 | 0/11 | 5 | 2 | 0.458 | 372 | 0/11 baseline tests pass; verification failed |
| pydantic-vault | pydantic | partial | 43/43 | 35/43 | 4 | 0 | 0.659 | 487 | 35/43 baseline tests pass after migration |
| queueing-tool | numpy | green | 27/59 | 54/59 | 1 | 0 | 0.105 | 239 | numpy 1.26.4 → 2.4.6: all 27 baseline tests pass |

**green 2/5** (rate 40%) · median $0.2528 · median 287.8s · total $2.2662
