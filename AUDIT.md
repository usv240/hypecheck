# Self-audit against the rules and rubric (2026-10-17)

Sources:
- the Terms and Conditions on the hackathon's Rules tab;
- the About tab;
- the twelve winner patterns supplied with the brief.

Status key:
- ✅ met
- 🔧 gap, fixed in this pass
- ⏳ needs the author: an outward-facing action we won't take without a yes

## A. Pass/fail qualification (any miss = not judged)

| Requirement | Status | Evidence / action |
|---|---|---|
| Working agent on AWS | ✅ | EC2 + CloudFront live URL, with Bedrock via the instance role. 🔧 Elastic IP added, so a stop/start doesn't break the CloudFront origin |
| Decider makes ≥1 *meaningful* decision | ✅ | Claim strength per sentence gates `publish_release` |
| Paired with Amazon Bedrock for generation | ✅ | Claude Sonnet 4.6 rewrites flagged sentences. ✅ The agent runs on **Amazon Bedrock AgentCore Runtime** (direct code deploy, streaming), with an in-process fallback on EC2. It was verified end to end through the public URL |
| Article on Builder Center | ⏳ | Draft in `ARTICLE.md`. It must be posted by the author |
| Article covers the agent, the decision, and what it does | ✅ | Sections "The decision handed to Decider", "Results" |
| *Encouraged:* latency/cost vs LLM, accuracy, low-confidence handling | 🔧 | The latency and accuracy were there. Added: **$ cost per check** from list prices, and an explicit **three-zone low-confidence policy** (Proceed / human-review band / Guide), both thresholds conformal |
| Public repo, OSI licence | ✅ | github.com/usv240/hypecheck, Apache-2.0 |
| Reusable pattern **clearly labelled**, with typed question + option set + wiring + note | 🔧 | It was only described inside the main README. Added `decision_pattern/README.md` with the questions verbatim, the wiring, a usage note, calibration steps, and a decision table |
| Video < 3 min, public on YouTube/Vimeo, no third-party music/marks | ⏳ | Script in `VIDEO.md`. The author records it with the script in `VIDEO.md` and uploads it |
| Tags `#strands-decider-2b` + exactly one pattern tag | ⏳ | `#guardrails`, listed in `SUBMISSION.md` |
| Original, unpublished agent | ✅ | Created 2026-10-16/17. No prior publication |

## B. Rubric line by line: where a judge could take points, and the fix

### Creativity and cool factor (30%)

| Penalty risk | Fix |
|---|---|
| A first-time visitor doesn't understand what they're looking at | 🔧 Rebuilt the page using the principles in `DESIGN.md`. Changes:<br>• hero sentence and a 4-step "how it works" strip<br>• **ⓘ on every control, score, label and number** (hover, keyboard focus, or tap), in plain language<br>• glossary and FAQ |
| The CPU demo takes ~20 s with no feedback, so it looks broken | 🔧 Sentences now colour **live, one at a time** as Decider reads them, with a progress counter. The judge sees the decision model working |
| A second judge gets "another run in progress" | 🔧 Runs are now **queued** and show their position, never rejected |
| Colour-only red/green is inaccessible | ✅ Each sentence has a text label and icon (BLOCK / REVIEW / OK). **axe-core reports 0 violations** (WCAG 2.2 AA and best practice) in light and dark themes, with no horizontal overflow at 390 px. `tests/ui/a11y_check.py` checks this |

### Effective use of Decider with Bedrock + pattern quality (30%)

| Penalty risk | Fix |
|---|---|
| Thresholds hand-picked, as in most entries | ✅ Conformal calibration with a stated and measured false-flag rate |
| "Low-confidence handling" is implicit | 🔧 Three zones. The review band sits between the α = 0.20 and α = 0.10 conformal thresholds. Those sentences don't block, but are surfaced for a human glance and listed in the publish record |
| Bedrock is used only as a raw model call | ✅ The agent is also deployed to **AgentCore Runtime**, with a guarded Decider endpoint on EC2. Bedrock is used both as model access and as managed agent hosting |
| No cost number (the bonus) | 🔧 Measured tokens × list price → $ per check for Haiku 4.5 and Sonnet 4.6, against the EC2 cost per Decider decision. In README and article |
| Is the pattern reusable or just claimed to be? | ✅ `examples/leaflet_gate.py` runs it unchanged in a second domain, plus offline tests |

### Communication (25%)

