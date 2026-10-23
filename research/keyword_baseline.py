"""The no-model baseline: the site's cue-word lists used as a classifier. See
PREREGISTRATION-keyword-baseline.md. Offline; needs the public W&A test pairs for the text.

    python research/keyword_baseline.py --wa-dir data
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from spike import auroc  # noqa: E402

R = HERE / "results"
BLOCK = 0.5001  # Decider's conformal threshold at alpha 0.10

# The same lists as CUES in hypecheck/static/index.html, unchanged.
CUES = [
    (3, re.compile(r"\b(saves? lives|saving lives|causes?|caused|causing|prevents?|prevented|preventing|reduces?|reduced|"
                   r"reducing|increases?|increased|boosts?|boosted|cuts?|improves?|improved|leads? to|led to|protects? against|"
                   r"stops?|cures?|eliminates?|triggers?|reverses?|reversed|will (?:lower|reduce|raise|increase|improve|prevent|"
                   r"cause|grow|double|cut))\b", re.I)),
    (2, re.compile(r"\b(may|might|could|can|suggests?|suggesting|potential(?:ly)?|appears? to|likely|possible|possibly|promising)\b", re.I)),
    (1, re.compile(r"\b(associated with|association|linked (?:to|with)|link between|correlat\w*|related to|more likely|"
                   r"less likely|tends? to|higher rates?|lower rates?)\b", re.I)),
]


def level(text: str) -> int:
    return max((lvl for lvl, rx in CUES if rx.search(text)), default=0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wa-dir", type=Path, required=True)
    a = ap.parse_args()
    test = [json.loads(x) for x in (a.wa_dir / "test.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    dec = list(csv.DictReader((R / "spike-v1" / "wa_items.csv").open(encoding="utf-8")))
    assert [r["id"] for r in dec] == [t["original_file_id"] for t in test]
    gold = [r["gold"] for r in dec]
    y = [int(g == "exaggerates") for g in gold]
    kw = [level(t["press_release_conclusion"]) - level(t["abstract_conclusion"]) for t in test]
    kw_flag = [s > 0 for s in kw]
    d = [float(r["v2_p_exag"]) for r in dec]
    d_flag = [x > BLOCK for x in d]

    def rate(flags, lab):
        xs = [f for f, g in zip(flags, gold) if g == lab]
        return round(sum(xs) / len(xs), 4)

    rng, n = random.Random(0), len(y)
    gaps = []
    for _ in range(5000):
        ix = [rng.randrange(n) for _ in range(n)]
        yy = [y[i] for i in ix]
        gaps.append(auroc(yy, [d[i] for i in ix]) - auroc(yy, [kw[i] for i in ix]))
    gaps.sort()
    out = {
        "n": n,
        "keyword_rule": {"auroc": round(auroc(y, kw), 4), "recall_exaggerates": rate(kw_flag, "exaggerates"),
                         "false_flag_same": rate(kw_flag, "same"),
                         "level_counts_release": {k: sum(level(t["press_release_conclusion"]) == k for t in test) for k in range(4)}},
        "decider": {"auroc": round(auroc(y, d), 4), "recall_exaggerates": rate(d_flag, "exaggerates"),
                    "false_flag_same": rate(d_flag, "same")},
        "auroc_gap_decider_minus_rule": round(auroc(y, d) - auroc(y, kw), 4),
        "auroc_gap_95ci": [round(gaps[125], 4), round(gaps[4874], 4)],
    }
    (R / "keyword-baseline").mkdir(exist_ok=True)
    (R / "keyword-baseline" / "summary.json").write_text(json.dumps(out, indent=1))
    with (R / "keyword-baseline" / "items.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "gold", "level_abstract", "level_release", "kw_score", "kw_flag"])
        for t, r, s, fl in zip(test, dec, kw, kw_flag):
            w.writerow([r["id"], r["gold"], level(t["abstract_conclusion"]), level(t["press_release_conclusion"]), s, int(fl)])
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
