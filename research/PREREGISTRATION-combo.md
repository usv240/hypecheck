# Pre-registration: combining the three zero-shot signals

Written 2026-10-17, **before running**. Results are appended below the line.

## Why

Recall at a 10% false-flag budget is 39% with V2 alone. V1 (direct pair choice) and V3 (pair noul) carry partly independent signal.

## Method

1. Run V1, V2 and V3 on the W&A **train** split (100 pairs, 22 exaggerates).
2. Fit a logistic regression with features `[v1_p_exag, v2_p_exag, v3_p_overclaim]` and L2 regularisation C = 1.0, fixed in advance.

## Adoption rule

- Decided on train only, by leave-one-out cross-validation.
- Adopt the combination if its LOO AUROC on train exceeds V2's train AUROC by ≥ 0.02.
- Only then score it on test, once, with the conformal threshold refitted on train LOO scores.
- If it is not adopted, V2 stays and test is not scored with the combination.

## Prediction

The combination improves test AUROC from 0.716 to 0.73–0.78, and recall at α = 0.10 from 39% to 42–50%.

---

## Results (appended after the run)

Run 2026-10-17. Train split, n = 100: V1 AUROC 0.645, V2 0.712, V3 0.682.

| Train metric | Value |
|---|---|
| Combination, LOO AUROC | 0.686 |
| V2 alone, AUROC | 0.712 |
| Adopt (≥ +0.02 needed)? | **no** |

- **Not adopted.** V2 stays the gate's score.
- The test split was not scored with the combination.
- Prediction failed; the cause is likely 100 training pairs being too few to fit three correlated signals.
- Recall at α = 0.10 therefore stays at the measured 39% (95% CI 30–47%).
