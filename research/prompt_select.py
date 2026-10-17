"""Compare wordings of the strength question on the W&A train split only. See PREREGISTRATION-prompts.md.

    python research/prompt_select.py
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from decision_pattern.decider import Decider  # noqa: E402
from decision_pattern.fidelity import STRENGTH, STRENGTH_Q, overclaim_probability  # noqa: E402
from research.spike import auroc, macro_f1  # noqa: E402

V1 = copy.deepcopy(STRENGTH_Q)
V1["criteria"] = {
    "no_relationship": "no correlational or causal relationship between two things is stated: a "
    "description, a method, a count, a null result, or a single finding about one thing",
    "correlational": "an association only; cue words: 'associated with', 'linked to', 'related to', "
    "'correlated with', 'more likely', 'less likely', 'higher rates among', 'tend to'",
    "conditional_causal": "a causal effect with hedging; cue words: 'may', 'might', 'could', 'can', "
    "'suggests that', 'appears to', 'is thought to', 'potentially'",
    "direct_causal": "an unhedged causal effect; cue words in the present tense: 'causes', 'reduces', "
    "'increases', 'prevents', 'improves', 'leads to', 'protects against', 'saves lives', 'boosts', 'cuts'",
}

V2 = {
    "type": "choice",
    "instructions": "Classify the main claim of this statement as a science-communication coder would, "
    "by the strongest relationship it states between an exposure or intervention and an outcome.",
    "criteria": {
        "no_relationship": "no relationship between an exposure and an outcome is claimed",
        "correlational": "a correlational claim: the two go together, with no claim that one causes the other",
        "conditional_causal": "a causal claim that is conditional or hedged: the exposure may, might or "
        "could cause the outcome",
        "direct_causal": "a direct causal claim: the exposure causes, prevents, reduces or increases the outcome",
    },
}

V3 = copy.deepcopy(V1)
PREFIX3 = "A sentence from a health press release or paper:\n"

VARIANTS = {"V0": (STRENGTH_Q, ""), "V1": (V1, ""), "V2": (V2, ""), "V3": (V3, PREFIX3)}


def strengths(decider: Decider, text: str, q: dict, prefix: str) -> list[float]:
    ans = decider.ask(prefix + text, {"strength": q})["strength"]
    return [ans["probabilities"][k] for k in STRENGTH]


def main() -> None:
    out = ROOT / "research" / "results" / "prompt-select"
    out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(x) for x in (ROOT / "data" / "train.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    gold = [r["exaggeration_label"] for r in rows]
    y = [int(g == "exaggerates") for g in gold]
    decider = Decider()
    report = {}
    for name, (q, prefix) in VARIANTS.items():
        preds, scores = [], []
        for r in rows:
            pa = strengths(decider, r["abstract_conclusion"], q, prefix)
            pp = strengths(decider, r["press_release_conclusion"], q, prefix)
            sa, sp = pa.index(max(pa)), pp.index(max(pp))
            preds.append("exaggerates" if sp > sa else "downplays" if sp < sa else "same")
            scores.append(overclaim_probability(pp, pa))
        report[name] = {"auroc_exag": round(auroc(y, scores), 4),
                        "macro_f1": round(macro_f1(gold, preds, ["same", "exaggerates", "downplays"]), 4)}
        print(name, report[name], flush=True)
    best = max((n for n in report if n != "V0"), key=lambda n: report[n]["auroc_exag"])
    report["decision"] = {"best": best, "gain_over_V0": round(report[best]["auroc_exag"] - report["V0"]["auroc_exag"], 4),
                          "adopt": report[best]["auroc_exag"] - report["V0"]["auroc_exag"] >= 0.03}
    (out / "summary.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report["decision"]))


if __name__ == "__main__":
    main()
