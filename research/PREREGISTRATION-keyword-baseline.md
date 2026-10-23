# Pre-registration: the no-model baseline (keyword rules)

Written 2026-10-23, **before computing**. Results are appended below the line.

## Why

The cheapest possible gate needs no model: flag any press-release sentence that contains a causal
verb. If Decider doesn't clearly beat that rule, a builder should use the rule. Several strong
entries in this hackathon report a no-model baseline (credit: Lachesis, Menu Line Check, Which
Brain?); we had Claude and Bedrock Guardrails as baselines but no rule-based floor.

## The rule

The same cue-word lists the HypeCheck site uses to *explain* verdicts (`CUES` in
`hypecheck/static/index.html`), applied as a classifier:

- **Level of a text** = the highest cue level it contains: 3 if it has a direct-causal cue
  ("causes", "prevents", "saves lives", "reduces", …), else 2 if it has a hedge ("may", "could",
  "suggests", …), else 1 if it has an association cue ("associated with", "linked to", …), else 0.
- **Keyword rule flags a pair** when level(release) > level(abstract conclusion).
- **Keyword score** (for AUROC) = level(release) − level(abstract), so ranking is possible.

No tuning: the lists are used exactly as they ship on the site today.

## Data

The 563 Wright & Augenstein test pairs, same rows as `results/spike-v1/wa_items.csv` (pairing
checked by `original_file_id`). Text comes from the public dataset (`data/test.jsonl`).

## Measures

- Recall on exaggerates and false flags on `same` (rule vs Decider at its α = 0.10 threshold).
- AUROC of the keyword score vs Decider's.
- Paired bootstrap 95% CI of the AUROC gap (5,000 resamples, seed 0).

## Predictions

| # | Prediction |
|---|---|
| N1 | The rule's false flags on `same` are **above 15%** (verbs like "reduces" appear in faithful releases too) |
| N2 | Decider's AUROC beats the rule's by **≥ 0.08**, with the CI above 0 |
| N3 | The rule's recall is **higher** than Decider's 38.5% (it fires on any causal verb) |

## What changes the product

- If the rule matches or beats Decider on AUROC, the README says so and recommends the rule.
- Otherwise the rule is added to the results table as the no-model floor, with the CI.

---

## Results (appended after computing)

Computed 2026-10-23: `python research/keyword_baseline.py --wa-dir data`. Per-item output in
`results/keyword-baseline/items.csv`; summary in `results/keyword-baseline/summary.json`.

| Measure | Keyword rule (no model) | Strands Decider 2B |
|---|---|---|
| AUROC, exaggerates vs not | **0.528** | **0.716** |
| Recall on exaggerates | 43.4% | 38.5% |
| False flags on `same` | **26.4%** | **6.7%** |
| AUROC gap, Decider − rule, paired bootstrap 95% CI | | **+0.188 (0.124–0.254)** |

| Prediction | Result | Hit? |
|---|---|---|
| N1: the rule's false flags > 15% | 26.4% | yes |
| N2: Decider's AUROC ≥ rule + 0.08, CI above 0 | +0.188 (0.124–0.254) | yes |
| N3: the rule's recall > 38.5% | 43.4% | yes |

**How to read it.** The rule catches a few more exaggerations, but only by flagging one honest
release in four. That is what a keyword gate does: "reduces" and "improves" are common in faithful
releases too, because many studies do find effects. The rule ranks pairs at near chance (0.53).
Decider ranks them at 0.72 and holds false flags at 6.7%. So the model earns its place over the
cheapest alternative. Credit for the device: Lachesis, RoadSense and Menu Line Check report a
no-model arm.
