"""ClaimFidelityGate: a Strands intervention that stops text claiming more than its source.

Runs in `before_tool_call` on whichever tool publishes, sends or saves derived text. Strands
Decider scores every sentence against the source; plain Python turns the scores into a typed
action, with three zones for each sentence:

    p_overclaim > threshold                  BLOCK   -> the call returns Guide: the model gets its turn
                                                        back with the offending sentences and rewrites
    review_threshold < p <= threshold        REVIEW  -> low confidence: never blocks, but listed for a
                                                        human glance in the publish record
    p <= review_threshold                    OK

    still blocking after `max_rounds` rewrites -> Confirm (a person decides)
    nothing blocking                           -> Proceed

Both thresholds come from `decision_pattern.calibrate` (conformal, alpha = 0.10 and 0.20), not
from a hand-picked band, so each carries a stated false-flag rate. The model classifies; the code
decides; the LLM cannot negotiate with a number.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from strands.interventions import Confirm, Guide, InterventionHandler, Proceed

from .decider import Decider
from .fidelity import STRENGTH, DocumentVerdict, SentenceVerdict, check_document

READABLE = {
    "no_relationship": "no relationship",
    "correlational": "an association (correlation)",
    "conditional_causal": "a possible, hedged cause",
    "direct_causal": "a definite cause",
}


def load_threshold(path: str | Path, alpha: str = "0.1") -> float:
    """Read a threshold written by calibrate.py or research/calibration_eval.py."""
    data = json.loads(Path(path).read_text())
    return data["threshold"] if "threshold" in data else data["by_alpha"][alpha]["threshold"]


def zone(p_overclaim: float, threshold: float, review_threshold: float | None) -> str:
    if p_overclaim > threshold:
        return "block"
    if review_threshold is not None and p_overclaim > review_threshold:
        return "review"
    return "ok"


class ClaimFidelityGate(InterventionHandler):
    """Gate a publishing tool on claim fidelity.

    Args:
        decider: client for a running strands-decider server.
        source: callable returning the source text (e.g. the paper's conclusion) for this run.
        tool_name: the tool to gate; other tools pass through.
        text_arg: the tool argument holding the derived text.
        threshold: overclaim probability above which a sentence blocks the call.
        review_threshold: optional lower threshold; sentences between the two are surfaced for
            review but do not block (low-confidence zone).
        max_rounds: rewrites allowed before a person is asked.
        on_verdict: optional callback (verdict, action) for UIs and logs.
        on_sentence: optional callback (index, total, sentence_verdict) as each sentence is scored.
    """

    name = "claim-fidelity-gate"

    def __init__(self, decider: Decider, source: Callable[[], str], *, tool_name: str = "publish_release",
                 text_arg: str = "text", threshold: float = 0.5, review_threshold: float | None = None,
                 max_rounds: int = 3,
                 on_verdict: Callable[[DocumentVerdict, str], None] | None = None,
                 on_sentence: Callable[[int, int, SentenceVerdict], None] | None = None) -> None:
        self.decider = decider
        self.source = source
        self.tool_name = tool_name
        self.text_arg = text_arg
        self.threshold = threshold
        self.review_threshold = review_threshold
        self.max_rounds = max_rounds
        self.on_verdict = on_verdict
        self.on_sentence = on_sentence
        self.rounds = 0
        self.history: list[dict[str, Any]] = []
        self.review: list[str] = []

    def before_tool_call(self, event, **kwargs):
        if event.tool_use["name"] != self.tool_name:
            return Proceed()
        text = (event.tool_use.get("input") or {}).get(self.text_arg, "")
        self.rounds += 1
        verdict = check_document(self.decider, self.source(), text, on_sentence=self.on_sentence)
        zones = [zone(s.p_overclaim, self.threshold, self.review_threshold) for s in verdict.sentences]
        flagged = [s for s, z in zip(verdict.sentences, zones) if z == "block"]
        self.review = [s.sentence for s, z in zip(verdict.sentences, zones) if z == "review"]
        self.history.append({"round": self.rounds, "flagged": len(flagged), "review": len(self.review),
                             "sentences": len(verdict.sentences),
                             "max_p_overclaim": round(max((s.p_overclaim for s in verdict.sentences), default=0.0), 4)})

        if not flagged:
            action = "proceed"
            result = Proceed(reason=f"no sentence above {self.threshold:.2f}; {len(self.review)} for review")
        elif self.rounds > self.max_rounds:
            action = "confirm"
            result = Confirm(prompt=f"{len(flagged)} sentence(s) still claim more than the paper after "
                                    f"{self.max_rounds} rewrites. Publish anyway? (y/n)")
        else:
            action = "guide"
            result = Guide(feedback=self._feedback(verdict, flagged))
        if self.on_verdict:
            self.on_verdict(verdict, action)
        return result

    def _feedback(self, verdict: DocumentVerdict, flagged) -> str:
        lines = [f"The paper's conclusion claims {READABLE[verdict.source_strength]}. "
                 "These sentences claim more than that:"]
        for s in flagged:
            lines.append(f'- "{s.sentence}" reads as {READABLE[s.strength]} '
                         f"(overclaim probability {s.p_overclaim:.2f}).")
        # Document-level advisories: measured weaker than the sentence gate, so they inform the
        # rewrite but never block on their own.
        if verdict.advisory.get("advice_inflated", 0) >= 0.5:
            lines.append("Also check: the release gives readers stronger advice than the paper does.")
        if verdict.advisory.get("animal_to_human", 0) >= 0.5:
            lines.append("Also check: the release may present an animal or lab result as if it applied to people.")
        lines.append("Rewrite only those sentences so they claim no more than the paper does (e.g. 'is "
                     "associated with' instead of 'causes'), keep everything else, then call the tool again.")
        return "\n".join(lines)


__all__ = ["ClaimFidelityGate", "load_threshold", "zone", "STRENGTH"]
