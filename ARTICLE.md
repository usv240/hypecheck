# HypeCheck: an agent that won't publish a health claim the paper doesn't make

*Strands Decider 2B + Claude on Amazon Bedrock, hosted on Amazon Bedrock AgentCore Runtime · `#strands-decider-2b` `#guardrails`*

A study finds that patients who use an urgent cancer-referral pathway *tend* to live longer. The
press release says the pathway *is saving lives*. The news copies the press release.

**HypeCheck reads a draft health press release next to the paper it reports, flags every sentence
that claims more than the study found, has Claude rewrite it, and checks the rewrite again before
anything is published.**

- **Try it:** https://d174bz5yly61n4.cloudfront.net (there's a 30-second tour)
- **HypeWatch:** https://d174bz5yly61n4.cloudfront.net/hypewatch, a year of real NIH releases, checked
- **Code (Apache-2.0):** https://github.com/usv240/hypecheck
- **Video:** *(YouTube link)*

![HypeCheck: the paper says "could be efficacious", the release says "is saving lives", and the claim ladder shows the gap](https://raw.githubusercontent.com/usv240/hypecheck/main/docs/hero.jpg)

**In one line:** for every 1,000 honest press-release sentences, Claude Sonnet as the judge wrongly blocks 296 and costs $0.97; HypeCheck wrongly blocks 67 and costs $0.18, or nothing on your own GPU.

## Why it matters

In 2014, researchers read 462 university press releases next to their papers. A third turned "is
linked to" into "causes". When the release exaggerated, most of the news did too. When it didn't,
most of the news didn't (Sumner et al., *BMJ*).

It matters because health news changes what people do. After one burst of coverage questioning
statins, researchers estimated that about 219,000 people in the UK stopped taking them. They
caution that the study can't prove the coverage caused it (Matthews et al., *BMJ*, 2016).

A later randomised trial in nine press offices showed the fix works. Releases that matched the
evidence produced more accurate headlines, and they got just as much coverage (Adams et al.,
*BMC Medicine*, 2019).

The one free service that checked releases before publication was run by people, and it closed in
2018. Nothing has automated it.

## The decision handed to Decider

Strands Decider 2B is a small model that doesn't write text. It answers typed questions and gives
each answer a probability. HypeCheck asks it one question about the paper's conclusion and about
every sentence of the draft:

> **How strong is the relationship this sentence claims?**
> no relationship → linked (association) → *may* cause → causes

If a sentence sits higher on that ladder than the paper does, it's an overclaim. The check runs
inside the Strands agent as an intervention, just before the `publish_release` tool. Each sentence
lands in one of three zones:

- **BLOCK.** It clearly claims more than the paper. Publishing stops, and Claude gets the sentence
  back with the reason and rewrites it.
- **REVIEW.** The model is unsure. It doesn't block, but an editor sees it in the publish record.
  This is how HypeCheck handles low confidence.
- **OK.** It is within what the paper supports.

![A live check: "saving lives" is blocked at 0.80; the ladder shows the sentence at "causes" and the paper at "may cause"](https://raw.githubusercontent.com/usv240/hypecheck/main/docs/demo.jpg)

Claude's rewrite goes through the same check. In one recorded run, Claude's first rewrite still
overclaimed; Decider caught it, and the second rewrite passed. After three failed rewrites, a
person decides.

## Why a decision model, not Claude, does the judging

We asked Claude on Bedrock the same question on 563 expert-labelled press-release/paper pairs.

| | Decider 2B (no training) | Claude Haiku 4.5 | Claude Sonnet 4.6 | Claude Opus 4.6 |
|---|---|---|---|---|
| Honest releases wrongly flagged | **6.7%** (95% CI 4.1–9.4%) | 44.9% | 29.6% | 40.0% |
| Overall accuracy (macro-F1; best published system 0.474, a statistical tie) | **0.498** | 0.358 | 0.401 | 0.460 |
| Time per decision | 0.16 s on a laptop GPU | 2.0 s | 0.9 s | 5.3 s |
| Cost per sentence | $0.0002 on our CPU server, $0 on your own GPU | $0.0005 | $0.0010 | $0.0056 |

- **Fewer false alarms.** Claude over-flags. A gate that cries wolf gets switched off.
- **The threshold can be promised.** The Decider docs say to measure the cut-off on your own data.
  We did, with conformal calibration: pick the cut-off so that at most 10% of known-honest
  sentences would be flagged. On 441 pairs it had never seen, it flagged 7.7%.
- **It can't be argued with.** Decider returns a number, and plain code decides what to do. Every verdict ships a **decision receipt**: the rung probabilities, scores, thresholds and the rule, hashed. Anyone can recompute it without a model (`/v1/verify`), and a press officer can hand it to an editor.
- **A keyword rule can't do it either.** Flag every sentence with a causal verb and you catch a few more exaggerations, but you also flag one honest release in four (26%). Decider: 6.7%.
- **AWS's own grounding check doesn't catch this.** Amazon Bedrock Guardrails has a contextual
  grounding check for "does this text stay within its source". On the same pairs it ranked
  exaggerations at chance level: AUROC 0.50, against 0.72 for Decider, a gap of 0.21 (95% CI
  0.14–0.29). Grounding checks catch invented facts. A release that turns "could" into "saves
  lives" keeps the same facts and only inflates their strength, which is the job HypeCheck does.
  The two belong side by side.

All test data is published expert coding we didn't write. Every experiment was written down,
predictions included, before it ran: ten experiments, with every missed prediction reported.

## HypeWatch: the same check on real releases

To test it on text nobody chose for us, HypeWatch runs HypeCheck over every US National Institutes
of Health research release since February 2023 that cites its paper by DOI.

- **Coverage.** 85 releases were checked against their papers' abstracts.
- **Flags.** 15% had a headline or opening sentence the gate would block, under a stricter rule
  for public flags (a sentence must exceed the paper's conclusion *and* the strongest claim
  anywhere in the abstract).
- **Rewrites.** Claude's suggested rewrites passed Decider's check 67% of the time. That is below the 85% we predicted, so the page labels them suggestions, not fixes.

When the Sumner study came out, Ben Goldacre's *BMJ* editorial proposed linking every release to
its paper, naming its authors and opening it to review, to create "an information trail, and
accountability among peers and the public". HypeWatch automates part of that for one major
publisher of health news. Every flag sits next to the paper's own words, so a reader can judge. The
page updates every morning.

## A second use case: AI summaries

AI now writes much of the science people read. A 2025 study compared 4,900 AI summaries with
expert-written ones. The AI summaries were nearly five times as likely to state findings more
broadly than the paper did, and Claude was the most faithful family tested (Peters & Chin-Yee,
*Royal Society Open Science*).

We asked Claude Sonnet 4.6 and Haiku 4.5 to summarise the same 85 NIH papers, and wrote our
predictions down first.
- **About 1 in 9 summaries** had a sentence the gate blocks: 11.8% for Sonnet, 10.6% for Haiku.
- **Example.** A paper says medication for opioid use disorder in jail "was associated with" lower
  overdose and death risks. Both summaries said expanding it "can save lives".
- **The gate fixed 9 in 10** of the flagged summaries, re-checked by Decider.
- **One of four predictions missed:** Haiku did not overclaim more than Sonnet.
- **Limit:** these are Decider's flags, not human labels.

## How it runs on AWS

- **Amazon Bedrock AgentCore Runtime** hosts the agent, deployed as plain code with no container.
- **Amazon Bedrock** serves Claude.
- **Amazon EC2** runs Decider and the web page, behind **Amazon CloudFront**.
- **AWS Systems Manager Parameter Store** holds the key that protects the Decider endpoint.
- **Backups at every step:**
  - If AgentCore is unavailable, the page runs the same agent on EC2.
  - If Claude Sonnet is throttled, the agent switches to Claude Haiku.
  - If Decider can't be reached, the gate refuses to publish (`Deny`) rather than letting text
    through unchecked.

## What we learned

1. **Ask for one judgement at a time.** "How strong is this claim?" asked of each side, then
   compared, scored 0.50. "Is A stronger than B?" scored 0.41.
2. **Measure the cut-off.** The default answer under-called "causes" sentences, yet the model
   *ranked* them very well. A cut-off fitted on labelled data fixed that.
3. **Write predictions down first.** It made the failed predictions, and one scoring bug, easy to
   report instead of explain away.
4. **Put error bars on your own claims.** Our site said Decider scored "above the best published
   system", but the published score sat inside our 95% interval, so it now says "level with". The
   false-alarm gap to Claude survived the same test easily. A tool against overclaiming should not
   overclaim.

**Platform findings, for other builders:**
- **AgentCore code deploy from Windows:** `pip --platform` still pulls Windows-only wheels. We
  resolve the ARM64 list on Linux once and install it with `--no-deps`.
- **`Guide` ended the turn:** Claude stopped to ask the user until the system prompt said "rewrite
  and call the tool again in the same turn".
- **Listed is not enabled:** Claude 5.5 profiles were listed but denied, so the agent now falls back
  to another model.
- **Reported upstream:** [strands-decider#103](https://github.com/strands-labs/strands-decider/issues/103)
  proposes docs for comparing two texts, with our numbers, including the one that cuts against us.

**Cost and AI use.** All Claude usage during the build cost at most $9.04 on Bedrock, mostly the
three Claude baselines. The Guardrails run cost $0.07. An AI coding assistant wrote most of the
code under my direction. Every number here comes from a script in the repo. `python research/reproduce.py`, or the
[notebook](https://github.com/usv240/hypecheck/blob/main/notebooks/reproduce.ipynb), recomputes
all 22 headline numbers offline in about 10 seconds, and 17 offline tests cover the gate.

## Limits we measured

- **Recall:** at the strict cut-off it catches 39% of exaggerations. It is a safety net, not an
  editor.
- **Claim strength only:** it doesn't check numbers, doses or invented facts. The animal-to-human
  hint is weak (AUROC 0.61), so it never blocks.
- **No human labels:** HypeWatch and the AI-summary rates are Decider's flags, which is why every
  flag sits next to the paper's own words. No press officer has used it yet.
- **Scope:** English biomedicine only, and each experiment ran once.
- **Speed:** the live demo runs Decider on a CPU, about six times slower than a GPU.

## Reuse it

There are four ways in, all on the Developers page (https://d174bz5yly61n4.cloudfront.net/developers):
- **A free REST API** with instant keys and no signup.
- **An MCP connector**, so any agent can call `check_claims` before it publishes. We tested it with a Strands agent on Bedrock.
- **Calibration on your own labelled pairs**, in a form on the page: paste or upload them, get your threshold and a chart, then test new text against it.
- **A CloudFormation stack** that runs everything in your own AWS account.

For code, `pip install "git+https://github.com/usv240/hypecheck"` gives you `decision_pattern/`:
the question, the gate, the calibration script and tests. The same
gate runs unchanged on a patient-leaflet writer, where it caught "statin users were less likely to
develop dementia" stated as fact from an observational study. Use it anywhere text must not say
more than its source: summaries, RAG answers, patient materials.

*Sources:*
- Sumner et al., *BMJ* 2014
- Adams et al., *BMC Medicine* 2019
- Matthews et al., *BMJ* 2016
- Goldacre, *BMJ* 2014;349:g7465 (editorial)
- Wright & Augenstein, EMNLP 2021
- Yu et al., EMNLP 2019
- InSciOut (CC BY 4.0)
- Peters & Chin-Yee, *R Soc Open Sci* 2025

*The full technical write-up is `docs/ARTICLE-long.md` in the repo.*
