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

## 5. Notes for reuse

- It works for any "derived text must not exceed its source" job: summaries, RAG answers,
  patient leaflets, changelogs. `examples/leaflet_gate.py` runs it unchanged on a leaflet writer.
- Cost:
  - Each sentence costs one Decider call; the source costs one more.
  - The two advisories add three calls per document.
  - No LLM tokens are spent on judging.
- The client is standard library only (`decider.py`). Set `STRANDS_DECIDER_KEY` to send an
  `x-hypecheck-key` header when Decider sits behind a guarded proxy.
- Offline tests: `pytest -q tests` (uses a fake decider; no server or Bedrock needed).
