"""Fit the gate's threshold from labelled pairs, with a stated false-flag guarantee.

The Decider docs say the 0.9 / 0.5 bands are illustrative and should be measured on your own
traffic. This does that with split conformal prediction on the *faithful* pairs only:

    tau = the ceil((n + 1) * (1 - alpha))-th smallest overclaim score among n faithful pairs

Flag a new pair when its score exceeds tau. If new faithful pairs are exchangeable with the
calibration ones, the chance a faithful pair is flagged is at most alpha (Vovk et al. 2005;
Angelopoulos & Bates 2021, arXiv:2107.07511). It promises nothing about recall, which is
measured separately and reported next to it.

    python -m decision_pattern.calibrate --pairs pairs.jsonl --alpha 0.10 --out threshold.json

`pairs.jsonl` rows: {"source": ..., "derived": ..., "label": "faithful" | "overclaim" | ...}.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .decider import Decider
from .fidelity import overclaim_probability, strength


def conformal_threshold(faithful_scores: list[float], alpha: float) -> float:
    n = len(faithful_scores)
    k = math.ceil((n + 1) * (1 - alpha))
    if k > n:
        raise ValueError(f"{n} faithful pairs cannot support alpha={alpha}; need n >= {math.ceil(1 / alpha) - 1}")
    return sorted(faithful_scores)[k - 1]


def score_pairs(decider: Decider, rows: list[dict]) -> list[float]:
    return [overclaim_probability(strength(decider, r["derived"]), strength(decider, r["source"])) for r in rows]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=Path, required=True)
    ap.add_argument("--alpha", type=float, default=0.10)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    rows = [json.loads(line) for line in args.pairs.read_text(encoding="utf-8").splitlines() if line.strip()]
    scores = score_pairs(Decider(), rows)
    faithful = [s for s, r in zip(scores, rows) if r["label"] == "faithful"]
    tau = conformal_threshold(faithful, args.alpha)
    over = [s for s, r in zip(scores, rows) if r["label"] == "overclaim"]
    out = {
        "alpha": args.alpha, "threshold": round(tau, 6), "n_faithful": len(faithful),
        "calibration_recall": round(sum(s > tau for s in over) / len(over), 4) if over else None,
        "guarantee": f"P(flag | faithful) <= {args.alpha} for pairs exchangeable with the calibration set",
    }
    args.out.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
