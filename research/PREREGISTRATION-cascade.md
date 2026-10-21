# Pre-registration: ask Claude only when Decider is unsure (cascade)

Written 2026-10-21, **before computing**. Results are appended below the line.

## Idea

Credit: the idea comes from another hackathon entry (Bylaw), where an LLM is asked only when the decision model is unsure.

- Decider already sorts each sentence into three zones:
  - **BLOCK:** score > 0.5001 (conformal α = 0.10).
  - **OK:** score ≤ 0.3986 (α = 0.20).
  - **REVIEW:** in between.
- **The cascade:** BLOCK and OK keep Decider's verdict. A REVIEW sentence goes to Claude, and the cascade flags it only if Claude says "exaggerates".

## Data

The W&A test split: 563 pairs, of which 345 are `same` (faithful), 122 exaggerate and 96 downplay.

The cascade is computed offline, with no new model calls, from per-item outputs that already exist:
- `spike-v1/wa_items.csv`, Decider's `v2_p_exag`;
- `baseline-sonnet-4-6/items.csv`, Claude Sonnet 4.6's verdict (main variant);
- `baseline-haiku45/items.csv`, Claude Haiku 4.5's verdict (second variant).

Rows are paired by order, and the `gold` labels are checked to match row by row.

## Measures

- Recall on exaggerates.
- False flags on `same`, and on all non-exaggerating pairs.
- Share of pairs sent to Claude.
- Claude cost per 1,000 sentences: (share sent to Claude) × the measured cost per call.

## Prediction

- **Sonnet cascade vs Decider alone:**
  - recall rises from 38.5% to 43–55%;
  - false flags on `same` rise from 6.7% to 7–12%;
  - 8–20% of pairs go to Claude.
- **Haiku cascade:** a smaller recall gain and more false flags than Sonnet.

## Adoption rule

The product adds the cascade, as an option in the gate and on the site, only if the Sonnet cascade meets both conditions:
- it raises recall by **≥ 5 points**;
- it keeps false flags on `same` at **≤ 10%**.

Otherwise it is reported as not adopted.

---

## Results (appended after computing)

Computed 2026-10-21, offline, from existing per-item outputs: `python research/cascade_eval.py`. The output is in `results/cascade/summary.json`.

| System | Recall | False flags, `same` | False flags, non-exaggerating | Sent to Claude | Claude $ / 1,000 |
|---|---|---|---|---|---|
| Decider alone | 38.5% | 6.7% | 7.7% | 0% | $0 |
| Cascade, Sonnet 4.6 on REVIEW | 41.8% | 9.3% | 10.7% | 6.4% | $0.06 |
| Cascade, Haiku 4.5 on REVIEW | 42.6% | 10.4% | 12.0% | 6.4% | $0.03 |
| Sonnet 4.6 alone | 40.2% | 29.6% | 29.0% | 100% | $0.97 |
| Haiku 4.5 alone | 59.0% | 44.9% | 46.0% | 100% | $0.51 |

- **Rule:** recall must rise ≥ 5 points, with false flags on `same` ≤ 10%. The Sonnet cascade gained **+3.3 points** (false flags 9.3%). **Not adopted.**
- **Prediction mostly failed:**
  - Recall was 41.8%, below the predicted 43–55%.
  - The share sent to Claude was 6.4%, below the predicted 8–20%; the REVIEW band is narrower than assumed.
  - False flags of 9.3% landed inside the predicted range.
  - Haiku behaved as predicted: a little more recall and more false flags than Sonnet.
- **Worth reporting even though it isn't adopted:**
  - The Sonnet cascade beats Sonnet on its own on recall (41.8% vs 40.2%).
  - It does so with a third of the false flags (9.3% vs 29.6%), at 6% of the Claude cost.
  - So asking an LLM only when the decision model is unsure works better than asking it every time. It just doesn't move recall enough to justify adding a dependency on Claude to the gate.
- **The idea came from** another hackathon entry, Bylaw. We credit it here and in the article.
