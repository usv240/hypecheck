# Pre-registration: wording of the strength question, selected on train only

Written 2026-10-17, **before running**. Results are appended below the line.

## Why

Recall at α = 0.10 is 39%. The `criteria` descriptions "carry most of the signal" (Decider docs),
and the current wording was written once, untested. Four fixed variants are compared.

## Variants (fixed before running)

- **V0**: the current `STRENGTH_Q` in `decision_pattern/fidelity.py`.
- **V1 cue words**: V0 plus explicit cue lists per level (modal verbs → conditional; present-tense
  verbs of effect → direct; "associated/linked/more likely" → correlational).
- **V2 coder framing**: instructions framed as the InSciOut coding task ("as a science-communication
  coder would classify it"), with the levels defined as in Sumner et al.'s coding guide.
- **V3 = V1 with a one-line state prefix** ("A sentence from a health press release or paper:").

## Data and rule

- Selection on the W&A **train** split only (100 pairs, 22 exaggerates). The test split is not touched.
- Score = V2 strength-compare, as in the product.
- Metrics on train: exaggerates-vs-not AUROC (primary), 3-class macro-F1 (secondary).
- **Adopt** the best variant only if its train AUROC beats V0's by ≥ 0.03. If adopted, run the test
  split once with it and refit the conformal threshold on train; report both old and new test numbers.
- If nothing clears the bar, V0 stays and the test split is not re-run.

## Prediction

At most one variant clears the bar; V1 is the most likely. If adopted, test AUROC moves from 0.716 to
0.72–0.76 and recall at α = 0.10 from 39% to 40–48%.

---

## Results (appended after the run)

Run 2026-10-17, train split (n = 100), score = strength-compare.

| Variant | Train AUROC | Train macro-F1 |
|---|---|---|
| V0 (current) | 0.712 | 0.510 |
| V1 cue words | 0.722 | 0.602 |
| V2 coder framing | 0.585 | 0.392 |
| V3 = V1 + state prefix | **0.741** | 0.602 |

- Best is V3, gain over V0 = **0.0286**, below the pre-registered 0.03 bar. **Not adopted.** V0 stays; the test split was not re-run.
- The secondary metric (macro-F1 +0.09) is tempting, but it was declared secondary and the bar was on AUROC. Changing the rule after seeing the numbers is what pre-registration exists to prevent.
- Prediction partly held: one variant came close, V1-style cue words helped, and the coder framing hurt badly.
- V3 is the first thing to try in a follow-up with a larger calibration set.
