# Pre-registration: the advisory checks on full real press releases (InSciOut)

Written 2026-10-17, **before running**. Results are appended below the line; nothing above it changes.

## Why

The gate's two advisory checks, *animal → human* and *unsupported advice*, had no labelled data.

InSciOut (Sumner et al. 2014, figshare 903704, **CC BY 4.0**) contains:
- the full text of 462 UK university press releases from 2011;
- expert codes for the press releases and their source papers, including advice level and whether a study in non-human subjects is presented as being about humans.

Neither code was used to build the W&A benchmark the gate's thresholds came from, so this is a second, independent test.

## Data

Table `Tables for GEE analysis.xlsx`, one row per press release; text from `5. Press releases/*.docx`. Article ID *n* is the *n*-th file in sorted order, checked on IDs 2, 52 and 69.

- **Animal**: the 45 releases whose paper is coded non-human (journal code 0).
  - Label: the release's code. 0 = still non-human (22). 1 or 2 = implicitly or explicitly human (23).
  - The two releases from human studies are excluded.
- **Advice**: 116 releases.
  - Release advice code: 0 none, 1 implicit, 2 explicit indirect, 3 explicit direct.
  - Paper (journal) advice code, the same scale.
  - "Inflated" = release code > paper code.

## Questions (fixed before running)

- **Animal.** State: "The study this press release reports was done in animals, cells or a lab model, not in people.", followed by the release text. Question: one `noul` asking whether the release presents the finding as applying to people.
- **Advice.** One 4-way `choice` on the release text, with the Sumner coding definitions as option descriptions.
  - Inflation score = P(predicted release level > the paper's coded level).
  - The paper's level is taken from the codes, to isolate the release-side detector.

## Predictions

| Metric | Prediction |
|---|---|
| Animal: AUROC for human-inferred vs faithful | 0.65 – 0.85 |
| Advice: 4-class macro-F1 | 0.30 – 0.50 |
| Advice: AUROC for explicit advice (code ≥ 2) | 0.65 – 0.85 |
| Advice: AUROC for inflated vs not | 0.60 – 0.80 |

## What would change the product

If either advisory AUROC is < 0.60, that check is removed from the gate's feedback and from the article claims.

---

## Results (appended after the run)

Run on 2026-10-17 against `strands-decider-2B-qwen3.5-v1-2610` (zero-shot) on an RTX 4070 Laptop GPU under WSL2. That was 161 decider calls at a mean of 268 ms per full press release. Per-item results are in `results/insciout/`.

| Metric | Predicted | Result | Hit? |
|---|---|---|---|
| Animal: AUROC for human-inferred vs faithful (n = 45, 23 positive) | 0.65–0.85 | **0.609** | **no** (below range, above the 0.60 removal line) |
| Advice: 4-class macro-F1 (n = 116) | 0.30–0.50 | **0.446** | yes |
| Advice: AUROC for explicit advice | 0.65–0.85 | **0.767** | yes |
| Advice: AUROC for inflated vs not (50 inflated) | 0.60–0.80 | **0.841** | better than predicted |

**Animal → human is weak.**
- At P ≥ 0.5 it never fires: recall 0/23, false flags 0/22. Its probabilities sit below 0.5 for every release.
- The AUROC of 0.61 on n = 45 has a wide interval and is barely over the pre-registered removal line.

Decisions:
- **Advice-inflation check:** it stays in the gate's feedback and is reported as measured. AUROC 0.84 on real press releases coded by Sumner's team.
- **Animal → human check:** it stays only as a low-weight hint, never as a claim.
  - The article states the measured weakness: AUROC 0.61, n = 45.
  - It is a candidate for tuning, if time allows.
