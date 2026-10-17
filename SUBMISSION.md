# Builder Center submission fields

**Project title:** HypeCheck — spell-check for hype in health press releases

**One-line description:**
HypeCheck reads a draft health press release next to the paper it reports, flags every sentence that claims more than the study found, has Claude rewrite it, and re-checks the rewrite before anything is published.

**Tags:** `#strands-decider-2b` `#guardrails` (plus `amazon-bedrock`, `strands`, `agents`)

**Decision pattern demonstrated:** Guardrails. Before the `publish_release` tool runs, Strands Decider 2B verifies that every sentence is grounded in what the paper's conclusion supports (claim strength: none < correlational < conditional causal < direct causal). Overclaims return `Guide`; still overclaiming after three rewrites returns `Confirm`; clean text returns `Proceed`.

**Links**
- Repository (Apache-2.0): https://github.com/usv240/hypecheck
- Reusable pattern: https://github.com/usv240/hypecheck/tree/main/decision_pattern
- Live demo: https://d174bz5yly61n4.cloudfront.net
- Article: *(Builder Center URL after posting ARTICLE.md)*
- Video: *(YouTube URL)*

**Headline numbers (all on public expert-labelled data, pre-registered):**
- Exaggeration detection macro-F1 0.498 zero-shot on 563 pairs (published best 0.4735, trained).
- Calibrated threshold promises ≤10% false flags; measured 7.7% on 441 held-out faithful pairs. Claude Haiku 4.5 asked the same question: 45%.
- 160 ms per decision on a laptop GPU, 0 tokens; the LLM baseline costs ~2 s and ~270 tokens per check.

**What was learned:** decompose the judgement (classify each side's strength, then compare) rather than ask for a direct comparison; calibrate thresholds on your own labelled data instead of using the illustrative 0.9/0.5 bands; pre-register and report the misses (two of five predictions failed, and are in the repo).
