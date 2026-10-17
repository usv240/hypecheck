# HypeCheck

HypeCheck reads a draft health press release next to the paper it reports, flags every sentence
that claims more than the study found, has Claude rewrite it, and re-checks the rewrite before
anything is published.

Built for the AWS Agent Experience Hackathon: Strands Decider. Tags: `#strands-decider-2b`
`#guardrails`.

**Live demo:** https://d174bz5yly61n4.cloudfront.net (Decider on an EC2 CPU instance, Claude on Bedrock via the instance role). **Article:** [ARTICLE.md](ARTICLE.md). **Video script:** [VIDEO.md](VIDEO.md).

![Round 1 blocks "is saving lives" at 0.80; round 2 publishes the rewrite](docs/demo.jpg)

- Decision model: [Strands Decider 2B](https://github.com/strands-labs/strands-decider), local, ~160 ms per sentence.
- Generative model: Claude on Amazon Bedrock, driven by the Strands Agents SDK.
- The decision handed to Decider: *does this sentence claim a stronger relationship than the paper's conclusion?*
  Asked once per sentence, and again on every rewrite, so Claude cannot talk its way past it.

## Why

Most exaggeration in health news starts in the press release, not the newsroom
(Sumner et al., *BMJ* 2014: 462 releases; causal overclaims in 33%, and when the release
exaggerated, 81% of news did too). A randomised trial showed that aligning releases with the
evidence made news more accurate with no loss of coverage (Adams et al., *BMC Medicine* 2019).
No tool checks a draft release against its own paper; the one human service that did closed in 2018.

## The reusable decision pattern

`decision_pattern/` is the part other builders can drop into their own agents:

| File | What it is |
|---|---|
| `fidelity.py` | The typed questions. A 4-level claim-strength `choice` (no relationship < correlational < conditional causal < direct causal) asked of the source and of each derived sentence, and the overclaim score `P(derived > source)`. Two advisory `noul`s ride in the same request. |
| `gate.py` | `ClaimFidelityGate`, a Strands `InterventionHandler.before_tool_call`. Flagged sentences → `Guide` (the model rewrites); still flagged after N rounds → `Confirm` (a person decides); clean → `Proceed`. |
| `calibrate.py` | Fits the threshold with split conformal prediction so it carries a stated false-flag rate, instead of the 0.9/0.5 bands the Decider docs call illustrative. |
| `decider.py` | A standard-library HTTP client for `strands-decider serve`. |

Use it for anything that must not say more than its source: summaries, RAG answers, patient leaflets, release notes.
`examples/leaflet_gate.py` runs the identical gate on a patient-leaflet writer. `pytest -q` runs the offline tests (fake decider, no Bedrock).

```python
from decision_pattern import Decider, ClaimFidelityGate, load_threshold

gate = ClaimFidelityGate(Decider(), source=lambda: paper_conclusion,
                         tool_name="publish_release", text_arg="text",
                         threshold=load_threshold("research/results/calibration/summary.json", "0.1"))
agent = Agent(model="us.anthropic.claude-sonnet-4-6", tools=[publish_release], interventions=[gate])
```

## Results

All test cases come from published expert-coded studies; none were written by us.
Every number below is pre-registered in `research/PREREGISTRATION-*.md`, with per-item outputs in `research/results/`.

| Measurement | Result |
|---|---|
| Exaggeration detection, 563 expert-labelled release/abstract pairs (Wright & Augenstein 2021), 3-class macro-F1, zero-shot | **0.498** (published best, trained: 0.4735) |
| Same, exaggerates-vs-not AUROC | 0.716 |
| Conformal threshold fitted on 78 faithful train pairs, α = 0.10 → false-flag rate on 441 held-out non-overclaim pairs | **7.7%** (95% CI 5.6–10.6%), promise kept |
| Recall of exaggerations at that threshold | 39% (CI 30–47%); Claude Haiku 4.5 at the same false-flag level: 18% |
| Claude Haiku 4.5 asked the same question, unthresholded | flags 45% of faithful releases |
| Advice inflation on 116 real 2011 UK press releases (InSciOut, Sumner et al.), AUROC | 0.84 |
| Animal→human inference, 45 releases, AUROC | 0.61 — weak; kept only as a hint |
| Causal-language strength, 3,061 PubMed sentences (Yu et al. 2019), direct-causal vs correlational AUROC | 0.894 |
| Latency per sentence, RTX 4070 Laptop | 160 ms median; Claude Haiku: ~2,000 ms |

## Run it

```bash
pip install strands-decider  # or from the repo for CUDA/MLX extras
strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8099

pip install -r requirements.txt            # needs AWS credentials with Bedrock access
python -m hypecheck.agent --draft examples/referral_release.txt \
    --conclusion "Use of the urgent referral pathway could be efficacious."
uvicorn hypecheck.web:app --port 8080      # the demo UI
```

To reproduce the evaluation, fetch the public datasets (links in `research/PREREGISTRATION-spike.md`)
into `data/`, install `requirements-research.txt`, and run the scripts in `research/`.

## Deploy on AWS

`deploy/ec2-bootstrap.sh` builds a single instance running Decider (GPU if present, CPU otherwise)
and the web app, with Bedrock reached through the instance role.

## Licence

Apache-2.0. Benchmark data is not redistributed; see each dataset's own licence.
