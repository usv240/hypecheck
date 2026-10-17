# HypeCheck: a press-office agent that won't publish a health claim the paper doesn't make

*Strands Decider 2B + Claude on Amazon Bedrock, hosted on Amazon Bedrock AgentCore Runtime. Pattern: `#guardrails`.*

**HypeCheck reads a draft health press release next to the paper it reports, flags every
sentence that claims more than the study found, has Claude rewrite it, and re-checks the rewrite
before anything is published.**

Two numbers first:
- **False flags.** On 345 press releases that experts judged faithful to their paper, HypeCheck
  wrongly flagged 6.7%. Claude, asked the same question, flagged 29.6% (Sonnet 4.6), 40.0% (Opus 4.6)
  and 44.9% (Haiku 4.5).
- **Overall accuracy.** On the full benchmark of 563 expert-labelled pairs, Strands Decider scores
  macro-F1 0.498 with no training on the task. The best published system, which was trained on
  it, scores 0.4735.

- Live demo: https://d174bz5yly61n4.cloudfront.net (the "New here?" tour takes 30 seconds)
- Code, Apache-2.0: https://github.com/usv240/hypecheck
- Reusable pattern: https://github.com/usv240/hypecheck/tree/main/decision_pattern
- Video: *(YouTube link)*

## The problem starts before the news

A study finds that people who use an urgent cancer-referral pathway *tend* to live longer. The
university press release says the pathway *is saving lives*. The newspapers copy the release.

Sumner and colleagues read 462 UK university press releases next to their papers (*BMJ*, 2014):
- 33% turned an association into a cause.
- 36% presented animal results as if they were about people.
- 40% gave advice the paper did not give.

When the release exaggerated, 58–86% of the news did too; when it didn't, only 10–18% did. A
randomised trial in nine real press offices then showed that aligning releases with the evidence
made news headlines more accurate, with no drop in coverage (Adams et al., *BMC Medicine*, 2019).

The one free service that reviewed releases before publication was run by people, and it closed
in 2018. Nothing has automated the job since. That is the gap HypeCheck fills.

## The decision handed to Decider

Strands Decider is a small, open decision model. It does not write text: it reads text and a
typed question, and returns an answer with a probability.

HypeCheck asks it one question over and over:

> **How strong is the relationship this statement claims?**
> no relationship < association (correlational) < hedged cause ("may reduce") < definite cause ("reduces")

The question is asked once of the paper's conclusion and once of every sentence in the draft. A
sentence's **overclaim score** is the probability that it sits on a higher rung than the paper:

```
P(overclaim) = Σ over rungs i > j of  P(sentence = i) · P(paper = j)
```

Two document-level questions ride in the same pass, and neither ever blocks on its own:
- **Advice.** Does the release tell readers what to do more strongly than the paper does?
- **Animal to human.** Does it present an animal or lab result as if it applied to people?

### Where the decision sits

The gate is a Strands `InterventionHandler.before_tool_call` on the agent's `publish_release`
tool. Each sentence lands in one of three zones:

| Zone | When | Agent action |
|---|---|---|
| BLOCK | score above the strict threshold | `Guide`: Claude gets its turn back with the blocked sentences and why, and rewrites only those |
| REVIEW | between the strict and the lenient threshold | not blocked; written into the publish record for an editor (our low-confidence handling) |
| OK | below both | passes |
| — | still blocked after 3 rewrites | `Confirm`: a person decides |

Every rewrite goes through the same gate. In one recorded run on AgentCore, Claude's first
rewrite still overclaimed (score 0.56). Decider caught it, and the third round was clean.

```
draft → Claude (Bedrock, on AgentCore Runtime) ── publish_release ──▶ ClaimFidelityGate
            ▲                                                         │ Decider 2B, per sentence
            └──── Guide: "sentence 1 reads as a definite cause;      │
                   the paper is hedged" ◀─────────────────────────────┤ BLOCK
                                                                      ▼ OK / REVIEW
                                                   Proceed → newsroom outbox (+ review list)
```

## Why a decision model and not the LLM

We measured three reasons.

**1. It doesn't cry wolf.**
- Asked directly, every Claude model over-flagged faithful releases: 29.6–44.9%.
- That fits a 2025 study finding that language models overgeneralise science in 26–73% of summaries.
- The same tendency is why Claude's own rewrite is re-checked by Decider rather than trusted.

**2. Its probabilities support a promise.**
- The Decider documentation calls its 0.9 / 0.5 routing bands illustrative and says to measure on
  your own traffic. We did, with *conformal calibration*: a standard statistical recipe that sets
  the cut-off on known-faithful examples so that at most a chosen share of them would be flagged.
- We fitted on 78 training pairs, aiming for at most 10%. On 441 pairs it had never seen, it flagged
  7.7% (95% CI 5.6–10.6%).
- Closed LLM APIs do not expose option probabilities, so this recipe is not available for them.

**3. It's fast, and many questions on one text cost almost nothing.**
- About 160 ms per decision on a laptop GPU, with zero tokens.
- A four-sentence release takes eight decisions.
- Claude Haiku took about 2 s per judgement and Opus about 5 s.

## Results

