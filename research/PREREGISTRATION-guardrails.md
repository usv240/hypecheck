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

Run 2026-10-22 from us-east-1:
`python research/guardrails_baseline.py --wa-dir data`. One temporary guardrail
(`hypecheck-grounding-baseline-*`) was created and deleted in the same run. Per-item scores are in
`results/guardrails/{train,test}_items.jsonl`; the summary is in `results/guardrails/summary.json`.

| Measure | Bedrock Guardrails (grounding) | Strands Decider 2B |
|---|---|---|
| AUROC, exaggerates vs not (test, n = 563) | **0.503** | **0.716** |
| AUROC gap, Decider − Guardrails, paired bootstrap 95% CI | | **+0.214 (0.142–0.289)** |
| False flags on `same` at α = 0.10 | 13.3% | 6.7% |
| Recall on exaggerates at α = 0.10 | 13.9% | 38.5% |
| Latency per call (p50 / p95) | 243 / 359 ms (managed API) | 160 ms laptop GPU · ~0.9 s our CPU server |
| Cost | $0.10 per 1,000 sentences (664 text units, $0.066 for the whole run) | $0 in API fees ($0.18 per 1,000 on our CPU server) |

| Prediction | Result | Hit? |
|---|---|---|
| G1: AUROC 0.50–0.65, below 0.716 | 0.503 | yes (at the bottom of the range) |
| G2: the CI of the gap is above 0 | 0.142–0.289 | yes |
| G3: recall below 38.5% | 13.9% | yes |
| G4: false flags on `same` 3–15% | 13.3% | yes |

**How to read it:**
- **On this task the grounding check is at chance level.** Its grounding scores are low for nearly
  every press release, because a release paraphrases its paper rather than quoting it. The median
  is 0.08 for faithful releases and 0.09 for exaggerating ones; about a quarter of each scores
  0.01 or less. The conformal threshold therefore sits at an overclaim score of 0.99, and what it
  flags is close to random.
- **This is not a verdict on Guardrails in general.** The grounding check is built to catch facts
  that a RAG answer adds beyond its retrieved source. It is not built for changes in claim strength
  between two texts that both paraphrase the same finding. The result says the two tools solve
  different problems, and that this problem needs a decision model asked the specific question.
- **Product decision, as pre-registered:** Guardrails' AUROC is below Decider's, so the README and
  article report it as an AWS-native baseline that Decider beats on this task, with the CI. A
  natural combination in production is Guardrails for invented facts plus HypeCheck for inflated
  strength. That combination was not tested.
