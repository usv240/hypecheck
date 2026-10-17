"""Named baseline: Claude on Amazon Bedrock as the exaggeration judge, same pairs as spike.py.

The obvious alternative to a decision model is to ask a frontier LLM. This asks it the same
three-way question over the same Wright & Augenstein test pairs and records accuracy, per-call
latency and token usage, so cost can be computed from published Bedrock prices.

    python baseline_bedrock.py --wa data/test.jsonl --model us.anthropic.claude-haiku-4-5-20251001-v1:0 \
        --out research/results/baseline-haiku45
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3
from botocore.config import Config

from spike import auroc, macro_f1, pair_state

MAX_TOKENS = 400

SYSTEM = (
    "You compare a health press release with the conclusion of the scientific paper it reports. "
    "Decide whether the press release describes the finding with the same strength as the paper, "
    "exaggerates it (a stronger or more certain relationship, e.g. causation where the paper "
    "reports association), or downplays it (a weaker or more hedged relationship). "
    'Reply with JSON only: {"label": "same" | "exaggerates" | "downplays", "p_exaggerates": <0..1>}'
)


def judge(client, model: str, row: dict) -> dict:
    t0 = time.perf_counter()
    resp = client.converse(
        modelId=model,
        system=[{"text": SYSTEM}],
        messages=[{"role": "user", "content": [{"text": pair_state(row["abstract_conclusion"], row["press_release_conclusion"])}]}],
        inferenceConfig={"maxTokens": MAX_TOKENS, "temperature": 0},
    )
    ms = (time.perf_counter() - t0) * 1000
    # An empty reply (e.g. stopReason "refusal") counts as unparsed rather than crashing the run.
    text = "".join(b.get("text", "") for b in resp["output"]["message"]["content"])
    try:
        parsed = json.loads(text[text.index("{"): text.rindex("}") + 1])
        label, p = parsed["label"], float(parsed.get("p_exaggerates", 0.5))
    except (ValueError, KeyError):
        label, p = "unparsed", 0.5
    return {"id": row["original_file_id"], "gold": row["exaggeration_label"], "pred": label,
            "p_exag": p, "latency_ms": round(ms, 1), "stop": resp.get("stopReason", ""),
            "in_tok": resp["usage"]["inputTokens"], "out_tok": resp["usage"]["outputTokens"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wa", type=Path, required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-tokens", type=int, default=400, help="Opus 4.6 reasons in prose before the JSON; 60 truncated 405/563")
    args = ap.parse_args()
    global MAX_TOKENS
    MAX_TOKENS = args.max_tokens
    args.out.mkdir(parents=True, exist_ok=True)

    rows = [json.loads(line) for line in args.wa.read_text(encoding="utf-8").splitlines() if line.strip()]
    client = boto3.client("bedrock-runtime", region_name=args.region,
                          config=Config(retries={"max_attempts": 10, "mode": "adaptive"}))
    with ThreadPoolExecutor(args.workers) as pool:
        recs = list(pool.map(lambda r: judge(client, args.model, r), rows))

    with (args.out / "items.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(recs[0]))
        w.writeheader()
        w.writerows(recs)

    gold = [r["gold"] for r in recs]
    same = [r for r in recs if r["gold"] == "same"]
    ms = sorted(r["latency_ms"] for r in recs)
    summary = {
        "model": args.model, "n": len(recs),
        "macro_f1": round(macro_f1(gold, [r["pred"] for r in recs], ["same", "exaggerates", "downplays"]), 4),
        "auroc_exag": round(auroc([int(g == "exaggerates") for g in gold], [r["p_exag"] for r in recs]), 4),
        "false_flag_on_same": round(sum(r["pred"] == "exaggerates" for r in same) / len(same), 4),
        "unparsed": sum(r["pred"] == "unparsed" for r in recs),
        "latency_median_ms": round(statistics.median(ms), 1),
        "latency_p95_ms": ms[int(0.95 * (len(ms) - 1))],
        "input_tokens": sum(r["in_tok"] for r in recs), "output_tokens": sum(r["out_tok"] for r in recs),
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
