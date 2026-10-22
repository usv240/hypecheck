# Pre-registration: which Decider 2B checkpoint, and does an ensemble catch more?

Written 2026-10-23, **before any of these runs**. Results are appended below the line.

## Why

Recall at the strict threshold is our weakest number: 38.5% (95% CI 30–47%). HypeCheck uses
`strands-decider-2B-qwen3.5-v1-2610`, the current reference checkpoint. Strands Labs publishes two
other 2B Decider checkpoints, `strands-decider-2B-hobson-v21` and `strands-decider-2B-hobson-v19`,
and other entries in this hackathon use them. All three are "Decider 2B", so all are within the
rules. We test whether one of them, or an average of two, ranks overclaims better.

## Candidates

Every candidate uses the same strength question (`decision_pattern/fidelity.py`, `STRENGTH_Q`) and
the same score: P(release rung > abstract rung).
- **C0:** v1-2610, the current checkpoint. Its train scores already exist.
- **C1:** hobson-v21.
- **C2:** hobson-v19.
- **E:** the mean of C0's score and the score of whichever of C1/C2 has the higher train AUROC.

## Procedure

1. **Train split only (100 pairs).** Score C1 and C2 on the server, CPU, one at a time beside the
   live demo. Compute train AUROC for exaggerates vs not, for C0, C1, C2 and E.
2. **Pick one candidate:** the one with the highest train AUROC. If it isn't C0, it must beat C0's
   train AUROC by ≥ 0.03. Otherwise C0 stays and **no test run is made**.
3. **Test once (563 pairs).** Fit the conformal threshold at α = 0.10 on the picked candidate's 78
   non-exaggerating train pairs. Then measure on test:
   - AUROC;
   - recall on exaggerates;
   - false flags on `same` and on all 441 non-exaggerating pairs;
   - a paired-bootstrap 95% CI of the recall and AUROC differences against C0 (5,000 resamples,
     seed 0).

## Adoption rule (decided now)

The product switches to the picked candidate only if, on test, all three hold:
- recall at α = 0.10 rises by **≥ 5 points**;
- false flags on all non-exaggerating pairs stay **≤ 10%** (the conformal promise);
- AUROC does not fall.

Otherwise C0 stays and the result is reported as "not adopted".

## Predictions

| # | Prediction |
|---|---|
| K1 | No single checkpoint beats C0's train AUROC by ≥ 0.03 |
| K2 | The ensemble E has the highest train AUROC of the four |
| K3 | If a test run happens, the recall gain is under 5 points, so the switch is not adopted |

The reasoning: C0 is the newest reference checkpoint and was trained with rule-application rows.
Averaging two checkpoints usually ranks slightly better but rarely moves recall at a fixed
false-flag rate by much.
