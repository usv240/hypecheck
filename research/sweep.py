"""Threshold sweep from the saved Decider scores: what every cut-off would have done. Offline, $0.

    python research/sweep.py            # writes results/sweep/{sweep.csv,summary.json} and docs/sweep.svg

The conformal threshold (alpha 0.10) is one point on this curve. The sweep shows whether it sits on
a plateau or a knife edge, and what each alternative buys. Credit for the device: evidence-first,
Escalator and Doorman in the same hackathon ship a sweep over cached scores.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE / "results"
OUT = R / "sweep"
CAL = json.loads((R / "calibration" / "summary.json").read_text())["by_alpha"]
TAUS = {a: CAL[a]["threshold"] for a in ("0.05", "0.1", "0.2")}


def main() -> int:
    rows = list(csv.DictReader((R / "spike-v1" / "wa_items.csv").open(encoding="utf-8")))
    p = [float(r["v2_p_exag"]) for r in rows]
    gold = [r["gold"] for r in rows]
    pos = [x for x, g in zip(p, gold) if g == "exaggerates"]
    neg_same = [x for x, g in zip(p, gold) if g == "same"]
    neg_all = [x for x, g in zip(p, gold) if g != "exaggerates"]
    grid = [i / 100 for i in range(0, 101)]
    table = []
    for t in grid:
        rec = sum(x > t for x in pos) / len(pos)
        ff_same = sum(x > t for x in neg_same) / len(neg_same)
        ff_all = sum(x > t for x in neg_all) / len(neg_all)
        tp, fp = sum(x > t for x in pos), sum(x > t for x in neg_all)
        table.append({"threshold": t, "recall": round(rec, 4), "false_flag_same": round(ff_same, 4),
                      "false_flag_not_overclaim": round(ff_all, 4),
                      "precision": round(tp / (tp + fp), 4) if tp + fp else None,
                      "flag_rate": round(sum(x > t for x in p) / len(p), 4)})
    OUT.mkdir(exist_ok=True)
    with (OUT / "sweep.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]))
        w.writeheader(); w.writerows(table)

    # the band of thresholds that keep the alpha-0.10 promise on test (false flags on non-overclaim <= 10%)
    keep = [x["threshold"] for x in table if x["false_flag_not_overclaim"] <= 0.10]
    at = lambda t: next(x for x in table if abs(x["threshold"] - round(t, 2)) < 1e-9)  # noqa: E731
    summary = {
        "n": len(rows), "grid": "0.00 to 1.00 in steps of 0.01",
        "conformal_thresholds": TAUS,
        "at_conformal": {a: at(t) for a, t in TAUS.items()},
        "thresholds_keeping_false_flags_le_10pct": {"min": min(keep), "max": max(keep), "count": len(keep)},
        "recall_range_within_that_band": [min(at(t)["recall"] for t in keep), max(at(t)["recall"] for t in keep)],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))

    # SVG: recall and false flags vs threshold, with the conformal points marked
    W, H, L, B, T = 760, 360, 60, 40, 20
    px = lambda t: L + t * (W - L - 20)  # noqa: E731
    py = lambda v: H - B - v * (H - B - T)  # noqa: E731
    def path(key):
        return " ".join(f"{'M' if i == 0 else 'L'}{px(x['threshold']):.1f},{py(x[key]):.1f}" for i, x in enumerate(table))
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="12">',
           f'<rect x="{px(min(keep)):.1f}" y="{T}" width="{px(max(keep)) - px(min(keep)):.1f}" height="{H - B - T}" fill="#2a78d6" opacity=".08"/>']
    for v in (0, .2, .4, .6, .8, 1):
        svg.append(f'<line x1="{L}" x2="{W - 20}" y1="{py(v):.1f}" y2="{py(v):.1f}" stroke="#e1e5ea"/><text x="{L - 8}" y="{py(v) + 4:.1f}" text-anchor="end" fill="#56606c">{int(v * 100)}%</text>')
    for t in (0, .2, .4, .6, .8, 1):
        svg.append(f'<text x="{px(t):.1f}" y="{H - B + 16}" text-anchor="middle" fill="#56606c">{t:.1f}</text>')
    svg.append(f'<path d="{path("recall")}" fill="none" stroke="#2a78d6" stroke-width="2.5"/>')
    svg.append(f'<path d="{path("false_flag_same")}" fill="none" stroke="#a3221a" stroke-width="2.5"/>')
    for a, t in TAUS.items():
        x = at(t)
        svg.append(f'<line x1="{px(t):.1f}" x2="{px(t):.1f}" y1="{T}" y2="{H - B}" stroke="#101318" stroke-dasharray="4 3" opacity=".5"/>')
        svg.append(f'<text x="{px(t) + 4:.1f}" y="{T + 12}" fill="#101318" font-size="11">α={a}: τ={t:.2f}</text>')
        svg.append(f'<circle cx="{px(t):.1f}" cy="{py(x["recall"]):.1f}" r="4" fill="#2a78d6"/><circle cx="{px(t):.1f}" cy="{py(x["false_flag_same"]):.1f}" r="4" fill="#a3221a"/>')
    svg.append(f'<text x="{W - 24}" y="{py(table[60]["recall"]) - 8:.1f}" text-anchor="end" fill="#2a78d6" font-weight="bold">recall on exaggerations</text>')
    svg.append(f'<text x="{W - 24}" y="{py(table[60]["false_flag_same"]) + 16:.1f}" text-anchor="end" fill="#a3221a" font-weight="bold">false flags on faithful releases</text>')
    svg.append(f'<text x="{px((min(keep) + max(keep)) / 2):.1f}" y="{H - B - 6}" text-anchor="middle" fill="#2a78d6" font-size="11">any threshold here keeps false flags ≤ 10%</text>')
    svg.append(f'<text x="{(L + W) / 2:.1f}" y="{H - 6}" text-anchor="middle" fill="#56606c">block threshold on the overclaim score (563 test pairs, saved Decider scores)</text></svg>')
    (HERE.parent / "docs" / "sweep.svg").write_text("".join(svg), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