All test data is published expert coding that we did not write. Every experiment's predictions and
pass/fail rule were committed before the run (`research/PREREGISTRATION-*.md`). The ones that
failed are reported alongside the ones that passed.

Two terms used below:
- **AUROC:** the chance that a randomly picked exaggerated release scores higher than a randomly
  picked faithful one. 0.5 is a coin flip; 1.0 is perfect.
- **Macro-F1:** a 0–1 accuracy score that weighs the three labels equally.

| Measurement | Decider 2B, zero-shot | Claude on Bedrock, same question |
|---|---|---|
| Faithful releases wrongly flagged | **6.7%** | Haiku 4.5 44.9% · Sonnet 4.6 29.6% · Opus 4.6 40.0% |
| Exaggeration macro-F1, 563 pairs (Wright & Augenstein 2021) | **0.498** (published best 0.4735, trained) | 0.358 · 0.401 · 0.460 |
| Exaggerates-vs-not AUROC | **0.716** | 0.570 · 0.580 · 0.663 |
| Conformal promise vs measured | ≤10% → 7.7% | — |
| Exaggerations caught at the strict threshold | 39% (CI 30–47%) | Haiku at a similar false-flag rate: 18% |
| Advice stronger than the paper, 116 real releases (InSciOut), AUROC | 0.84 | — |
| Causal strength, 3,061 PubMed sentences (Yu 2019), AUROC | 0.894 | — |
| Time per decision | 160 ms laptop GPU · ~0.9 s EC2 CPU | 2.0 s · 0.9 s · 5.3 s |
| Cost per sentence checked | $0.00018 on the c7i CPU server; $0 on owned hardware | $0.00051 · $0.00097 · $0.0056 |

How the costs were worked out:
- **Claude:** the tokens actually used in our runs, multiplied by Bedrock list prices.
- **Decider:** the c7i.4xlarge on-demand rate ($0.714/h) multiplied by 0.9 s per decision, at full use.

On a GPU we already own, the decision is free. The gap that matters most for a gate, though, is
the false-flag rate.

## How it runs on AWS

- **Amazon Bedrock AgentCore Runtime** hosts the Strands agent.
  - We used direct code deploy (a zip in S3, no container); the deploy script is in the repo.
  - The agent streams every step back to the page.
- **Amazon Bedrock** serves Claude Sonnet 4.6.
- **Amazon EC2** runs Strands Decider 2B and the web app.
  - The web app queues concurrent users and shows each sentence turning red, amber or green as
    Decider reads it.
  - **Amazon CloudFront** provides HTTPS.
- **AWS Systems Manager Parameter Store** holds the key that protects the Decider endpoint the
  AgentCore agent calls.
- If AgentCore is unavailable, the page runs the identical agent on the EC2 server instead.

## What we learned

- **Decompose the judgement.** Asking Decider "is A stronger than B?" scored macro-F1 0.41.
  Asking it to rate each claim on its own and then comparing the two ratings scored 0.50. It is
  better at "how strong is this?" than at comparisons.
- **Calibrate, as the docs say.** At default settings Decider under-called definite causal claims
  in PubMed sentences (F1 0.63), yet it ranked them very well (AUROC 0.89). Choosing the cut-off
  from labelled data, rather than using a hand-picked band, is what makes the gate usable.
- **Pre-register, then report the misses.** Two pre-registered experiments failed:
  - Combining three signals did not beat one.
  - A better prompt wording missed our adoption bar by 0.0014.

  We kept the original method in both cases. A one-time label-order mistake was caught because the
  first score came out as a mirror image (AUROC 0.106). It is recorded in the repo.

## Limits, measured

- At the strict threshold the gate catches 39% of exaggerations. It is a safety net; a press
  officer still reads the draft.
- The animal-to-human check is weak (AUROC 0.61, 45 releases), so it is shown as a hint only.
- The test set has 563 pairs, which gives wide intervals. The edge over 0.4735 is one run.
- The demo server runs Decider on CPU, about six times slower than a GPU, because a GPU quota
  request was still pending.

## The reusable pattern

The `decision_pattern/` folder in the repo contains:
- the typed question and option set;
- the overclaim score;
- `ClaimFidelityGate` (the intervention), with BLOCK / REVIEW / OK zones;
- `calibrate.py` (conformal thresholds with a stated false-flag rate);
- a standard-library client;
- offline tests.

`examples/leaflet_gate.py` runs the same gate unchanged on a patient-leaflet writer. There it
caught "people who took statins were less likely to develop dementia" stated as fact, when the
study was observational. The pattern fits anywhere text must not say more than its source:
summaries, RAG answers, release notes and patient materials.

## Sources

- Sumner P, et al. *BMJ* 2014;349:g7015.
- Adams RC, et al. *BMC Medicine* 2019;17:91.
- Bratton L, et al. *Wellcome Open Research* 2019 and 2020.
- Wright D, Augenstein I. EMNLP 2021.
- Yu B, Li Y, Wang J. EMNLP 2019.
- InSciOut data, figshare 903704 (CC BY 4.0).
- Peters U, Chin-Yee B. *Royal Society Open Science* 2025.
- Angelopoulos AN, Bates S. *A Gentle Introduction to Conformal Prediction*, 2021.
- Strands Decider: github.com/strands-labs/strands-decider.
