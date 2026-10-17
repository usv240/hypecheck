"""ClaimFidelityGate: a Strands intervention that stops text claiming more than its source.

Runs in `before_tool_call` on whichever tool publishes, sends or saves derived text. Strands
Decider scores every sentence against the source; plain Python turns the scores into a typed
action:

    any sentence over the calibrated threshold  -> Guide   (the model gets its turn back with the
                                                             offending sentences and rewrites)
    still over after `max_rounds` rewrites       -> Confirm (a person decides)
    otherwise                                    -> Proceed

The threshold comes from `decision_pattern.calibrate`, not from a hand-picked band, so it carries
a stated false-flag rate. The model classifies; the code decides; the LLM cannot negotiate with
a number.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from strands.interventions import Confirm, Guide, InterventionHandler, Proceed

from .decider import Decider
from .fidelity import STRENGTH, DocumentVerdict, check_document

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


class ClaimFidelityGate(InterventionHandler):
    """Gate a publishing tool on claim fidelity.

    Args:
        decider: client for a running strands-decider server.
        source: callable returning the source text (e.g. the paper's conclusion) for this run.
        tool_name: the tool to gate; other tools pass through.
        text_arg: the tool argument holding the derived text.
        threshold: overclaim probability above which a sentence is flagged.
        max_rounds: rewrites allowed before a person is asked.
        on_verdict: optional callback for UIs and logs.
    """

    name = "claim-fidelity-gate"

    def __init__(self, decider: Decider, source: Callable[[], str], *, tool_name: str = "publish_release",
                 text_arg: str = "text", threshold: float = 0.5, max_rounds: int = 3,
                 on_verdict: Callable[[DocumentVerdict, str], None] | None = None) -> None:
        self.decider = decider
        self.source = source
        self.tool_name = tool_name
        self.text_arg = text_arg
        self.threshold = threshold
        self.max_rounds = max_rounds
        self.on_verdict = on_verdict
        self.rounds = 0
        self.history: list[dict[str, Any]] = []

    def before_tool_call(self, event, **kwargs):
        if event.tool_use["name"] != self.tool_name:
            return Proceed()
        text = (event.tool_use.get("input") or {}).get(self.text_arg, "")
        verdict = check_document(self.decider, self.source(), text)
        flagged = [s for s in verdict.sentences if s.p_overclaim > self.threshold]
        advisories = [(s, k) for s in verdict.sentences for k, p in s.advisory.items() if p >= 0.5]
        self.rounds += 1
        self.history.append({"round": self.rounds, "flagged": len(flagged),
                             "sentences": len(verdict.sentences),
                             "max_p_overclaim": round(max((s.p_overclaim for s in verdict.sentences), default=0.0), 4)})

        if not flagged:
            action = "proceed"
            result = Proceed(reason=f"no sentence above {self.threshold:.2f}")
        elif self.rounds > self.max_rounds:
            action = "confirm"
            result = Confirm(prompt=f"{len(flagged)} sentence(s) still claim more than the paper after "
                                    f"{self.max_rounds} rewrites. Publish anyway? (y/n)")
        else:
            action = "guide"
            result = Guide(feedback=self._feedback(verdict, flagged, advisories))
        if self.on_verdict:
            self.on_verdict(verdict, action)
        return result

    def _feedback(self, verdict: DocumentVerdict, flagged, advisories) -> str:
        lines = [f"The paper's conclusion claims {READABLE[verdict.source_strength]}. "
                 "These sentences claim more than that:"]
        for s in flagged:
            lines.append(f'- "{s.sentence}" reads as {READABLE[s.strength]} '
                         f"(overclaim probability {s.p_overclaim:.2f}).")
        notes = {k for _, k in advisories}
        if "animal_to_human" in notes:
            lines.append("Also check: a sentence may present an animal or lab result as if it applied to people.")
        if "unsupported_advice" in notes:
            lines.append("Also check: a sentence may give readers advice the paper does not make.")
        lines.append("Rewrite only those sentences so they claim no more than the paper does (e.g. 'is "
                     "associated with' instead of 'causes'), keep everything else, then call the tool again.")
        return "\n".join(lines)


__all__ = ["ClaimFidelityGate", "load_threshold", "STRENGTH"]
