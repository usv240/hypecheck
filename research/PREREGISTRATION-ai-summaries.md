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

Run 2026-10-21 on the EC2 demo box (CPU Decider), with
`python -m research.ai_summary_eval`. All 85 abstracts were fetched; none was skipped. Per-item
output is in `results/ai-summaries/items.jsonl` (SHA-256 listed in `results/MANIFEST.json`). The
summary is in `results/ai-summaries/summary.json`.

| Measure | Sonnet 4.6 | Haiku 4.5 | NIH press office, same papers |
|---|---|---|---|
| Summaries with ≥ 1 BLOCK sentence | **11.8%** (10 of 85) | **10.6%** (9 of 85) | 15.3% of releases (longer texts: up to 8 sentences) |
| Per-sentence BLOCK rate | 4.3% (11 of 256) | 3.9% (10 of 255) | 2.9% (18 of 615) |
| Summaries with ≥ 1 REVIEW sentence | 17.6% | 21.2% | — |
| Flagged summaries left with no BLOCK after the gate | **90%** (9 of 10) | **89%** (8 of 9) | — |
| Exploratory: advice inflated (> 0.5) | 8.2% | 2.4% | — |

| Prediction | Result | Hit? |
|---|---|---|
| P1: 5–25% of Sonnet summaries have a BLOCK | 11.8% | **yes** |
| P2: Haiku's per-sentence BLOCK rate is higher than Sonnet's | 3.9% vs 4.3% | **no** |
| P3: both models' per-sentence rates are ≥ the NIH rate of 2.93% | 4.3% and 3.9% | **nominally yes, but within chance** (Fisher exact vs NIH: p = 0.31 and 0.53) |
| P4: ≥ 85% of flagged summaries are fixed by the gate | 90% and 89% | **yes** |

**Decision.** Both models exceed the 5% bar, so AI summaries are added to the site and article as
a second use case.

**How to read it:**
- **What the flags look like.** The paper on medication for opioid use disorder in jail reports
  that it "was associated with … decreased risks of overdose, death from any cause". Both Claude
  summaries said expanding it "can save lives". Claude's rewrites under the gate ("may be associated
  with reduced risks of overdose, death, and reincarceration") passed Decider's re-check.
- **Rewrites now pass about 90% of the time, against 67% in HypeWatch.** That supports the
  explanation given in the HypeWatch pre-registration: there, rewrites were held to a stricter
  rule than the flags. Here both use the same rule. This is a post-hoc reading, not a test.
- **Claude is no worse than the press office per sentence.** The gap is within chance, which fits
  Peters & Chin-Yee's finding that Claude is the most faithful family they tested. The claim we
  make is narrower: about 1 in 9 Claude summaries contains a sentence our gate would stop, and the
  gate fixes about 9 in 10 of those.
- **No ground truth.** These are Decider's flags. There are no human labels, so precision on this
  set is unknown. On the labelled benchmark, about 58% of BLOCKs at this threshold are real
  overclaims.
