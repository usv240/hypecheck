# Decision pattern: claim-fidelity gate (`#guardrails`)

**Problem it solves:** an agent is about to publish, send or save text derived from a source. The
gate stops any sentence that claims a stronger relationship than the source supports, then has the
model rewrite just those sentences.

**Where it sits:** `InterventionHandler.before_tool_call` on the tool that publishes. Strands runs
it before the tool executes.

**What Decider decides:** one typed `choice` question, asked once of the source and once of every
sentence of the derived text.

## 1. The typed question and option set

```python
STRENGTH_Q = {
    "type": "choice",
    "instructions": "How strong is the relationship this scientific statement claims?",
    "criteria": {
        "no_relationship":    "no correlational or causal relationship is stated; it reports a description, "
                              "a method, a null result or a single finding",
        "correlational":      "states an association between variables without claiming one causes the other, "
                              "e.g. 'associated with', 'linked to', 'more likely to have'",
        "conditional_causal": "states a causal relationship with hedging, e.g. 'may reduce', 'might cause', "
                              "'could improve'",
        "direct_causal":      "states outright that one thing causes, prevents, reduces, improves or increases "
                              "another, e.g. 'reduces', 'leads to', 'saves lives'",
    },
}
```

The options are ordered. The overclaim score of a sentence is the probability that it sits on a
higher level than the source:

```
P(overclaim) = Σ_{i > j} P(sentence = i) · P(source = j)
```

Two document-level questions ride along in the same pass. Both are advisory: they are passed to
the model but never block on their own.

| Question | Type | Measured | Used for |
|---|---|---|---|
| `ADVICE_Q`: strongest advice given (none / implicit / explicit-indirect / explicit-direct) | `choice` | AUROC 0.84 for "release advises more strongly than the paper", 116 real releases | hint in the Guide feedback |
| `ANIMAL_Q`: does the text present the finding as applying to people? | `noul` | AUROC 0.61, 45 releases (weak) | hint only |

## 2. The wiring

```python
from strands import Agent
from decision_pattern import Decider, ClaimFidelityGate, load_threshold

gate = ClaimFidelityGate(
    Decider(),                                   # STRANDS_DECIDER_URL, default http://127.0.0.1:8099
    source=lambda: paper_conclusion,             # what the text must not exceed
    tool_name="publish_release",                 # the tool to gate (others pass through)
    text_arg="text",                             # the tool argument holding the text
    threshold=load_threshold("calibration.json", "0.1"),          # BLOCK above this
    review_threshold=load_threshold("calibration.json", "0.2"),   # REVIEW between the two
    max_rounds=3,                                # then ask a person
)
agent = Agent(model="us.anthropic.claude-sonnet-4-6", tools=[publish_release], interventions=[gate])
```

## 3. What the gate returns

| Situation | Typed action | Effect |
|---|---|---|
| A sentence scores above `threshold` | `Guide(feedback=…)` | The model gets its turn back with each blocked sentence, its strength, and the paper's strength, and rewrites only those |
| A sentence scores between `review_threshold` and `threshold` | (counted, not blocking) | Low-confidence zone. Listed in `gate.review` so the publish record can carry it for an editor |
| Still blocked after `max_rounds` rewrites | `Confirm(prompt=…)` | A person decides (Strands interrupt) |
| Nothing above `threshold` | `Proceed()` | The tool runs |
| No source text, or Decider unreachable | `Deny(reason=…)` | Fails closed: nothing is published unchecked. `on_deny` reports why |

## 4. Calibrate the thresholds on your own data

The Decider docs call the 0.9 / 0.5 bands illustrative and say to measure on your own traffic.
`calibrate.py` does this with split conformal prediction over your *faithful* examples.

```bash
# pairs.jsonl: {"source": "...", "derived": "...", "label": "faithful" | "overclaim"}
python -m decision_pattern.calibrate --pairs pairs.jsonl --alpha 0.10 --out calibration.json
```

The threshold is the ⌈(n+1)(1−α)⌉-th smallest score among n faithful pairs. If new text resembles
the calibration set, at most α of faithful sentences are flagged. On the press-release benchmark,
α = 0.10 fitted on 78 pairs gave 7.7% on 441 unseen pairs. That α only works with
n ≥ 1/α − 1 faithful pairs.