| Penalty risk | Fix |
|---|---|
| Wall of text, no "60-second tour" | 🔧 The README opens with a judge-first summary: tagline, two numbers, links, screenshot. Detail sits below the fold |
| Jargon (AUROC, conformal, macro-F1) | 🔧 Each term has a ⓘ on the site and a one-line plain-English gloss in the article |
| No video | ✅ A 2:49 narrated video exists, made by `video/make_video.py` (live site, Amazon Polly voice, no music). ⏳ The author uploads it to YouTube |
| Learnings missing | ✅ The article has a "What we learned" section, including the failed pre-registered predictions |

### Originality (15%)

| Penalty risk | Fix |
|---|---|
| "Guardrail" is a crowded tag | ✅ The decision is new: claim strength against a source, using science-communication research scales. Collision search found no tool that checks a draft press release against its paper. The article states the gap with sources |

## C. Winner patterns (from the brief)

| # | Pattern | Status |
|---|---|---|
| 1 | Two numbers | ✅ Benchmark (W&A F1 / false flags), plus a second, independent set: InSciOut real releases, AUROC 0.84 |
| 2 | Cases from outside | ✅ All data is published expert coding |
| 3 | Named baseline beaten | ✅ AWS-native Bedrock Guardrails grounding check beaten (AUROC 0.72 vs 0.50, gap CI 0.14–0.29). Ties the published best (0.4735, trained) zero-shot; beats Haiku 4.5 and Sonnet 4.6 on macro-F1 and all three Claude models on false flags, each with a paired-bootstrap 95% CI (`research/significance.py`) |
| 4 | Negative control is the headline | ✅ 6.7% false flags on faithful releases vs 29.6–44.9% for Claude |
| 5 | Loop closes into the user's system | ✅ The release is published to the outbox only when clean. The publish record lists review-band sentences |
| 6 | Depth on one surface | ✅ One decision, five measurements |
| 7 | Verb-chain tagline | ✅ "reads… flags… has Claude rewrite… re-checks" |
| 8 | Demo can't break | 🔧 Queueing, Elastic IP, a health-checked systemd restart, and "Check with Decider only", which works with no Bedrock at all |
| 9 | Practitioner voice | ✅ via research, per the author's constraint: Sumner/Adams worked *with* press offices (the RCT ran in 9 real press offices), and HealthNewsReview's 2018 closure notice is cited |
| 10 | Shipped surface | ✅ HTTPS URL |
| 11 | Limits as measured properties | ✅ Recall 39%; animal check AUROC 0.61; CPU latency; CI widths |
| 12 | Inspect and rerun | ✅ Ten pre-registrations, per-item outputs, a SHA-256 manifest, and `research/reproduce.py`, which recomputes 22 of 22 headline numbers offline (also a test). Upstream docs issue strands-decider#103 |


## D. Second pass (after HypeWatch), scored 4 or 5 per rubric line

| Criterion | Before | Now | What moved it |
|---|---|---|---|
| Creativity & cool factor (30%) | 4 | **5** | **HypeWatch.** The same gate runs on 85 real NIH releases that cite their papers. Each flagged release shows the paper's own words, Claude's suggested rewrite and Decider's check of it. The page updates every morning. It is something a judge can browse, and it is about the real world, not a benchmark |
| Effective use of Decider + Bedrock (30%) | 5 | **5** | Adds Decider checking Claude's rewrites at scale (18 rewrites, 67% pass, reported against a missed prediction). Adds a second, stricter decision rule for public flags, built from Decider probabilities (min of two overclaim scores), with the calibrated false-flag rate kept as an upper bound |
| Communication (25%) | 4 | **5** | Article cut from 1,717 to about 930 words of plain language, with every number in one table. The video gains a HypeWatch scene. The README leads with the two numbers and the live links |
| Originality (15%) | 5 | **5** | No public tool checks real releases against their papers this way |

**Still out of our hands:**
- the GPU quota for the live demo's speed;
- posting the article;
- uploading the video;
- adding the submission tags.


## E. Third pass: reuse without cloning

Checked against "quality of your reusable decision pattern" (part of the 30% Effective use
criterion) and the announced recognition for the most-reused pattern:

- **Before:** the pattern could only be reused by copying `decision_pattern/` into your own code.
- **Now there are four routes, each verified live:**
  - **REST API** with instant hashed keys. Its limits protect the Bedrock budget.
  - **MCP connector.** A real Strands agent on Bedrock used it.
  - **Hosted calibration** on your own labelled pairs. In-sample on 12 pairs: threshold 0.44, 0% false flags, 100% recall.
  - **CloudFormation stack.** Test-launched in our own account.
