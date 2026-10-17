"""Day-1 feasibility spike: zero-shot Strands Decider on two public exaggeration benchmarks.

See PREREGISTRATION-spike.md for the variants, metrics and decision rule, all fixed before
running. Talks to a running `strands-decider serve` over HTTP, one request at a time.

    python spike.py --wa DATA/scientific-exaggeration-detection/test.jsonl \
                    --yu DATA/causal-language-use-in-science/data/pubmed_causal_language_use.csv \
                    --out results/
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
import urllib.request
from pathlib import Path

URL = "http://127.0.0.1:8099/v1/systemone"

STRENGTH = ["no_relationship", "correlational", "conditional_causal", "direct_causal"]

STRENGTH_Q = {
    "type": "choice",
    "instructions": "How strong is the relationship this scientific statement claims?",
    "criteria": {
        "no_relationship": "no correlational or causal relationship is stated; it reports a "
        "description, a method, a null result or a single finding",
        "correlational": "states an association between variables without claiming one causes "
        "the other, e.g. 'associated with', 'linked to', 'more likely to have'",
        "conditional_causal": "states a causal relationship with hedging, e.g. 'may reduce', "
        "'might cause', 'could improve'",
        "direct_causal": "states outright that one thing causes, prevents, reduces, improves or "
        "increases another, e.g. 'reduces', 'leads to', 'saves lives'",
    },
}

DIRECT_Q = {
    "type": "choice",
    "instructions": "Compared with the paper's own conclusion, how does the press release "
    "describe the finding?",
    "criteria": {
        "same": "the press release claims a relationship of the same strength as the paper",
        "exaggerates": "the press release claims a stronger or more certain relationship than "
        "the paper, e.g. causation where the paper reports association",
        "downplays": "the press release claims a weaker or more hedged relationship than the paper",
    },
}

NOUL_Q = {
    "type": "noul",
    "instructions": "Does the press release claim a stronger or more certain relationship than "
    "the paper's conclusion supports?",
    "criteria": {
        "true": "the press release overstates the finding, e.g. states causation where the paper "
        "reports only association, or drops the paper's hedging",
        "false": "the press release claims no more than the paper does",
    },
}


def ask(state: str, questions: dict) -> tuple[dict, float]:
    body = json.dumps({"state": state, "questions": questions}).encode()
    req = urllib.request.Request(URL, body, {"content-type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.load(r)
    return out["answers"], (time.perf_counter() - t0) * 1000


def pair_state(abstract: str, press: str) -> str:
    return (
        "A scientific paper's conclusion and the press release written about it.\n\n"
        f"PAPER'S CONCLUSION: {abstract}\n\nPRESS RELEASE: {press}"
    )


def macro_f1(gold: list, pred: list, labels: list) -> float:
    f1s = []
    for c in labels:
        tp = sum(g == c and p == c for g, p in zip(gold, pred))
        fp = sum(g != c and p == c for g, p in zip(gold, pred))
        fn = sum(g == c and p != c for g, p in zip(gold, pred))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return sum(f1s) / len(f1s)


def auroc(y: list[int], s: list[float]) -> float:
    pos = [v for v, t in zip(s, y) if t]
    neg = [v for v, t in zip(s, y) if not t]
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def lat(ms: list[float]) -> dict:
    ms = sorted(ms)
    return {"median_ms": round(statistics.median(ms), 1), "p95_ms": round(ms[int(0.95 * (len(ms) - 1))], 1)}


def run_wa(path: Path, out: Path) -> dict:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    recs, lat_pair, lat_sent = [], [], []
    for i, r in enumerate(rows):
        ans, ms = ask(pair_state(r["abstract_conclusion"], r["press_release_conclusion"]),
                      {"direct": DIRECT_Q, "overclaim": NOUL_Q})
        lat_pair.append(ms)
        a_ans, ms_a = ask(r["abstract_conclusion"], {"strength": STRENGTH_Q})
        p_ans, ms_p = ask(r["press_release_conclusion"], {"strength": STRENGTH_Q})
        lat_sent += [ms_a, ms_p]
        pa = [a_ans["strength"]["probabilities"][k] for k in STRENGTH]
        pp = [p_ans["strength"]["probabilities"][k] for k in STRENGTH]
        p_exag = sum(pp[i_] * pa[j] for i_ in range(4) for j in range(4) if i_ > j)
        p_down = sum(pp[i_] * pa[j] for i_ in range(4) for j in range(4) if i_ < j)
        sa, sp = pa.index(max(pa)), pp.index(max(pp))
        v2 = "exaggerates" if sp > sa else "downplays" if sp < sa else "same"
        recs.append({
            "id": r["original_file_id"], "gold": r["exaggeration_label"],
            "gold_abs_strength": r["abstract_strength"], "gold_pr_strength": r["press_release_strength"],
            "v1_pred": ans["direct"]["choice"], "v1_p_exag": round(ans["direct"]["probabilities"]["exaggerates"], 4),
            "v1_conf": round(ans["direct"]["confidence"], 4),
            "v3_p_overclaim": round(ans["overclaim"]["noul"], 4),
            "v2_pred": v2, "v2_p_exag": round(p_exag, 4), "v2_p_down": round(p_down, 4),
            "v2_abs_strength": sa, "v2_pr_strength": sp,
        })
        if i % 50 == 0:
            print(f"W&A {i}/{len(rows)}", flush=True)

    with (out / "wa_items.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(recs[0]))
        w.writeheader()
        w.writerows(recs)

    gold = [r["gold"] for r in recs]
    y = [int(g == "exaggerates") for g in gold]
    labels = ["same", "exaggerates", "downplays"]
    same = [r for r in recs if r["gold"] == "same"]
    strength_gold = [r["gold_abs_strength"] for r in recs] + [r["gold_pr_strength"] for r in recs]
    strength_pred = [r["v2_abs_strength"] for r in recs] + [r["v2_pr_strength"] for r in recs]
    return {
        "n": len(recs),
        "label_counts": {c: gold.count(c) for c in labels},
        "v1_macro_f1": round(macro_f1(gold, [r["v1_pred"] for r in recs], labels), 4),
        "v2_macro_f1": round(macro_f1(gold, [r["v2_pred"] for r in recs], labels), 4),
        "v1_auroc_exag": round(auroc(y, [r["v1_p_exag"] for r in recs]), 4),
        "v2_auroc_exag": round(auroc(y, [r["v2_p_exag"] for r in recs]), 4),
        "v3_auroc_exag": round(auroc(y, [r["v3_p_overclaim"] for r in recs]), 4),
        "false_flag_on_same": {
            "v1_argmax": round(sum(r["v1_pred"] == "exaggerates" for r in same) / len(same), 4),
            "v2_argmax": round(sum(r["v2_pred"] == "exaggerates" for r in same) / len(same), 4),
            "v3_at_0.5": round(sum(r["v3_p_overclaim"] >= 0.5 for r in same) / len(same), 4),
        },
        "strength_macro_f1_on_wa_sentences": round(macro_f1(strength_gold, strength_pred, [0, 1, 2, 3]), 4),
        "latency_pair_request": lat(lat_pair),
        "latency_sentence_request": lat(lat_sent),
    }


def run_yu(path: Path, out: Path) -> dict:
    with path.open(encoding="utf-8", errors="replace") as f:
        rows = [r for r in csv.DictReader(f) if r["sentence"].strip()]
    recs, ms_all = [], []
    for i, r in enumerate(rows):
        ans, ms = ask(r["sentence"], {"strength": STRENGTH_Q})
        ms_all.append(ms)
        probs = ans["strength"]["probabilities"]
        recs.append({"gold": int(r["label"]), "pred": STRENGTH.index(ans["strength"]["choice"]),
                     "conf": round(ans["strength"]["confidence"], 4),
                     **{f"p_{k}": round(probs[k], 4) for k in STRENGTH}})
        if i % 250 == 0:
            print(f"Yu19 {i}/{len(rows)}", flush=True)

    with (out / "yu19_items.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(recs[0]))
        w.writeheader()
        w.writerows(recs)

    gold, pred = [r["gold"] for r in recs], [r["pred"] for r in recs]
    bin_rows = [r for r in recs if r["gold"] in (1, 3)]  # correlational vs direct causal
    bg = [int(r["gold"] == 3) for r in bin_rows]
    bp = [int(r["p_direct_causal"] > r["p_correlational"]) for r in bin_rows]
    tp = sum(g and p for g, p in zip(bg, bp))
    prec = tp / max(1, sum(bp))
    rec = tp / max(1, sum(bg))
    return {
        "n": len(recs),
        "macro_f1_4class": round(macro_f1(gold, pred, [0, 1, 2, 3]), 4),
        "accuracy_4class": round(sum(g == p for g, p in zip(gold, pred)) / len(recs), 4),
        "direct_vs_correlational_f1": round(2 * prec * rec / (prec + rec) if prec + rec else 0.0, 4),
        "direct_vs_correlational_auroc": round(auroc(bg, [r["p_direct_causal"] - r["p_correlational"] for r in bin_rows]), 4),
        "latency": lat(ms_all),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wa", type=Path, required=True)
    ap.add_argument("--yu", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    summary = {"model": "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610", "wa": run_wa(args.wa, args.out)}
    print(json.dumps(summary["wa"], indent=1), flush=True)
    summary["yu19"] = run_yu(args.yu, args.out)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
