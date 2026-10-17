# HypeCheck

**HypeCheck reads a draft health press release next to the paper it reports, flags every sentence
that claims more than the study found, has Claude rewrite it, and re-checks the rewrite before
anything is published.**

On 345 press releases that experts judged faithful to their paper, HypeCheck wrongly flagged
**6.7%**. Claude asked the same question flagged 29.6% (Sonnet 4.6) to 44.9% (Haiku 4.5). On the
full 563-pair benchmark it scores macro-F1 **0.498 zero-shot**, against 0.4735 for the best
published system, which was trained on the task.

| | |
|---|---|
| **Live demo** | https://d174bz5yly61n4.cloudfront.net (click *New here? 30-second tour*) |
| **Decision pattern** | [`decision_pattern/`](decision_pattern/README.md): a claim-fidelity gate, `#guardrails` |
| **Article** | [ARTICLE.md](ARTICLE.md) (also on AWS Builder Center) |
| **Video** | *(YouTube link)* |
| **Tags** | `#strands-decider-2b` `#guardrails` |

![Round 1 blocks "is saving lives" at 0.80; round 2 publishes the rewrite](docs/demo.jpg)

## The decision handed to Strands Decider

Decider gets one typed question, asked of the paper's conclusion and then of every sentence in the draft:

> *How strong is the relationship this statement claims?*
> `no_relationship` < `correlational` < `conditional_causal` < `direct_causal`

The overclaim score is `P(sentence level > paper level)`. A Strands `InterventionHandler` runs it
in `before_tool_call` on `publish_release`. Each sentence then lands in one of three zones, and
both thresholds are conformal, fitted on held-out expert-labelled data:

| Zone | Rule | What happens |
|---|---|---|
| **BLOCK** | score > 0.50 (α = 0.10) | `Guide`: Claude rewrites those sentences, then the rewrite is re-checked |
| **REVIEW** | 0.40 < score ≤ 0.50 (α = 0.20) | Low confidence. Doesn't block; listed for an editor in the publish record |
| **OK** | score ≤ 0.40 | Passes |
| | still blocked after 3 rewrites | `Confirm`: a person decides |

Decider only classifies; plain code decides; Claude cannot argue with a number. In one recorded
AgentCore run, Claude's first rewrite *still* overclaimed (0.56). The gate caught it and the
third round was clean.

## Why this problem

- **The exaggeration starts upstream.** Most exaggeration in health news starts in the press
  release, not the newsroom (Sumner et al., *BMJ* 2014, 462 releases). A third of releases turned
  correlation into causation. When the release exaggerated, 81% of the news did too.
- **Fixing the release works.** A randomised trial in 9 press offices showed that aligning releases
  with the evidence made headlines more accurate with no loss of coverage (Adams et al.,
  *BMC Medicine* 2019).
- **Nobody has automated it.** The only free human pre-publication review service closed in 2018,
  and no tool checks a draft against its own paper.

## Results

All test data is published expert coding that we did not write. Every experiment was
pre-registered before it ran ([research/](research/README.md)), including the two whose
predictions failed.

| Measurement | Decider 2B (zero-shot) | Claude on Bedrock, same question |
|---|---|---|
| Faithful releases wrongly flagged (the negative control) | **6.7%** | Haiku 4.5 44.9% · Sonnet 4.6 29.6% · Opus 4.6 40.0% |
| Exaggeration macro-F1, 563 pairs (Wright & Augenstein 2021) | **0.498** (published best 0.4735, trained) | Haiku 0.358 · Sonnet 0.401 · Opus 0.460 |
| Exaggerates-vs-not AUROC | **0.716** | Haiku 0.570 · Sonnet 0.580 · Opus 0.663 |
| Conformal promise (≤10% false flags) vs measured, 441 unseen non-overclaim pairs | 7.7% (95% CI 5.6–10.6%) | — |
| Recall at that strict threshold | 39% (CI 30–47%) | Haiku at ~10% false flags: 18% |
| Advice inflation, 116 real UK releases (InSciOut), AUROC | 0.84 | — |
| Causal strength, 3,061 PubMed sentences (Yu 2019), direct-vs-correlational AUROC | 0.894 | — |
| Latency per decision | 160 ms (laptop RTX 4070) · ~0.9 s (EC2 CPU) | Haiku ~2.0 s · Sonnet ~0.9 s · Opus ~5.3 s |
| Cost per sentence checked | $0.00018 (c7i CPU at full use) · $0 on owned hardware | Haiku $0.00051 · Sonnet $0.00097 · Opus $0.0056 |

