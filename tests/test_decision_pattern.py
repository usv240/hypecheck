"""Offline tests for the reusable pattern: no decider server, no Bedrock.

    pip install pytest && pytest -q
"""

from __future__ import annotations

import math

import pytest

from decision_pattern.calibrate import conformal_threshold
from decision_pattern.fidelity import STRENGTH, check_document, overclaim_probability, split_sentences
from decision_pattern.gate import ClaimFidelityGate


class FakeDecider:
    """Answers the strength question from a lookup of phrases, everything else neutral."""

    def __init__(self, table: dict[str, int]) -> None:
        self.table = table
        self.calls = 0
        self.total_ms = 0.0

    def ask(self, state, questions):
        self.calls += 1
        out = {}
        for name, q in questions.items():
            if q["type"] == "noul":
                out[name] = {"type": "noul", "noul": 0.1}
                continue
            keys = list(q["criteria"])
            level = next((lvl for phrase, lvl in self.table.items() if phrase in state), 0)
            probs = {k: 0.02 for k in keys}
            probs[keys[min(level, len(keys) - 1)]] = 1 - 0.02 * (len(keys) - 1)
            out[name] = {"type": "choice", "choice": keys[min(level, len(keys) - 1)], "probabilities": probs, "confidence": 0.9}
        return out


def test_overclaim_probability_orders_levels():
    assert overclaim_probability([0, 0, 0, 1], [0, 1, 0, 0]) == pytest.approx(1.0)   # direct > correlational
    assert overclaim_probability([0, 1, 0, 0], [0, 0, 0, 1]) == pytest.approx(0.0)   # correlational < direct
    assert overclaim_probability([0, 1, 0, 0], [0, 1, 0, 0]) == pytest.approx(0.0)   # same level
    assert overclaim_probability([0.5, 0, 0, 0.5], [0, 1, 0, 0]) == pytest.approx(0.5)


def test_conformal_threshold_matches_quantile_formula():
    scores = [i / 100 for i in range(100)]            # 0.00 .. 0.99, n = 100
    k = math.ceil(101 * 0.9)                           # 91st smallest for alpha = 0.10
    assert conformal_threshold(scores, 0.10) == pytest.approx(sorted(scores)[k - 1])
    with pytest.raises(ValueError):
        conformal_threshold([0.1, 0.2], 0.10)          # too few faithful pairs for the alpha


def test_split_sentences_keeps_abbreviations_simple():
    text = "Coffee was linked to lower risk. The study had 8,000 people! Was it causal? No. Not shown."
    # fragments of three characters or fewer ("No.") are dropped on purpose
    assert split_sentences(text) == ["Coffee was linked to lower risk.", "The study had 8,000 people!", "Was it causal?", "Not shown."]


def test_check_document_flags_only_the_overclaim():
    decider = FakeDecider({"saves lives": 3, "could be": 2, "linked": 1})
    verdict = check_document(decider, "Use of the pathway could be efficacious.",
                             "The pathway saves lives. Practices were linked to lower mortality.", advisory=False)
    assert verdict.source_strength == "conditional_causal"
    assert [s.strength for s in verdict.sentences] == ["direct_causal", "correlational"]
    assert verdict.sentences[0].p_overclaim > 0.9
    assert verdict.sentences[1].p_overclaim < 0.1


class _Event:
    def __init__(self, name, text):
        self.tool_use = {"name": name, "input": {"text": text}}


def test_gate_guides_then_proceeds_then_confirms():
    from strands.interventions import Confirm, Guide, Proceed

    decider = FakeDecider({"saves lives": 3, "could be": 2})
    gate = ClaimFidelityGate(decider, lambda: "The pathway could be efficacious.", threshold=0.5, max_rounds=2)
    assert isinstance(gate.before_tool_call(_Event("other_tool", "The pathway saves lives.")), Proceed)
    assert isinstance(gate.before_tool_call(_Event("publish_release", "The pathway saves lives.")), Guide)
    assert isinstance(gate.before_tool_call(_Event("publish_release", "The pathway could be efficacious.")), Proceed)
    gate.rounds = 2
    assert isinstance(gate.before_tool_call(_Event("publish_release", "The pathway saves lives.")), Confirm)
    assert STRENGTH[-1] == "direct_causal"


def test_review_zone_does_not_block():
    from strands.interventions import Proceed

    from decision_pattern.gate import zone

    assert zone(0.8, 0.5, 0.4) == "block" and zone(0.45, 0.5, 0.4) == "review" and zone(0.2, 0.5, 0.4) == "ok"
    decider = FakeDecider({"may": 2, "could be": 2})
    gate = ClaimFidelityGate(decider, lambda: "The pathway could be efficacious.", threshold=0.99, review_threshold=0.0)
    # same level as the source: overclaim ~0, so it is OK; nothing blocks, review list is empty
    assert isinstance(gate.before_tool_call(_Event("publish_release", "The pathway may help.")), Proceed)
    assert gate.history[-1]["flagged"] == 0
