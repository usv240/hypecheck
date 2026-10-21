"""Are the headline differences bigger than chance? Paired bootstrap over the 563 W&A test pairs. Offline: no model calls.

    python research/significance.py
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

R = Path(__file__).resolve().parent / "results"
LABELS = ("same", "exaggerates", "downplays")
BLOCK = 0.5001  # conformal threshold, alpha = 0.10
PUBLISHED_BEST = 0.4735  # MT-PET, Wright & Augenstein 2021 (trained on the task)
B = 5000


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def macro_f1(gold: list[str], pred: list[str]) -> float:
    fs = []
    for c in LABELS:
        tp = sum(g == c and p == c for g, p in zip(gold, pred))
        fp = sum(g != c and p == c for g, p in zip(gold, pred))
        fn = sum(g == c and p != c for g, p in zip(gold, pred))
        fs.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return sum(fs) / len(fs)


def false_flag(gold: list[str], flag: list[bool]) -> float:
    xs = [f for g, f in zip(gold, flag) if g == "same"]
    return sum(xs) / len(xs) if xs else 0.0


def ci(xs: list[float]) -> list[float]:
    xs = sorted(xs)
    return [round(xs[int(0.025 * len(xs))], 4), round(xs[int(0.975 * len(xs)) - 1], 4)]


def main() -> None:
    dec = rows(R / "spike-v1" / "wa_items.csv")
    gold = [r["gold"] for r in dec]
    d_pred = [r["v2_pred"] for r in dec]
    d_flag = [float(r["v2_p_exag"]) > BLOCK for r in dec]
    n = len(dec)
    rng = random.Random(0)
    samples = [[rng.randrange(n) for _ in range(n)] for _ in range(B)]
    pick = lambda xs, ix: [xs[i] for i in ix]

    boot_f1 = [macro_f1(pick(gold, ix), pick(d_pred, ix)) for ix in samples]
    out = {
        "n": n, "bootstrap_samples": B, "seed": 0,
        "decider": {
            "macro_f1": round(macro_f1(gold, d_pred), 4), "macro_f1_95ci": ci(boot_f1),
            "share_of_resamples_above_published_best": round(sum(x > PUBLISHED_BEST for x in boot_f1) / B, 4),
            "false_flag_same": round(false_flag(gold, d_flag), 4),
            "false_flag_same_95ci": ci([false_flag(pick(gold, ix), pick(d_flag, ix)) for ix in samples]),
        },
        "published_best_macro_f1": PUBLISHED_BEST,
        "vs_claude": {},
    }
    for name in ("haiku45", "sonnet-4-6", "opus-4-6"):
        llm = rows(R / f"baseline-{name}" / "items.csv")
        assert [r["gold"] for r in llm] == gold, name
        l_pred = [r["pred"] for r in llm]
        l_flag = [p == "exaggerates" for p in l_pred]
        f1_diff = [macro_f1(pick(gold, ix), pick(d_pred, ix)) - macro_f1(pick(gold, ix), pick(l_pred, ix))
                   for ix in samples]
        ff_diff = [false_flag(pick(gold, ix), pick(l_flag, ix)) - false_flag(pick(gold, ix), pick(d_flag, ix))
                   for ix in samples]
        out["vs_claude"][name] = {
            "macro_f1": round(macro_f1(gold, l_pred), 4),
            "macro_f1_gain_for_decider": round(macro_f1(gold, d_pred) - macro_f1(gold, l_pred), 4),
            "macro_f1_gain_95ci": ci(f1_diff),
            "false_flag_same": round(false_flag(gold, l_flag), 4),
            "false_flags_avoided_by_decider": round(false_flag(gold, l_flag) - false_flag(gold, d_flag), 4),
            "false_flags_avoided_95ci": ci(ff_diff),
        }
    (R / "significance").mkdir(exist_ok=True)
    (R / "significance" / "summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
