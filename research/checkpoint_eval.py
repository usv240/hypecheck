"""Score W&A pairs with a given Decider checkpoint, same question and score as the live gate.
See PREREGISTRATION-checkpoints.md.

    python research/checkpoint_eval.py score --url http://127.0.0.1:8101 --name hobson-v21 --split train --wa-dir data
    python research/checkpoint_eval.py summary --wa-dir data
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import random
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from spike import STRENGTH_Q, auroc  # noqa: E402

# Load the stdlib-only parts of decision_pattern without its Strands-dependent __init__.
_pkg = types.ModuleType("decision_pattern")
_pkg.__path__ = [str(HERE.parent / "decision_pattern")]
sys.modules.setdefault("decision_pattern", _pkg)


def _load(name):
    spec = importlib.util.spec_from_file_location(f"decision_pattern.{name}", f"{_pkg.__path__[0]}/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"decision_pattern.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


Decider = _load("decider").Decider
LEVELS = ["no_relationship", "correlational", "conditional_causal", "direct_causal"]
OUT = HERE / "results" / "checkpoints"


def conformal(scores: list[float], alpha: float) -> float:
    import math
    k = math.ceil((len(scores) + 1) * (1 - alpha))
    return sorted(scores)[k - 1]


def p_over(pd: list[float], ps: list[float]) -> float:
    return sum(pd[i] * ps[j] for i in range(4) for j in range(4) if i > j)


def strength(d: Decider, text: str) -> list[float]:
    a = d.ask(text, {"strength": STRENGTH_Q})["strength"]["probabilities"]
    return [a[k] for k in LEVELS]


def load_wa(wa_dir: Path, split: str) -> list[dict]:
    return [json.loads(x) for x in (wa_dir / f"{split}.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


def score(args) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{args.name}_{args.split}.jsonl"
    done = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
    rows = load_wa(args.wa_dir, args.split)
    d = Decider(url=args.url, timeout=600)
    with path.open("a", encoding="utf-8") as f:
        for i, r in enumerate(rows[done:], done):
            ps, pd = strength(d, r["abstract_conclusion"]), strength(d, r["press_release_conclusion"])
            f.write(json.dumps({"i": i, "id": r["original_file_id"], "gold": r["exaggeration_label"],
                                "p_src": [round(x, 5) for x in ps], "p_der": [round(x, 5) for x in pd],
                                "p_exag": round(p_over(pd, ps), 5)}) + "\n")
            f.flush()
            if i % 20 == 0:
                print(args.name, args.split, i, flush=True)


def items(name: str, split: str) -> list[dict]:
    p = OUT / f"{name}_{split}.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def summary(args) -> None:
    train = load_wa(args.wa_dir, "train")
    gold_tr = [r["exaggeration_label"] for r in train]
    y_tr = [int(g == "exaggerates") for g in gold_tr]
    c0_tr = json.loads((HERE / "results" / "calibration" / "train_scores.json").read_text())
    cands = {"C0 v1-2610": c0_tr}
    for name in ("hobson-v21", "hobson-v19"):
        it = items(name, "train")
        if len(it) == len(train):
            assert [x["gold"] for x in it] == gold_tr
            cands[name] = [x["p_exag"] for x in it]
    tr_auc = {k: round(auroc(y_tr, v), 4) for k, v in cands.items()}
    others = {k: v for k, v in tr_auc.items() if not k.startswith("C0")}
    out = {"train_auroc": tr_auc}
    if others:
        best = max(others, key=others.get)
        cands["E mean(C0," + best + ")"] = [(a + b) / 2 for a, b in zip(c0_tr, cands[best])]
        out["train_auroc"] = {k: round(auroc(y_tr, v), 4) for k, v in cands.items()}
    tr = out["train_auroc"]
    pick = max(tr, key=tr.get)
    if not pick.startswith("C0") and tr[pick] - tr["C0 v1-2610"] < 0.03:
        pick = "C0 v1-2610"
    out["picked"] = pick
    out["test_run_required"] = not pick.startswith("C0")

    # test, only for the picked candidate (and only if its per-item test scores exist)
    dec = list(csv.DictReader((HERE / "results" / "spike-v1" / "wa_items.csv").open(encoding="utf-8")))
    gold = [r["gold"] for r in dec]
    y = [int(g == "exaggerates") for g in gold]
    c0 = [float(r["v2_p_exag"]) for r in dec]
    if out["test_run_required"]:
        base = pick.split("(")[-1].rstrip(")").split(",")[-1] if pick.startswith("E") else pick
        it = items(base, "test")
        if len(it) == len(dec):
            assert [x["id"] for x in it] == [r["id"] for r in dec]
            other = [x["p_exag"] for x in it]
            new = [(a + b) / 2 for a, b in zip(c0, other)] if pick.startswith("E") else other
            new_tr = cands[pick]
            neg = lambda sc: [s for s, g in zip(sc, gold_tr) if g != "exaggerates"]  # noqa: E731
            t_new, t_c0 = conformal(neg(new_tr), 0.10), conformal(neg(c0_tr), 0.10)

            def stats(sc, t, idx=None):
                idx = idx or range(len(gold))
                g = [gold[i] for i in idx]; s = [sc[i] for i in idx]
                rec = [x > t for x, gg in zip(s, g) if gg == "exaggerates"]
                ffn = [x > t for x, gg in zip(s, g) if gg != "exaggerates"]
                ffs = [x > t for x, gg in zip(s, g) if gg == "same"]
                return {"auroc": auroc([int(gg == "exaggerates") for gg in g], s), "recall": sum(rec) / len(rec),
                        "ff_not_overclaim": sum(ffn) / len(ffn), "ff_same": sum(ffs) / len(ffs)}

            a, b = stats(new, t_new), stats(c0, t_c0)
            rng = random.Random(0)
            dr, da = [], []
            for _ in range(5000):
                ix = [rng.randrange(len(gold)) for _ in range(len(gold))]
                sa, sb = stats(new, t_new, ix), stats(c0, t_c0, ix)
                dr.append(sa["recall"] - sb["recall"]); da.append(sa["auroc"] - sb["auroc"])
            dr.sort(); da.sort()
            ci = lambda xs: [round(xs[125], 4), round(xs[4874], 4)]  # noqa: E731
            out["test"] = {"threshold": round(t_new, 4), "picked": {k: round(v, 4) for k, v in a.items()},
                           "C0": {k: round(v, 4) for k, v in b.items()},
                           "recall_gain": round(a["recall"] - b["recall"], 4), "recall_gain_95ci": ci(dr),
                           "auroc_gain": round(a["auroc"] - b["auroc"], 4), "auroc_gain_95ci": ci(da)}
            out["adopted"] = (a["recall"] - b["recall"] >= 0.05 and a["ff_not_overclaim"] <= 0.10
                              and a["auroc"] >= b["auroc"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score")
    s.add_argument("--url", required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--split", choices=["train", "test"], required=True)
    s.add_argument("--wa-dir", type=Path, required=True)
    m = sub.add_parser("summary")
    m.add_argument("--wa-dir", type=Path, required=True)
    a = ap.parse_args()
    score(a) if a.cmd == "score" else summary(a)


if __name__ == "__main__":
    main()
