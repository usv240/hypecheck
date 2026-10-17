"""Does the conformal threshold keep its false-flag promise on unseen pairs?

Fit on the W&A *train* split (100 pairs, never used for any other choice), then apply to the
*test* split. Test scores come from results/spike-v1/wa_items.csv (`v2_p_exag`), which uses the
exact scoring in decision_pattern.fidelity, so the test set is not re-queried.

"Not overclaim" = `same` + `downplays`, the population the guarantee is stated over.

    python research/calibration_eval.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from decision_pattern.calibrate import conformal_threshold, score_pairs  # noqa: E402
from decision_pattern.decider import Decider  # noqa: E402

ALPHAS = [0.05, 0.10, 0.20]
OUT = ROOT / "research" / "results" / "calibration"


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if n == 0:
        return [float("nan")] * 2
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [round(c - h, 4), round(c + h, 4)]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    train = [json.loads(x) for x in (ROOT / "data" / "train.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    pairs = [{"source": r["abstract_conclusion"], "derived": r["press_release_conclusion"], "label": r["exaggeration_label"]} for r in train]
    cache = OUT / "train_scores.json"
    if cache.exists():
        scores = json.loads(cache.read_text())
    else:
        scores = score_pairs(Decider(), pairs)
        cache.write_text(json.dumps(scores))

    test = list(csv.DictReader((ROOT / "research" / "results" / "spike-v1" / "wa_items.csv").open(encoding="utf-8")))
    neg_train = [s for s, p in zip(scores, pairs) if p["label"] != "exaggerates"]
    report = {"n_train": len(pairs), "n_train_not_overclaim": len(neg_train),
              "train_label_counts": {k: sum(p["label"] == k for p in pairs) for k in ("same", "exaggerates", "downplays")},
              "n_test": len(test), "by_alpha": {}}
    for a in ALPHAS:
        tau = conformal_threshold(neg_train, a)
        flag = lambda r: float(r["v2_p_exag"]) > tau  # noqa: E731
        groups = {g: [r for r in test if r["gold"] == g] for g in ("same", "downplays", "exaggerates")}
        not_over = groups["same"] + groups["downplays"]
        k_ff, k_same, k_rec = sum(map(flag, not_over)), sum(map(flag, groups["same"])), sum(map(flag, groups["exaggerates"]))
        report["by_alpha"][str(a)] = {
            "threshold": round(tau, 4),
            "promised_max_false_flag": a,
            "test_false_flag_not_overclaim": round(k_ff / len(not_over), 4),
            "test_false_flag_not_overclaim_95ci": wilson(k_ff, len(not_over)),
            "test_false_flag_same_only": round(k_same / len(groups["same"]), 4),
            "test_recall_exaggerates": round(k_rec / len(groups["exaggerates"]), 4),
            "test_recall_95ci": wilson(k_rec, len(groups["exaggerates"])),
            "test_precision": round(k_rec / max(1, k_rec + k_ff), 4),
        }
    (OUT / "summary.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