## 5. Without writing code

The same gate is a hosted API and an MCP tool, and you can calibrate it on your own pairs. Instructions and a free key are at https://d174bz5yly61n4.cloudfront.net/developers.

## 6. Decision receipts

Every verdict carries a receipt: canonical JSON with the checkpoint, the rung probabilities for the
source and each sentence, the overclaim scores, the thresholds and their basis, the zones, the
policy text, and a SHA-256 over all of it. The facts are written by code, never by a model.

```python
from decision_pattern import build_receipt, verify_receipt
receipt = build_receipt(verdict, source=paper, derived=draft, threshold=0.5001, review_threshold=0.3986,
                        zones=zones, action="guide", model="strands-decider-2B-qwen3.5-v1-2610")
verify_receipt(receipt)   # recomputes scores, zones and the hash with no model; names any sentence that disagrees
```

In HypeCheck the receipt is attached to each agent round, to the published release in the outbox, and
to every `/v1/check` and `/v1/rewrite` response. `POST /v1/verify` (no key) and the MCP tool
`verify_decision_receipt` check one. Credit for the device: Changeset Second Opinion and Heal or Halt
in the same hackathon.

## 7. Install

```bash
pip install "git+https://github.com/usv240/hypecheck"   # installs decision_pattern only
```

## 8. Notes for reuse

- It works for any "derived text must not exceed its source" job: summaries, RAG answers,
  patient leaflets, changelogs. `examples/leaflet_gate.py` runs it unchanged on a leaflet writer.
- Cost:
  - Each sentence costs one Decider call; the source costs one more.
  - The two advisories add three calls per document.
  - No LLM tokens are spent on judging.
- The client is standard library only (`decider.py`). Set `STRANDS_DECIDER_KEY` to send an
  `x-hypecheck-key` header when Decider sits behind a guarded proxy.
- Backups: give `STRANDS_DECIDER_URL` several servers, comma-separated, and the client fails
  over to the next one. If none answers, the gate returns `Deny`. In HypeCheck's own agent, a
  throttled or unavailable Claude Sonnet 4.6 falls back to Claude Haiku 4.5
  (`HYPECHECK_FALLBACK_MODEL`). Both models are cross-region inference profiles.
- Offline tests: `pytest -q tests` (uses a fake decider; no server or Bedrock needed).

## 9. What this uses from Strands Decider and the hackathon brief

| Capability | How it is used here |
|---|---|
| `choice` questions | Claim strength (4 options) and advice level (4 options), asked of the source and of each sentence |
| `noul` (yes/no) | The animal-to-human hint. It is weak (AUROC 0.61), so it informs the rewrite but never blocks |
| `score` questions | Not used. The Decider repo reports that `score` does not hold up on unseen tasks behind a confidence gate. An ordered `choice` plus probabilities gives the same ladder with calibrated probabilities |
| Calibrated probabilities | Overclaim probability = Σ P(sentence level i)·P(source level j) for i > j. Thresholds come from conformal calibration, not the illustrative 0.9/0.5 bands |
| Low-confidence handling | A REVIEW zone between the two calibrated thresholds: never blocks, always surfaced to an editor |
| All four intervention actions | `Proceed`, `Guide`, `Confirm` and `Deny` (see section 3) |
| Amazon Bedrock | Claude Sonnet 4.6 writes and rewrites, with Haiku 4.5 as its backup. Haiku, Sonnet and Opus were also measured as judges for comparison |
| Measured latency and cost | 160 ms per decision on a laptop GPU, about 0.9 s on the CPU demo server, $0 in LLM tokens, against Claude as the judge (README) |
| Decision patterns | **Guardrails** is the declared pattern. **Context scoring**: HypeWatch asks Decider for the strength of each abstract sentence and compares against the strongest one. **Model routing**: we measured a Bylaw-style cascade (Claude only on REVIEW) and did not adopt it (`research/PREREGISTRATION-cascade.md`) |
| Vision (`--vision`) | Not used. The text claims are the thing being checked, and the Decider docs report that its confidence doesn't drop when an image is missing |
