"""AWS-native baseline: Amazon Bedrock Guardrails' contextual grounding check on the same pairs.
See PREREGISTRATION-guardrails.md. Creates one temporary guardrail and deletes it afterwards.

    python research/guardrails_baseline.py --wa-dir data            # calls ApplyGuardrail, resumes
    python research/guardrails_baseline.py --wa-dir data --summary  # recompute summary only
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from pathlib import Path

import boto3
from botocore.config import Config

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spike import auroc  # noqa: E402

import importlib.util  # noqa: E402
import types  # noqa: E402

# Load calibrate.py on its own: the package __init__ imports the Strands gate, which this offline
# baseline does not need.
_pkg = types.ModuleType("decision_pattern"); _pkg.__path__ = [str(Path(__file__).resolve().parents[1] / "decision_pattern")]
sys.modules.setdefault("decision_pattern", _pkg)
_spec = importlib.util.spec_from_file_location("decision_pattern.calibrate", _pkg.__path__[0] + "/calibrate.py")
_cal = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_cal)
conformal_threshold = _cal.conformal_threshold

R = Path(__file__).resolve().parent / "results"
OUT = R / "guardrails"
QUERY = "What did the study find?"
REGION = "us-east-1"
PRICE_PER_1000_UNITS = 0.10  # contextual grounding, USD per 1,000 text units (1 unit = up to 1,000 characters)


def make_guardrail(client) -> str:
    g = client.create_guardrail(
        name=f"hypecheck-grounding-baseline-{int(time.time())}",
        description="Temporary: contextual grounding baseline for HypeCheck research. Safe to delete.",
        contextualGroundingPolicyConfig={"filtersConfig": [{"type": "GROUNDING", "threshold": 0.01},
                                                           {"type": "RELEVANCE", "threshold": 0.01}]},
        blockedInputMessaging="blocked", blockedOutputsMessaging="blocked")
    return g["guardrailId"]


def score(rt, gid: str, source: str, derived: str) -> dict:
    t0 = time.perf_counter()
    r = rt.apply_guardrail(guardrailIdentifier=gid, guardrailVersion="DRAFT", source="OUTPUT", content=[
        {"text": {"text": source, "qualifiers": ["grounding_source"]}},
        {"text": {"text": QUERY, "qualifiers": ["query"]}},
        {"text": {"text": derived, "qualifiers": ["guard_content"]}}])
    ms = (time.perf_counter() - t0) * 1000
    f = {x["type"]: x["score"] for a in r.get("assessments", []) for x in a.get("contextualGroundingPolicy", {}).get("filters", [])}
    units = r.get("usage", {}).get("contextualGroundingPolicyUnits", 0)
    return {"grounding": f.get("GROUNDING"), "relevance": f.get("RELEVANCE"), "ms": round(ms, 1), "units": units}


def run(split: str, rows: list[dict], rt, gid: str) -> list[dict]:
    path = OUT / f"{split}_items.jsonl"
    done = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    with path.open("a", encoding="utf-8") as f:
        for i, r in enumerate(rows[len(done):], len(done)):
            s = score(rt, gid, r["abstract_conclusion"], r["press_release_conclusion"])
            item = {"i": i, "id": r["original_file_id"], "gold": r["exaggeration_label"], **s}
            f.write(json.dumps(item) + "\n")
            done.append(item)
            if i % 50 == 0:
                print(split, i, s, flush=True)
    return done


def summarize(train: list[dict], test: list[dict]) -> dict:
    over = lambda x: 1 - x["grounding"]  # noqa: E731
    tau = conformal_threshold([over(x) for x in train if x["gold"] != "exaggerates"], 0.10)
    dec = list(csv.DictReader((R / "spike-v1" / "wa_items.csv").open(encoding="utf-8")))
    assert [d["id"] for d in dec] == [x["id"] for x in test]
    y = [int(x["gold"] == "exaggerates") for x in test]
    g, d = [over(x) for x in test], [float(r["v2_p_exag"]) for r in dec]
    rng, n = random.Random(0), len(y)
    diffs = []
    for _ in range(5000):
        ix = [rng.randrange(n) for _ in range(n)]
        yy = [y[i] for i in ix]
        diffs.append(auroc(yy, [d[i] for i in ix]) - auroc(yy, [g[i] for i in ix]))
    diffs.sort()
    same = [o > tau for o, x in zip(g, test) if x["gold"] == "same"]
    rec = [o > tau for o, x in zip(g, test) if x["gold"] == "exaggerates"]
    ms = sorted(x["ms"] for x in test)
    units = sum(x["units"] for x in train + test)
    return {
        "n_train": len(train), "n_test": n, "threshold_overclaim": round(tau, 4), "alpha": 0.10,
        "guardrails": {"auroc": round(auroc(y, g), 4), "false_flag_same": round(sum(same) / len(same), 4),
                       "recall_exaggerates": round(sum(rec) / len(rec), 4),
                       "latency_ms_p50": ms[n // 2], "latency_ms_p95": ms[int(n * .95)]},
        "decider": {"auroc": round(auroc(y, d), 4)},
        "auroc_gap_decider_minus_guardrails": round(auroc(y, d) - auroc(y, g), 4),
        "auroc_gap_95ci": [round(diffs[int(.025 * len(diffs))], 4), round(diffs[int(.975 * len(diffs)) - 1], 4)],
        "text_units": units, "cost_usd": round(units / 1000 * PRICE_PER_1000_UNITS, 4),
        "cost_per_1000_sentences_usd": round(1000 * units / (len(train) + n) / 1000 * PRICE_PER_1000_UNITS, 4),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wa-dir", type=Path, required=True)
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    load = lambda f: [json.loads(x) for x in (a.wa_dir / f).read_text(encoding="utf-8").splitlines() if x.strip()]  # noqa: E731
    if a.summary:
        rd = lambda s: [json.loads(x) for x in (OUT / f"{s}_items.jsonl").read_text().splitlines()]  # noqa: E731
        train, test = rd("train"), rd("test")
    else:
        cfg = Config(retries={"max_attempts": 10, "mode": "adaptive"})
        ctl = boto3.client("bedrock", region_name=REGION, config=cfg)
        rt = boto3.client("bedrock-runtime", region_name=REGION, config=cfg)
        gid = make_guardrail(ctl)
        print("guardrail", gid, flush=True)
        try:
            train, test = run("train", load("train.jsonl"), rt, gid), run("test", load("test.jsonl"), rt, gid)
        finally:
            ctl.delete_guardrail(guardrailIdentifier=gid)
            print("deleted guardrail", gid, flush=True)
    s = summarize(train, test)
    (OUT / "summary.json").write_text(json.dumps(s, indent=1))
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    main()