- **Not done:** a true one-click "Launch stack" button. It needs a public S3 bucket, which means
  changing an S3 security setting. That is left to the author; the page offers download plus
  console instead.


## F. Final audit against Rules.md (2026-10-23, deadline day)

Every requirement on the About and Rules tabs, checked against the live state, not memory.

### Pass/fail

| Requirement (Rules.md) | Status | Checked how |
|---|---|---|
| Working agent on AWS using Decider 2B for a meaningful decision, paired with Amazon Bedrock | ✅ | Live run through AgentCore Runtime today: two Decider verdicts, Claude Sonnet 4.6 rewrite, published, receipts attached. `/api/health` 200 |
| Written article on Builder Center describing the agent, what it does, and the decision handed to Decider | ⏳ **you** | `ARTICLE.md` is final (1,900 words, screenshots load from GitHub). Must be pasted and published on Builder Center |
| Public repo with the agent's source and at least one reusable Decider 2B decision pattern others can use | ✅ | github.com/usv240/hypecheck is public; Apache-2.0 detected by GitHub's API; `decision_pattern/README.md` is titled "Decision pattern: claim-fidelity gate (`#guardrails`)" and gives the typed question and options verbatim, the `InterventionHandler` wiring, a usage note, calibration, receipts and install (`pip install git+…`). 🔧 Fixed today: the LICENSE still carried the Apache template's `[yyyy] [name of copyright owner]` |
| Short public demo video, under three minutes, showing the agent and its Decider decision working | ⏳ **you** | `video/hypecheck-demo.mp4` is 2:49 (under 3:00), Polly narration, no music, no third-party footage. It shows the **old** design, so re-render first (`video/make_video.py`), then upload to YouTube or Vimeo |
| One decision pattern declared | ✅ | Guardrails, stated in the article's first line, the pattern README and SUBMISSION.md |
| Original agent, not published before | ✅ | First commit 2026-10-17, inside the hackathon window; the collision search found no prior tool that gates a release against its paper |
| Tags: `#strands-decider-2b` plus one pattern tag | ⏳ **you** | `strands-decider-2b`, `guardrails`, then `amazon-bedrock`, `strands-agents`, `amazon-bedrock-agentcore` (five is the form's maximum). 🔧 Fixed today: SUBMISSION.md listed two different tag sets |
| Builder 18+, with a Builder Center profile, not an excluded country or employee | ⏳ **you** | Your account; the Chrome profile is currently signed out |
| One entry per person | ✅ | HypeCheck only |

**Encouraged, not required:** measured latency and cost (✅ per decision and per 1,000 sentences, with the Claude comparison), decision accuracy (✅ with CIs), how low-confidence cases are handled (✅ the REVIEW zone, and `Deny` when unverifiable).

### Rubric, scored 4 or 5 (the judges' scale)

| Criterion | Weight | Score | Why this score, and the one thing that could lower it |
|---|---|---|---|
| Creativity and cool factor | 30% | **5** | Hype stopped at its source; the claim ladder explains every verdict; HypeWatch runs on real NIH releases daily; AI summaries as a second use case; a receipt a press officer can hand to an editor. *Risk:* a judge who wants a physical or personal hook |
| Effective use of Decider 2B with Bedrock, incl. the reusable pattern; latency/cost bonus | 30% | **5** | One typed question compared in code; conformal thresholds with a kept promise; Decider re-checks Claude; all four intervention actions; Decider failover and Claude fallback; the pattern is pip-installable, an API, MCP and a CloudFormation stack; cost and latency measured against Claude, Guardrails and a keyword rule. *Risk:* recall 39% at the strict threshold, stated openly |
| Communication quality | 25% | **4 → 5** | Site with ⓘ on every number and a 30-second tour; README that opens with a where-to-look table; article with screenshots, limits, misses and learnings; notebook. **4 until the video is re-rendered and the article is posted**; then 5 |
| Originality | 15% | **5** | No other entry, in 275, works on health news, press releases or AI summaries of science; the data predates the hackathon |
| **Weighted** | | **4.75 now; 5.00 once the video and article are up** | |

### What only the author can do today (in order)

1. Sign in to Builder Center in Chrome.
2. Say "render the video" so I re-render it against the new design (about 1–1.5 h); then upload it (public or unlisted) and give me the link.
3. Say "freeze" so I tag `v1.0-submission` and put the video link into README, ARTICLE and SUBMISSION.
4. Create the project: paste `ARTICLE.md` as Markdown, cover `docs/cover.jpg`, repo, live demo, notebook link, the five tags. Publish well before 11:59 PM PDT.
