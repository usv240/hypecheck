# Pre-registration: do AI summaries of the same papers overclaim, and does the gate fix them?

Written 2026-10-21, **before any summary was generated**. Results are appended below the line.

## Why

Peters & Chin-Yee (2025, *R. Soc. Open Sci.* 12:241776, doi:10.1098/rsos.241776) compared 4,900
LLM summaries with the original texts:
- Several popular models broadened conclusions in 26–73% of cases.
- LLM summaries were 4.85× as likely as expert-written human summaries to contain broad
  generalisations (95% CI 3.06–7.70).
- Claude models were the most faithful they tested (−1 to 20%).

Their three types of overgeneralisation are generic, present tense and action-guiding. These map
onto our claim-strength check and advice check. If the gate works on AI summaries, its use extends
from press offices to every app that summarises research.

## Data

- **Papers:** the 85 papers HypeWatch already checked against their NIH press releases. The full
  abstract for each is re-fetched by DOI with the same chain HypeWatch uses (Europe PMC, then
  OpenAlex, then Semantic Scholar). Papers whose abstract can't be fetched are dropped and counted.
- **Summaries:** for each paper, one summary from each of:
  - Claude Sonnet 4.6 (`us.anthropic.claude-sonnet-4-6`);
  - Claude Haiku 4.5 (`us.anthropic.claude-haiku-4-5-20251001-v1:0`).
- **Settings:** Bedrock default temperature, max 300 tokens.
- **Prompt (ours, not Peters'):** "Summarize the key findings of this research abstract for a
  general audience in three sentences. Reply with the summary only."

## Scoring

The scoring is the same public rule HypeWatch uses on NIH releases, with the same thresholds:
- A summary sentence's score is min(score against the conclusion, score against the abstract's
  strongest sentence).
- BLOCK > 0.5001; REVIEW > 0.3986.

**The gate:**
- Each BLOCK sentence gets up to two Claude Sonnet 4.6 rewrites.
- A rewrite counts as fixed only if Decider scores it ≤ 0.5001 under the **same public rule**.
  This fixes the mismatch noted in the HypeWatch pre-registration, where rewrites were held to a
  stricter rule than the original flags.

## Measures

**Primary:**
1. Share of summaries with ≥ 1 BLOCK sentence, per model.
2. Per-sentence BLOCK rate, per model, compared with the NIH releases' rate on the same papers:
   2.93% (18 of 615 sentences).
3. After the gate: share of flagged summaries with no BLOCK sentence left.

**Exploratory (no prediction):**
- Advice inflation, the document-level `advice_inflated` > 0.5. It corresponds to Peters'
  "action-guiding" type.

## Predictions

| # | Prediction |
|---|---|
| P1 | 5–25% of Sonnet 4.6 summaries have ≥ 1 BLOCK sentence |
| P2 | Haiku 4.5's per-sentence BLOCK rate is higher than Sonnet 4.6's |
| P3 | Both Claude models' per-sentence BLOCK rates are ≥ the NIH press office's 2.93% on the same papers |
| P4 | After the gate, ≥ 85% of flagged summaries have no BLOCK sentence left |

## What changes the product

- **If either model has ≥ 5% of summaries with a BLOCK:** the site and article add "AI summaries"
  as a second use case, with these numbers.
- **If both are below 5%:** we report that Decider agrees with Peters & Chin-Yee that Claude
  summarises faithfully, and we do not market an AI-summary use case.
- **Either way:** this measures what Decider flags. There are no human labels, so it is not ground
  truth.

---

## Results (appended after the run)