Cost basis:
- **Claude:** tokens actually used across 563 checks × Bedrock list price (Haiku 4.5 $1/$5, Sonnet 4.6 $3/$15, Opus 4.6 $5/$25 per million tokens in/out).
- **Decider:** c7i.4xlarge on-demand at $0.714/h × 0.9 s per decision.

**Measured limits:**
- 39% recall at the strict threshold: it is a safety net, not a full reviewer.
- The animal-to-human hint is weak: AUROC 0.61 on 45 releases, so it never blocks.
- 563 pairs give wide intervals.
- The demo server runs Decider on CPU, because a GPU quota request was still pending.

## Architecture on AWS

![HypeCheck on AWS](docs/architecture.svg)

- **Amazon Bedrock AgentCore Runtime** hosts the Strands agent (`agentcore_app.py`).
  - Direct code deploy, no container: `deploy/agentcore_deploy.py`.
  - Streams every event.
- **Amazon Bedrock** serves Claude Sonnet 4.6, which drives the agent and writes the rewrites.
- **Amazon EC2** (Elastic IP) runs Strands Decider 2B and the web app, which queues runs and
  streams sentence-by-sentence progress.
- **Amazon CloudFront** gives HTTPS.
- **AWS Systems Manager Parameter Store** holds the key that guards the Decider endpoint
  AgentCore calls.
- **Fallback:** if AgentCore fails, the web app runs the identical agent in-process.

## The reusable decision pattern

[`decision_pattern/README.md`](decision_pattern/README.md) covers the typed question and option
set, the wiring, the actions, and how to calibrate on your own data. In short:

```python
from decision_pattern import Decider, ClaimFidelityGate, load_threshold

gate = ClaimFidelityGate(Decider(), source=lambda: paper_conclusion,
                         tool_name="publish_release", text_arg="text",
                         threshold=load_threshold("calibration.json", "0.1"),
                         review_threshold=load_threshold("calibration.json", "0.2"))
agent = Agent(model="us.anthropic.claude-sonnet-4-6", tools=[publish_release], interventions=[gate])
```

`examples/leaflet_gate.py` runs the identical gate on a patient-leaflet writer: it caught "less
likely to develop dementia" stated as fact. `pytest -q` runs the offline tests (fake decider, no
Bedrock).

## Run it yourself

```bash
pip install strands-decider
strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8099

pip install -r requirements.txt            # AWS credentials with Bedrock access
python -m hypecheck.agent --draft examples/referral_release.txt \
    --conclusion "Use of the urgent referral pathway could be efficacious."
uvicorn hypecheck.web:app --port 8080      # the demo UI
```

To deploy:
- `deploy/ec2-bootstrap.sh` builds the EC2 box. It uses the GPU if there is one, CPU otherwise.
- `deploy/agentcore_deploy.py` creates the AgentCore runtime.
- `deploy/update-ec2.sh` rolls out new code.

## Repository map

| Path | What |
|---|---|
| `decision_pattern/` | The reusable gate: questions, scoring, intervention, conformal calibration, client |
| `hypecheck/` | The agent (`agent.py`), web app (`web.py`, `static/`), AgentCore client |
| `agentcore_app.py` | AgentCore Runtime entrypoint |
| `research/` | Pre-registrations, evaluation scripts, per-item results |
| `deploy/` | EC2 bootstrap and update, AgentCore deploy |
| `AUDIT.md`, `DESIGN.md` | Self-audit against the rules; UI design principles |

## Licence

Apache-2.0. Benchmark data is not redistributed; each dataset keeps its own licence
(see `research/README.md`).
