"""The same gate on a different job: a patient-leaflet writer that cannot overstate a drug study.

Nothing in `decision_pattern` is specific to press releases. Point ClaimFidelityGate at the tool
that saves the leaflet and give it the study's conclusion as the source; the questions, the
scoring and the calibrated threshold are unchanged.

    strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8099
    python examples/leaflet_gate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strands import Agent, tool

from decision_pattern import ClaimFidelityGate, Decider, load_threshold

STUDY = ("In this observational cohort, statin use was associated with a lower incidence of "
         "dementia; residual confounding cannot be excluded.")

LEAFLET_REQUEST = ("Write a four-sentence patient leaflet paragraph about this study for people "
                   "over 65, then save it with save_leaflet.")


@tool
def save_leaflet(text: str) -> str:
    """Save the finished leaflet paragraph.

    Args:
        text: the paragraph to save.
    """
    Path("outbox").mkdir(exist_ok=True)
    Path("outbox/leaflet.txt").write_text(text, encoding="utf-8")
    return "saved"


def main() -> None:
    decider = Decider()
    gate = ClaimFidelityGate(decider, lambda: STUDY, tool_name="save_leaflet", text_arg="text",
                             threshold=load_threshold("research/results/calibration/summary.json", "0.1"),
                             on_verdict=lambda v, a: print(f"[gate] round {len(gate.history)}: {a}; "
                                                           f"max overclaim {max(s.p_overclaim for s in v.sentences):.2f}"))
    agent = Agent(model="us.anthropic.claude-sonnet-4-6", tools=[save_leaflet], interventions=[gate],
                  system_prompt="You write clear patient leaflets. If saving is blocked with feedback, "
                                "fix only the sentences named and save again.",
                  callback_handler=None)
    print(agent(f"STUDY CONCLUSION: {STUDY}\n\n{LEAFLET_REQUEST}"))
    print(f"[gate] {gate.rounds} round(s), {decider.calls} decisions, {decider.total_ms:.0f} ms in the decider")


if __name__ == "__main__":
    main()
