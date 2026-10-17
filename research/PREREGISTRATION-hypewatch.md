# Pre-registration: HypeWatch, real NIH news releases

Written 2026-10-17 while the backfill was running. Only the first 5 releases had been seen, from a
trial on archive page 0: no blocks under the strict rule, 3 review-zone sentences. Results are
appended below the line.

## Question

On real releases that we did not choose, how often does HypeCheck find a headline or opening
sentence claiming more than the paper it cites? Can Claude fix those sentences well enough that
Decider accepts them?

## Data

- **Releases.** Every NIH news release on archive pages 0–51 (about the last year) whose
  "Reference" section gives a DOI.
- **Papers.** The abstract of each cited paper, from Europe PMC, then OpenAlex, then Semantic
  Scholar.
- **Text checked.** The headline, the subtitle and the first 6 new sentences of each release.

## Rules (fixed before the run)

- **Benchmark rule.** A sentence's score is P(it claims more than the paper's conclusion). This is
  the rule calibrated on the expert-labelled test set.
- **Public rule (what HypeWatch shows).** The minimum of two scores: P(more than the conclusion) and
  P(more than the strongest claim in the first 14 abstract sentences). This can only remove flags,
  so the calibrated false-flag rate is an upper bound for it.
- **Zones.** BLOCK above 0.50 (conformal α = 0.10). REVIEW above 0.399 (α = 0.20).
- **Rewrites.** Each BLOCK sentence gets a Claude Sonnet 4.6 rewrite, with up to 2 tries. A rewrite
  counts as verified if its benchmark-rule score is ≤ 0.50.

## Predictions

| Measure | Prediction |
|---|---|
| Releases with ≥ 1 BLOCK sentence, public rule | 3 – 20% |
| Releases with ≥ 1 BLOCK sentence, benchmark rule | 20 – 50% |
| Mean score, headlines vs other sentences | headlines higher |
| Rewrites verified within 2 tries | ≥ 85% |
| Releases skipped because no abstract was found | ≤ 15% of those with a DOI |

Context for the first two rows, from manual coding of UK university releases: 33% had causal
overstatement in 2011 (Sumner 2014) and 13% in 2015 (Bratton 2020). NIH releases go through a
federal communications office, so we expect fewer flags than university releases.

## What would change the product

If the public-rule block rate is 0%, HypeWatch will lead with the review zone and say plainly
that it found no blocking overclaims. If rewrites are verified less than 70% of the time, the page
will show the rewrites as "unverified suggestions".

---

## Results (appended after the run)
