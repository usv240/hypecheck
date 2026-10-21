# Builder Center submission fields

**Project title:** HypeCheck — spell-check for hype in health press releases

**One-line description:**
HypeCheck reads a draft health press release next to the paper it reports, flags every sentence that claims more than the study found, has Claude rewrite it, and re-checks the rewrite before anything is published.

**Tags:** `#strands-decider-2b` `#guardrails` (plus `amazon-bedrock`, `strands`, `agents`)

**Decision pattern demonstrated:** Guardrails. Before the `publish_release` tool runs, Strands Decider 2B verifies that every sentence is grounded in what the paper's conclusion supports (claim strength: none < correlational < conditional causal < direct causal). Overclaims return `Guide`; still overclaiming after three rewrites returns `Confirm`; clean text returns `Proceed`.

**Links**
- Repository (Apache-2.0): https://github.com/usv240/hypecheck
- Reusable pattern: https://github.com/usv240/hypecheck/tree/main/decision_pattern
- Developers (free API key, REST, MCP, bring your own data or AWS): https://d174bz5yly61n4.cloudfront.net/developers
- Live demo: https://d174bz5yly61n4.cloudfront.net
- HypeWatch (real NIH releases, daily): https://d174bz5yly61n4.cloudfront.net/hypewatch
- Article: *(Builder Center URL after posting ARTICLE.md)*
- Video: *(YouTube URL)*. Upload `video/hypecheck-demo.mp4` (2:34, narrated, no music)

**Headline numbers (all on public expert-labelled data, pre-registered):**
- Per 1,000 honest sentences: Claude Sonnet as the judge wrongly blocks 296 for $0.97; HypeCheck blocks 67 for $0.18 ($0 on your own GPU).
- Exaggeration detection macro-F1 0.498 zero-shot on 563 pairs (95% CI 0.452–0.541): level with the published best (0.4735, trained). Claude Opus 4.6 0.460.
- Every gap to Claude on false flags is outside chance (paired bootstrap; smallest, Sonnet: 22.9 points, CI 17.8–27.9).
- Faithful releases wrongly flagged: 6.7%, against Claude 29.6–44.9% (Sonnet 4.6, Opus 4.6, Haiku 4.5). The calibrated promise is ≤10%, and the measured rate on 441 unseen pairs is 7.7%.
- The agent is hosted on Amazon Bedrock AgentCore Runtime; Decider runs on EC2 behind CloudFront.
- HypeWatch: 85 NIH releases (2023–2026) checked against their papers. 15.3% have a sentence the strict public rule blocks (43.5% under the benchmark rule). Claude rewrites pass Decider's check 67% of the time.
- 160 ms per decision on a laptop GPU, 0 tokens; the LLM baseline costs ~2 s and ~270 tokens per check.

**What was learned:** decompose the judgement (classify each side's strength, then compare) rather than ask for a direct comparison; calibrate thresholds on your own labelled data instead of using the illustrative 0.9/0.5 bands; pre-register and report the misses (two of five predictions failed, and are in the repo).
