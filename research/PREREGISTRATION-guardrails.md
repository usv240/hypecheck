# Pre-registration: Amazon Bedrock Guardrails' contextual grounding check as a baseline

Written 2026-10-22, **before any Guardrails call**. Results are appended below the line.

## Why

AWS already sells a check for "does this text stay within its source": the contextual grounding
check in Amazon Bedrock Guardrails (`ApplyGuardrail`). It returns a grounding score from 0 to 1 for
a piece of content against a grounding source. If it catches claim exaggeration as well as
Decider does, a builder should use it instead. That makes it the most relevant AWS-native
baseline, alongside Claude asked as a judge.

## Data and procedure

- **Data:** the same Wright & Augenstein 2021 pairs: 100 train and 563 test (345 `same`, 122
  exaggerates, 96 downplays).
  - Grounding source = the abstract's conclusion.
  - Content = the press-release sentence.
  - Query = the fixed question "What did the study find?".
- **The guardrail:** one temporary guardrail with only a contextual grounding filter (GROUNDING
  and RELEVANCE, threshold 0.01 so it never blocks; we only read the scores). It is deleted after
  the run.
- **Score:** overclaim score = 1 − grounding score.
- **Threshold:** fitted exactly as for Decider. Split conformal at α = 0.10 on the 78 train pairs
  that do not exaggerate; that rule is then applied once to the test set.

## Measures

**Primary:**
1. AUROC, exaggerates vs not, on test.
2. False flags on `same` at the α = 0.10 threshold.
3. Recall on exaggerates at that threshold.
4. The paired-bootstrap 95% CI of the AUROC difference (Decider minus Guardrails). The bootstrap
   uses 5,000 resamples, seed 0.

**Secondary:**
- Latency per call.
- Cost: text units × the published price.

## Predictions

| # | Prediction |
|---|---|
| G1 | Guardrails AUROC is between 0.50 and 0.65, below Decider's 0.716 |
| G2 | The AUROC gap (Decider − Guardrails) has a 95% CI above 0 |
| G3 | At α = 0.10, Guardrails' recall is below Decider's 38.5% |
| G4 | Guardrails' false flags on `same` are 3–15% (conformal should hold for it too) |

The reasoning: the grounding check is designed for facts that aren't in the source. Turning
"could be efficacious" into "is saving lives" keeps the same entities and topic, so it may still
look grounded.

## What changes the product

- **If Guardrails' AUROC ≥ Decider's** (point estimate): the README and article say so in the
  results table. They recommend Guardrails as an alternative gate and do not claim Decider is
  better at this task.
- **Otherwise:** it is reported as an AWS-native baseline that Decider beats on this task, with
  the CI.
- **Either way:** the code and per-item scores are published.

---

## Results (appended after the run)
