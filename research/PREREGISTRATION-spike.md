# Pre-registration: day-1 feasibility spike

Written 2026-10-16, **before any model output was seen**. Results are appended below the line and
nothing above it is edited afterwards. This follows the convention of the strands-decider repo.

## Question

Can Strands Decider 2B (`StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`, zero-shot, no tuning)
detect when a health press release claims more than the paper it reports?

## Data (none authored by us)

- **W&A**: Wright & Augenstein, EMNLP 2021. Test split: 563 press-release/abstract conclusion pairs, labelled `same` / `exaggerates` / `downplays`, plus a 0–3 claim-strength label for each side. The labels come from the Sumner 2014 and Bratton 2019 expert coding. GPL-3.0, evaluation only.
- **Yu19**: Yu, Li & Wang, EMNLP 2019. 3,061 PubMed conclusion sentences labelled 0 no relationship, 1 correlational, 2 conditional causal, 3 direct causal. GPL-3.0, evaluation only.

## Variants (fixed before running)

- **V1 direct.** One `choice` question over the pair: same / exaggerates / downplays.
- **V2 strength-compare.** Classify each sentence's strength (4-way `choice`) separately, then call it exaggeration if press strength > abstract strength. A continuous score comes from `P(exag) = Σ_{i>j} p_press(i)·p_abs(j)`.
- **V3 noul.** A yes/no question: does the press release claim a stronger relationship than the paper supports?

## Metrics

- Macro-F1 for 3-class exaggeration on W&A test. Published best is MT-PET **47.35**; the supervised baseline is 29.05.
- AUROC for exaggerates vs not.
- **Negative control:** the false-flag rate on `same` pairs.
- Strength macro-F1 on Yu19, and binary F1 for direct-causal vs correlational.
- Median and p95 latency per request on an RTX 4070 Laptop (8 GB) under WSL2.

## Predictions

| Metric | Prediction |
|---|---|
| Yu19 4-class strength macro-F1 (zero-shot) | 0.50 – 0.70 |
| Yu19 direct-causal vs correlational F1 | 0.70 – 0.85 |
| W&A 3-class macro-F1, best variant | 0.40 – 0.55 |
| W&A exaggerates-vs-not AUROC, best variant | 0.65 – 0.80 |
| False-flag rate on `same` pairs at the default argmax | 15 – 35% |
| Median latency per request | ≤ 250 ms |

## Decision rule

- **GO** if either of these holds:
  - the best W&A 3-class macro-F1 ≥ 0.47, which beats the published SOTA;
  - Yu19 direct-causal vs correlational F1 ≥ 0.70 **and** W&A AUROC ≥ 0.70.
- **GO-WITH-TUNING** if W&A AUROC is 0.60–0.70. Then LoRA-tune the strength head on Yu19 with the repo's recipe, with W&A test held out.
- **PIVOT** to the runner-up idea (false-premise medical guard, Cancer-Myth CC BY 4.0) if W&A AUROC < 0.60 **and** Yu19 binary F1 < 0.60.

---

## Results (appended after the run)

Run on 2026-10-17 against `strands-decider-2B-qwen3.5-v1-2610` (zero-shot), served under WSL2 on an RTX 4070 Laptop GPU (8 GB). Per-item outputs are in `results/spike-v1/`.

### W&A (563 test pairs: 345 same, 122 exaggerates, 96 downplays)

| Metric | Predicted | Result | Hit? |
|---|---|---|---|
| 3-class macro-F1, best variant | 0.40–0.55 | **0.498** (V2 strength-compare). V1 direct: 0.408 | yes |
| Exaggerates-vs-not AUROC, best variant | 0.65–0.80 | **0.716** (V2). V1: 0.676. V3 noul: 0.629 | yes |
| False-flag rate on `same`, default argmax | 15–35% | **14.5%** (V2), 7.5% (V1), 6.4% (V3 at 0.5) | better than predicted |
| Median latency | ≤ 250 ms | 160 ms per sentence request, 323 ms per pair request (2 questions) | yes |

V2 reaches 0.498, above the published MT-PET best of 0.4735. That comparison has two caveats:
- MT-PET was trained on 100 in-task pairs plus auxiliary data, while Decider here is untrained.
- This is one run on 563 items. We have not computed a CI yet, so do not call it a resolved win.

### Yu19 (3,061 sentences)

**Scoring error, disclosed.**
- The pre-registration assumed Yu labels 1 = correlational and 3 = direct causal. The dataset README says the reverse: 1 = direct causal, 3 = correlational.
- The first `yu19` block in `summary.json` is therefore wrong. The tell was a binary AUROC of 0.106, a mirror image.
- `yu19_corrected` re-scores the **same per-item predictions** with the right map. No model calls were redone.

| Metric | Predicted | Result (corrected) | Hit? |
|---|---|---|---|
| 4-class macro-F1 | 0.50–0.70 | **0.539** (accuracy 0.619) | yes |
| Direct-causal vs correlational F1, default argmax | 0.70–0.85 | **0.626** | **no** |
| Direct-causal vs correlational AUROC (not pre-registered) | — | **0.894** | — |

Failure analysis:
- Decider labels only 116 of 494 direct-causal sentences as direct causal. It puts 180 under "no relationship".
- Ranking is strong (AUROC 0.89), so the miss is a threshold / prior problem. Calibration on labelled data is the planned fix. It is not evidence of missing signal.

### Decision

- **GO.** The GO rule needs either clause, and the first holds:
  - Clause 1 holds: the W&A macro-F1 of 0.498 is ≥ 0.47.
  - Clause 2 fails: W&A AUROC is 0.716 (≥ 0.70), but Yu19 binary F1 at default argmax is 0.626 (< 0.70).
- Product consequence: the gate's thresholds must be **calibrated on labelled pairs**, not taken from the 0.9/0.5 convention. That is what the conformal/calibration pattern is for.
