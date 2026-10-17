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
| Paired with Amazon Bedrock for generation | ✅ | Claude Sonnet 4.6 rewrites flagged sentences. 🔧 The agent also runs on **Amazon Bedrock AgentCore Runtime** (see C) |
| Article on Builder Center | ⏳ | Draft in `ARTICLE.md`. It must be posted by the author |
| Article covers the agent, the decision, and what it does | ✅ | Sections "The decision handed to Decider", "Results" |
| *Encouraged:* latency/cost vs LLM, accuracy, low-confidence handling | 🔧 | The latency and accuracy were there. Added: **$ cost per check** from list prices, and an explicit **three-zone low-confidence policy** (Proceed / human-review band / Guide), both thresholds conformal |
| Public repo, OSI licence | ✅ | github.com/usv240/hypecheck, Apache-2.0 |
| Reusable pattern **clearly labelled**, with typed question + option set + wiring + note | 🔧 | It was only described inside the main README. Added `decision_pattern/README.md` with the questions verbatim, the wiring, a usage note, calibration steps, and a decision table |
| Video < 3 min, public on YouTube/Vimeo, no third-party music/marks | ⏳ | Script in `VIDEO.md`. 🔧 Added a fully automated narrated recording (`video/`, Amazon Polly voice, no music) so a draft exists. The author uploads it |
| Tags `#strands-decider-2b` + exactly one pattern tag | ⏳ | `#guardrails`, listed in `SUBMISSION.md` |
| Original, unpublished agent | ✅ | Created 2026-10-16/17. No prior publication |

## B. Rubric line by line: where a judge could take points, and the fix

### Creativity and cool factor (30%)

| Penalty risk | Fix |
|---|---|
| A first-time visitor doesn't understand what they're looking at | 🔧 Rebuilt the page using the principles in `DESIGN.md`. Changes:<br>• hero sentence and a 4-step "how it works" strip<br>• **ⓘ on every control, score, label and number** (hover, keyboard focus, or tap), in plain language<br>• glossary and FAQ |
| The CPU demo takes ~20 s with no feedback, so it looks broken | 🔧 Sentences now colour **live, one at a time** as Decider reads them, with a progress counter. The judge sees the decision model working |
| A second judge gets "another run in progress" | 🔧 Runs are now **queued** and show their position, never rejected |
| Colour-only red/green is inaccessible | 🔧 Each sentence has a text label and icon (BLOCK / REVIEW / OK). Contrast was checked for WCAG AA |

### Effective use of Decider with Bedrock + pattern quality (30%)

| Penalty risk | Fix |
|---|---|
| Thresholds hand-picked, as in most entries | ✅ Conformal calibration with a stated and measured false-flag rate |
| "Low-confidence handling" is implicit | 🔧 Three zones. The review band sits between the α = 0.20 and α = 0.10 conformal thresholds. Those sentences don't block, but are surfaced for a human glance and listed in the publish record |
| Bedrock is used only as a raw model call | 🔧 The agent is also deployed to **AgentCore Runtime**, with a guarded Decider endpoint on EC2. Bedrock is used both as model access and as managed agent hosting |
| No cost number (the bonus) | 🔧 Measured tokens × list price → $ per check for Haiku 4.5 and Sonnet 4.6, against the EC2 cost per Decider decision. In README and article |
| Is the pattern reusable or just claimed to be? | ✅ `examples/leaflet_gate.py` runs it unchanged in a second domain, plus offline tests |

### Communication (25%)

| Penalty risk | Fix |
|---|---|
| Wall of text, no "60-second tour" | 🔧 The README opens with a judge-first summary: tagline, two numbers, links, screenshot. Detail sits below the fold |
| Jargon (AUROC, conformal, macro-F1) | 🔧 Each term has a ⓘ on the site and a one-line plain-English gloss in the article |
| No video | ⏳ / 🔧 An automated narrated draft exists. The author records or uploads it |
| Learnings missing | ✅ The article has a "What we learned" section, including the two failed pre-registered experiments |

### Originality (15%)

| Penalty risk | Fix |
|---|---|
| "Guardrail" is a crowded tag | ✅ The decision is new: claim strength against a source, using science-communication research scales. Collision search found no tool that checks a draft press release against its paper. The article states the gap with sources |

## C. Winner patterns (from the brief)

| # | Pattern | Status |
|---|---|---|
| 1 | Two numbers | ✅ Benchmark (W&A F1 / false flags), plus a second, independent set: InSciOut real releases, AUROC 0.84 |
| 2 | Cases from outside | ✅ All data is published expert coding |
| 3 | Named baseline beaten | ✅ Published SOTA 0.4735; Claude Haiku 4.5 / Sonnet 4.6 / Opus 4.6 |
| 4 | Negative control is the headline | ✅ 7.7% false flags vs 45% |
| 5 | Loop closes into the user's system | ✅ The release is published to the outbox only when clean. The publish record lists review-band sentences |
| 6 | Depth on one surface | ✅ One decision, five measurements |
| 7 | Verb-chain tagline | ✅ "reads… flags… has Claude rewrite… re-checks" |
| 8 | Demo can't break | 🔧 Queueing, Elastic IP, a health-checked systemd restart, and "Check with Decider only", which works with no Bedrock at all |
| 9 | Practitioner voice | ✅ via research, per the author's constraint: Sumner/Adams worked *with* press offices (the RCT ran in 9 real press offices), and HealthNewsReview's 2018 closure notice is cited |
| 10 | Shipped surface | ✅ HTTPS URL |
| 11 | Limits as measured properties | ✅ Recall 39%; animal check AUROC 0.61; CPU latency; CI widths |
| 12 | Inspect and rerun | ✅ Pre-registrations, per-item CSVs, `research/README.md` commands, tests |
