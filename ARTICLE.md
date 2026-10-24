# HypeCheck: an agent that won't publish a health claim the paper doesn't make

*Strands Decider 2B + Claude on Amazon Bedrock, hosted on Amazon Bedrock AgentCore Runtime · Pattern: Guardrails · `#strands-decider-2b` `#guardrails`*

A study finds that patients who use an urgent cancer-referral pathway *tend* to live longer. The press release says the pathway *is saving lives*. The news copies the press release.

**HypeCheck reads a draft health press release next to the paper it reports, flags every sentence that claims more than the study found, has Claude rewrite it, and checks the rewrite again before anything is published.**

- **Watch (2:44):** https://youtu.be/FYuR9-ymPR4
- **Try it:** https://d174bz5yly61n4.cloudfront.net (there is a 30-second tour)
- **Code (Apache-2.0):** https://github.com/usv240/hypecheck
- **Reusable decision pattern:** https://github.com/usv240/hypecheck/tree/main/decision_pattern
- **HypeWatch:** https://d174bz5yly61n4.cloudfront.net/hypewatch, a year of real NIH releases, checked every morning

![HypeCheck: the paper says "could be efficacious", the release says "is saving lives", and the claim ladder shows the gap](https://raw.githubusercontent.com/usv240/hypecheck/main/docs/hero.jpg)

## In 60 seconds

- **The agent:** a Strands agent that drafts and publishes health press releases. Its `publish_release` tool cannot run until every sentence has been checked against the paper.
- **The decision Decider makes:** *How strong is the relationship this sentence claims?* Asked once about the paper's conclusion, then about every sentence of the draft. If a sentence sits higher than the paper, it is an overclaim.
- **The pattern:** Guardrails. Clean text → **Proceed**. Overclaim → **Guide** (Claude rewrites, Decider re-checks). Still overclaiming after three rewrites → **Confirm** (a person decides). No paper, or Decider unreachable → **Deny** (fails closed).
- **Why Decider and not Claude:** on 563 expert-labelled pairs, Decider wrongly flags **6.7%** of honest releases; Claude asked the same question flags **30–45%**. Decider does it in **0.16 s and 0 tokens** per sentence.
- **Tested on text nobody chose for us:** 85 real NIH press releases and 170 Claude-written summaries of the same papers.
- **Reusable:** `pip install "git+https://github.com/usv240/hypecheck"`, plus a free REST API, an MCP connector, calibration on your own data, and a CloudFormation stack for your own AWS account.

## Why it matters

In 2014, researchers read 462 university press releases next to their papers. A third turned "is linked to" into "causes", and when the release exaggerated, most of the news did too (Sumner et al., *BMJ*).

Health news changes what people do. After one burst of coverage questioning statins, researchers estimated that about 219,000 people in the UK stopped taking them (Matthews et al., *BMJ*, 2016; the authors note the study cannot prove the coverage caused it).

The fix is known to work. In a randomised trial across nine press offices, releases that matched the evidence produced more accurate headlines and got just as much coverage (Adams et al., *BMC Medicine*, 2019). The one free service that checked releases before publication was run by people, and it closed in 2018. Nothing has automated it until now.

## What HypeCheck does, end to end

1. **Paste the draft and the paper's conclusion**, or just a PubMed ID and HypeCheck fetches the conclusion for you.
2. **Decider reads every sentence** and places it on a four-rung ladder: *no relationship → linked → may cause → causes*. Each sentence lands in a zone:
   - **BLOCK**: it clearly claims more than the paper. Publishing stops.
   - **REVIEW**: Decider is unsure. It does not block, but an editor sees it in the publish record. This is how low confidence is handled instead of guessing.
   - **OK**: within what the paper supports.
3. **Claude on Amazon Bedrock rewrites only the blocked sentences**, with the reason attached. Decider reads the rewrite again. In one recorded run Claude's first rewrite still overclaimed; Decider caught it and the second passed. After three failed rounds, a person decides.
4. **Publish with a decision receipt.** Every verdict ships the rung probabilities, scores, thresholds and the rule, hashed. Anyone can recompute it with `/v1/verify` and no model, and a press officer can hand it to an editor.
5. **Every number has an ⓘ.** Each score, threshold and chart on the site explains itself in a sentence. Light and dark themes; works on a phone.
6. **HypeWatch** runs the same check every morning on real NIH releases, with the paper's own words next to every flag.
7. **AI-summary check:** the same gate applied to Claude's summaries of scientific papers.
8. **For builders:** free API key in one click, MCP connector for any agent, calibration on your own labelled pairs, one-click deploy to your own AWS account.

![A live check: "saving lives" is blocked at 0.80; the ladder shows the sentence at "causes" and the paper at "may cause"](https://raw.githubusercontent.com/usv240/hypecheck/main/docs/demo.jpg)

## Why a decision model, not Claude, does the judging

We asked Claude on Bedrock the same question on 563 press-release/paper pairs coded by experts (Sumner et al.'s InSciOut data, via Wright & Augenstein, EMNLP 2021).

| | Decider 2B (no training) | Claude Haiku 4.5 | Claude Sonnet 4.6 | Claude Opus 4.6 |
|---|---|---|---|---|
| Honest releases wrongly flagged | **6.7%** (95% CI 4.1–9.4%) | 44.9% | 29.6% | 40.0% |
| Overall accuracy (macro-F1; best published system 0.474) | **0.498** | 0.358 | 0.401 | 0.460 |
| Time per decision | **0.16 s** on a laptop GPU | 2.0 s | 0.9 s | 5.3 s |
| Cost per sentence | **$0.0002** on our CPU server, $0 on your own GPU | $0.0005 | $0.0010 | $0.0056 |

**In one line:** for every 1,000 honest sentences, Claude Sonnet as the judge wrongly blocks 296 and costs $0.97; HypeCheck wrongly blocks 67 and costs $0.18.

- **Fewer false alarms.** A gate that cries wolf gets switched off. Claude over-flags; Decider, with a threshold fitted to data, does not.
- **A threshold you can promise.** The Decider docs say to measure the cut-off on your own data. We did, with conformal calibration: at most 10% of known-honest sentences may be flagged. On 441 pairs the model had never seen, it flagged 7.7%. The promise held.
- **It can't be argued with.** Decider returns a number and plain code decides. Claude can be talked into anything; a receipt with a hash cannot.
- **Two more baselines, so the model earns its place.** A keyword rule (flag every causal verb) catches a few more exaggerations but flags one honest release in four (26%). Amazon Bedrock Guardrails' contextual grounding check, built for a neighbouring problem, ranks exaggerations at chance here (AUROC 0.50 vs 0.72 for Decider): grounding catches invented facts, and a release that turns "could" into "saves lives" keeps all the same facts. The two belong side by side.

Decider's accuracy is level with the best published system, which was trained on this task. Decider was not.

## Tested on text nobody chose for us

**HypeWatch.** Every NIH research release since February 2023 that cites its paper by DOI: 85 releases, checked against their abstracts. 15% had a headline or opening sentence the gate would block, under a stricter rule for public flags. Claude's suggested rewrites passed Decider 67% of the time, below the 85% we predicted, so the page calls them suggestions, not fixes. Ben Goldacre's *BMJ* editorial on the Sumner study asked for every release to be linked to its paper and opened to review, to create "an information trail, and accountability among peers and the public". HypeWatch automates part of that for one major publisher of health news.

**AI summaries.** A 2025 study found AI summaries nearly five times as likely as expert ones to state findings more broadly than the paper (Peters & Chin-Yee, *Royal Society Open Science*). We asked Claude Sonnet 4.6 and Haiku 4.5 to summarise the same 85 NIH papers. About 1 in 9 summaries had a sentence the gate blocks (11.8% and 10.6%). Example: a paper says opioid-use-disorder medication in jails "was associated with" fewer deaths; both summaries said it "can save lives". The gate fixed 9 in 10 of them.

## How it runs on AWS

- **Amazon Bedrock AgentCore Runtime** hosts the Strands agent, deployed as plain code.
- **Amazon Bedrock** serves Claude Sonnet 4.6, with Haiku 4.5 as the fallback when Sonnet is throttled.
- **Amazon EC2** runs Decider 2B and the web app behind **Amazon CloudFront**; several Decider servers with failover.
- **AWS Systems Manager Parameter Store** holds the key that protects the Decider endpoint.
- If AgentCore is unavailable, the page runs the same agent on EC2. If Decider cannot be reached, the gate returns **Deny** rather than letting text through unchecked.

## The reusable pattern

`decision_pattern/` in the repo is a self-contained package: the typed Decider question and option set, a Strands `InterventionHandler` that sits in front of any tool, the conformal calibration script, the receipt builder and verifier, and a README that walks through all four actions. It knows nothing about press releases. The same gate ran unchanged on a patient-leaflet writer and caught "statin users were less likely to develop dementia" stated as fact from an observational study. Use it anywhere text must not say more than its source: summaries, RAG answers, patient materials, marketing copy.

## What we learned

1. **Ask Decider one judgement at a time.** "How strong is this claim?" asked of each side, then compared in code, scored 0.50. "Is A stronger than B?" asked directly scored 0.41. (Filed upstream as [strands-decider#103](https://github.com/strands-labs/strands-decider/issues/103).)
2. **Measure the cut-off, don't assume it.** Decider under-called "causes" sentences at the default, yet *ranked* them well. A threshold fitted on labelled data fixed it.
3. **`Guide` needs a nudge.** Claude stopped to ask the user until the system prompt said "rewrite and call the tool again in the same turn".
4. **A tool against overclaiming must not overclaim.** Our site once said Decider scored "above the best published system". The published score sat inside our 95% interval, so it now says "level with". The false-alarm gap to Claude survived the same test easily.

## Limits we measured

- At the strict cut-off it catches **39%** of exaggerations: a safety net, not an editor.
- It checks claim strength only, not numbers, doses or invented facts.
- HypeWatch and AI-summary rates are Decider's flags, not human labels, which is why every flag sits next to the paper's own words.
- English biomedicine only; the live demo runs Decider on a CPU, about six times slower than a GPU.

**How to trust the numbers.** All ten experiments were pre-registered, and every missed prediction is in the repo, along with every miss at the strict threshold listed by direction. `python research/reproduce.py` (or the [notebook](https://github.com/usv240/hypecheck/blob/main/notebooks/reproduce.ipynb)) recomputes all 22 headline numbers offline in about ten seconds. An AI coding assistant wrote most of the code under my direction; all Claude usage during the build cost at most $9.04 on Bedrock.

*Sources: Sumner et al., BMJ 2014 · Matthews et al., BMJ 2016 · Adams et al., BMC Medicine 2019 · Goldacre, BMJ 2014;349:g7465 · Wright & Augenstein, EMNLP 2021 · Yu et al., EMNLP 2019 · Peters & Chin-Yee, R Soc Open Sci 2025 · InSciOut (CC BY 4.0)*
