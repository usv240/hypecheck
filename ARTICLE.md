# HypeCheck: a press-office agent that will not publish a health claim the paper doesn't make

*Strands Decider 2B + Claude on Amazon Bedrock. Pattern: `#guardrails`.*

On 563 expert-labelled press-release/paper pairs, Strands Decider 2B detects exaggeration with
macro-F1 0.498 zero-shot, above the best published system (0.4735, trained), and when its
threshold is fitted by conformal calibration it flags only 7.7% of faithful releases, inside
the 10% it promises. Asked the same question, Claude Haiku 4.5 flags 45% of them.

**HypeCheck reads a draft health press release next to the paper it reports, flags every
sentence that claims more than the study found, has Claude rewrite it, and re-checks the
rewrite before anything is published.**

- Live demo: https://d174bz5yly61n4.cloudfront.net (Decider on an EC2 CPU box; the laptop GPU numbers below are faster)
- Repo, Apache-2.0: https://github.com/usv240/hypecheck
- Video: *(link)*

## The problem is upstream of the news

A study finds that people who use an urgent cancer-referral pathway *tend* to live longer.
The university press release says the pathway *is saving lives*. The newspapers copy the
release.

Sumner and colleagues read 462 UK university press releases and their papers (BMJ, 2014).
Forty per cent gave advice the paper did not, 33% turned an association into a cause, and 36%
presented animal results as human. When the release exaggerated, 58–86% of the news did too;
when it didn't, 10–18%. A randomised trial then showed the fix works: releases aligned with the
evidence produced more accurate headlines with no loss of coverage (Adams et al., BMC
Medicine, 2019). The one free human service that reviewed releases before publication closed
in 2018. Nothing automated it.

## The decision handed to Decider

One typed question, asked over and over:

> How strong is the relationship this statement claims?
> `no_relationship` < `correlational` < `conditional_causal` < `direct_causal`

It is asked once of the paper's conclusion and once of every sentence in the draft. The
overclaim score for a sentence is the probability that it sits on a higher level than the
paper:

```
P(overclaim) = Σ_{i>j} P(sentence = i) · P(paper = j)
```

Two document-level questions ride in the same pass: a four-level *advice* scale (does the
release tell readers what to do more strongly than the paper does?) and a yes/no on
animal-to-human inference.

The gate is a Strands `InterventionHandler.before_tool_call` on the `publish_release` tool.
A sentence over the threshold returns `Guide` with the offending sentences, so Claude rewrites
only those and calls the tool again; the rewrite is scored again; after three rounds the gate
returns `Confirm` and a person decides; clean text returns `Proceed`.

```
draft ──▶ Claude (Bedrock) ──publish_release──▶ ClaimFidelityGate ──▶ Decider 2B (local)
                ▲                                     │ per sentence, ~160 ms
                └──── Guide: "sentence 1 reads as a definite cause; the paper is hedged" ◀──┘
                                                      │ clean
                                                      ▼ Proceed → newsroom outbox
```

## Why a decision model, not the LLM

Three reasons, each measured.

**It can't be argued with.** Claude cannot negotiate with a probability. When we asked Claude
to judge exaggeration directly, it over-flagged: Haiku 4.5 called 45% of faithful releases
exaggerated, Sonnet 4.6 30%. That matches the 2025 finding that LLMs overgeneralise science
26–73% of the time, which is also why the rewrite is re-checked by Decider rather than trusted.

**Many questions on one text are nearly free.** The strength question, the advice question and
the animal question share the encoded state. A four-sentence release costs eight Decider calls
and about 1.3 s on a laptop GPU.

**The confidence is calibrated enough to promise something.** The Decider docs say the 0.9/0.5
routing bands are illustrative and should be measured on your own traffic. We did that with
split conformal prediction: fit the threshold on 78 faithful training pairs at α = 0.10, and
the promise is that at most 10% of faithful sentences are flagged. On 441 held-out
non-overclaim pairs it flagged 7.7% (95% CI 5.6–10.6%).

## Results

Every test case comes from a published expert-coded study; we authored none. Every number
was pre-registered (`research/PREREGISTRATION-*.md`) before the run, and the predictions we
missed are recorded alongside the ones we hit.

| Measurement | Decider 2B (zero-shot) | Comparison |
|---|---|---|
| Exaggeration, 3-class macro-F1 on 563 pairs (Wright & Augenstein 2021) | **0.498** | best published: 0.4735 (MT-PET, trained); Haiku 4.5: 0.358; Sonnet 4.6: 0.401 |
| Exaggerates-vs-not AUROC | 0.716 | Haiku 0.570; Sonnet 0.580 |
| **False flags on faithful releases** (the negative control) | **7.7%** at the calibrated threshold | Haiku 45%; Sonnet 30% |
| Recall of exaggerations at that false-flag budget | 39% (CI 30–47%) | Haiku at ~10% false flags: 18% |
| Advice inflation, 116 real UK releases (InSciOut), AUROC | 0.84 | — |
| Causal strength, 3,061 PubMed sentences (Yu 2019), direct-vs-correlational AUROC | 0.894 | — |
| Latency per decision | 160 ms median, RTX 4070 Laptop; ~0.9 s on a c7i CPU | Haiku ~2.0 s; Sonnet ~0.95 s per pair |
| Tokens per 563 checks | 0 | Haiku: 120k in + 34k out |

End to end on the demo release: two rounds, 16 decisions, 8.5 s wall, of which 2.2 s is Decider.

## What we learned

- **Decompose the judgement.** Asking Decider to compare the pair directly scored macro-F1
  0.41. Classifying each side's strength separately and comparing the distributions scored
  0.50. The model is better at "how strong is this claim?" than at "is A stronger than B?"
- **Calibrate on your own data, as the docs say.** The default argmax under-called direct
  causal claims on PubMed sentences (F1 0.63 despite AUROC 0.89). A fitted threshold, not a
  hand-picked band, is what makes the gate usable.
- **Pre-register, then report misses.** Two predictions failed (a combination of three
  signals did not beat one; the animal check is weak) and one scoring bug was caught by a
  mirror-image AUROC. Writing the rule down first made those easy to report.

## Limits, measured

- Recall at the strict threshold is 39%. The gate is a safety net, not a complete reviewer;
  a press officer still reads the draft.
- The animal-to-human check scores AUROC 0.61 on 45 releases. It is shown as a hint, never
  used to block.
- 563 pairs give wide intervals; the edge over the published 0.4735 is one run, not a
  settled result.
- Decider on CPU is six times slower than on a GPU; the live demo runs on CPU because a
  GPU quota was not granted in time.

## The reusable pattern

`decision_pattern/` in the repo: `fidelity.py` (the typed questions and the overclaim score),
`gate.py` (`ClaimFidelityGate`, the intervention), `calibrate.py` (conformal threshold with a
stated false-flag rate) and a standard-library client. `examples/leaflet_gate.py` runs the
same gate on a patient-leaflet writer with no code changes beyond the tool name. Tests run
offline with a fake decider.

Use it anywhere derived text must not say more than its source: summaries, RAG answers,
release notes, patient materials.

## Sources

Sumner et al., BMJ 2014;349:g7015 · Adams et al., BMC Med 2019;17:91 · Bratton et al.,
Wellcome Open Res 2019/2020 · Wright & Augenstein, EMNLP 2021 · Yu, Li & Wang, EMNLP 2019 ·
InSciOut data, figshare 903704 (CC BY 4.0) · Peters & Chin-Yee, R Soc Open Sci 2025 ·
Angelopoulos & Bates, "A gentle introduction to conformal prediction", 2021.
