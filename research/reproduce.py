"""Recompute every headline number from the saved per-item outputs. Offline: no Decider, no AWS,
no network, $0, a few seconds.

    python research/reproduce.py

It verifies the result files against MANIFEST.json, recomputes each number from the per-item rows
(not from the saved summaries), and checks it against the value the README states. Exit code 1
if anything differs.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE / "results"
sys.path.insert(0, str(HERE))

from spike import auroc, macro_f1 as _mf1  # noqa: E402

LABELS = ["same", "exaggerates", "downplays"]
macro_f1 = lambda g, p: _mf1(g, p, LABELS)  # noqa: E731

BLOCK, REVIEW = 0.5001, 0.3986  # conformal thresholds at alpha 0.10 and 0.20 (results/calibration/summary.json)


def rows(p: Path) -> list[dict]:
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def jl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def rate(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs)


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    checks: list[tuple[str, float, float, float]] = []  # (claim, recomputed, stated, tolerance)

    def check(claim: str, value: float, stated: float, tol: float = 0.0006) -> None:
        checks.append((claim, value, stated, tol))

    # 0. the files are the ones the numbers were computed from
    bad = [f for f, m in json.loads((R / "MANIFEST.json").read_text())["files"].items()
           if (R / f).exists() and load("manifest").sha(R / f) != m["sha256"]]
    print("manifest:", "all result files match" if not bad else f"CHANGED: {bad}")

    # 1. benchmark: Decider vs Claude on 563 Wright & Augenstein pairs
    dec = rows(R / "spike-v1" / "wa_items.csv")
    gold = [r["gold"] for r in dec]
    y = [int(g == "exaggerates") for g in gold]
    p = [float(r["v2_p_exag"]) for r in dec]
    check("Decider macro-F1 (3 labels)", macro_f1(gold, [r["v2_pred"] for r in dec]), 0.498, 0.0006)
    check("Decider AUROC, exaggerates vs not", auroc(y, p), 0.716)
    check("Decider false flags on faithful, alpha 0.10", rate(x > BLOCK for x, g in zip(p, gold) if g == "same"), 0.067)
    check("Decider recall at alpha 0.10", rate(x > BLOCK for x, g in zip(p, gold) if g == "exaggerates"), 0.385)
    check("Conformal promise: false flags on 441 non-exaggerating", rate(x > BLOCK for x, g in zip(p, gold) if g != "exaggerates"), 0.077)
    for name, ff, f1 in (("haiku45", 0.449, 0.358), ("sonnet-4-6", 0.296, 0.401), ("opus-4-6", 0.400, 0.460)):
        llm = rows(R / f"baseline-{name}" / "items.csv")
        assert [r["gold"] for r in llm] == gold, name
        check(f"Claude {name} false flags on faithful", rate(r["pred"] == "exaggerates" for r in llm if r["gold"] == "same"), ff)
        check(f"Claude {name} macro-F1", macro_f1(gold, [r["pred"] for r in llm]), f1)

    # 2. paired bootstrap (same procedure and seed as significance.py)
    sig = load("significance")
    rng, n = random.Random(0), len(dec)
    samples = [[rng.randrange(n) for _ in range(n)] for _ in range(sig.B)]
    boot = sorted(sig.macro_f1([gold[i] for i in ix], [dec[i]["v2_pred"] for i in ix]) for ix in samples)
    check("Decider macro-F1 95% CI, lower", boot[int(0.025 * sig.B)], 0.452)
    check("Decider macro-F1 95% CI, upper", boot[int(0.975 * sig.B) - 1], 0.541)

    # 3. AWS-native baseline: Bedrock Guardrails contextual grounding
    g = jl(R / "guardrails" / "test_items.jsonl")
    assert [x["id"] for x in g] == [r["id"] for r in dec]
    check("Bedrock Guardrails AUROC", auroc(y, [1 - x["grounding"] for x in g]), 0.503)

    # 4. cascade (Claude only on REVIEW), Sonnet
    son = rows(R / "baseline-sonnet-4-6" / "items.csv")
    flag = [x > BLOCK or (REVIEW < x <= BLOCK and s["pred"] == "exaggerates") for x, s in zip(p, son)]
    check("Cascade recall (Sonnet on REVIEW)", rate(f for f, g0 in zip(flag, gold) if g0 == "exaggerates"), 0.418)

    # 5. HypeWatch: real NIH releases
    hw = json.loads((HERE.parent / "hypecheck" / "hypewatch.json").read_text(encoding="utf-8"))["releases"]
    check("HypeWatch releases checked", len(hw), 85, 0)
    check("HypeWatch releases with a BLOCK sentence", rate(r["flagged"] > 0 for r in hw), 0.153)
    sugg = [s for r in hw for s in r["sentences"] if "suggestion_ok" in s]
    check("HypeWatch rewrites verified", rate(s["suggestion_ok"] for s in sugg), 0.667)

    # 6. AI summaries
    ai = jl(R / "ai-summaries" / "items.jsonl")
    for m, stated in (("sonnet-4-6", 0.118), ("haiku-4-5", 0.106)):
        check(f"AI summaries with a BLOCK ({m})", rate(any(s["zone"] == "block" for s in i["summaries"][m]["sentences"]) for i in ai), stated)

    # 7. InSciOut advice inflation (real UK releases)
    adv = rows(R / "insciout" / "advice_items.csv")
    check("InSciOut advice inflation AUROC", auroc([int(float(r["gold_inflated"])) for r in adv], [float(r["p_inflated"]) for r in adv]), 0.841)

    width = max(len(c[0]) for c in checks)
    fails = 0
    for claim, v, stated, tol in checks:
        ok = abs(v - stated) <= tol
        fails += not ok
        print(f"{'ok ' if ok else 'BAD'} {claim:<{width}}  recomputed {v:.4f}  stated {stated}")
    print(f"\n{len(checks) - fails} of {len(checks)} headline numbers reproduce from the saved per-item outputs.")
    return 1 if fails or bad else 0


if __name__ == "__main__":
    sys.exit(main())
