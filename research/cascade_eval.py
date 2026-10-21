"""Ask Claude only when Decider is unsure. See PREREGISTRATION-cascade.md. Offline: no model calls.

    python research/cascade_eval.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

R = Path(__file__).resolve().parent / "results"
BLOCK, REVIEW = 0.5001, 0.3986
COST_PER_CALL = {"sonnet-4-6": 0.000972, "haiku45": 0.000514}  # measured tokens x Bedrock list price


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def rate(xs: list[bool]) -> float:
    return round(sum(xs) / len(xs), 4) if xs else float("nan")


def evaluate(decider: list[dict], llm: list[dict] | None, name: str) -> dict:
    flags, sent = [], 0
    for i, d in enumerate(decider):
        p = float(d["v2_p_exag"])
        if p > BLOCK:
            flags.append(True)
        elif p <= REVIEW or llm is None:
            flags.append(False)
        else:
            sent += 1
            flags.append(llm[i]["pred"] == "exaggerates")
    gold = [d["gold"] for d in decider]
    same = [f for f, g in zip(flags, gold) if g == "same"]
    not_over = [f for f, g in zip(flags, gold) if g != "exaggerates"]
    over = [f for f, g in zip(flags, gold) if g == "exaggerates"]
    return {"system": name, "recall": rate(over), "false_flag_same": rate(same),
            "false_flag_not_overclaim": rate(not_over), "sent_to_claude": round(sent / len(decider), 4),
            "claude_cost_per_1000": round(1000 * sent / len(decider) * COST_PER_CALL.get(name.split()[-1], 0), 3)}


def main() -> None:
    decider = rows(R / "spike-v1" / "wa_items.csv")
    out = {"n": len(decider), "thresholds": {"block": BLOCK, "review": REVIEW}, "systems": []}
    out["systems"].append(evaluate(decider, None, "decider alone"))
    for name in ("sonnet-4-6", "haiku45"):
        llm = rows(R / f"baseline-{name}" / "items.csv")
        assert len(llm) == len(decider) and all(a["gold"] == b["gold"] for a, b in zip(decider, llm)), name
        out["systems"].append(evaluate(decider, llm, f"cascade {name}"))
        # Claude alone, for reference (its own verdict on every pair)
        g = [r["gold"] for r in llm]
        out["systems"].append({"system": f"claude alone {name}",
                               "recall": rate([r["pred"] == "exaggerates" for r in llm if r["gold"] == "exaggerates"]),
                               "false_flag_same": rate([r["pred"] == "exaggerates" for r in llm if r["gold"] == "same"]),
                               "false_flag_not_overclaim": rate([r["pred"] == "exaggerates" for r in llm if r["gold"] != "exaggerates"]),
                               "sent_to_claude": 1.0, "claude_cost_per_1000": round(1000 * COST_PER_CALL[name], 3)})
    (R / "cascade" ).mkdir(exist_ok=True)
    (R / "cascade" / "summary.json").write_text(json.dumps(out, indent=1))
    for s in out["systems"]:
        print(f"{s['system']:<26} recall {s['recall']:.3f}  ff_same {s['false_flag_same']:.3f}  "
              f"ff_notover {s['false_flag_not_overclaim']:.3f}  to_claude {s['sent_to_claude']:.3f}  $/1000 {s['claude_cost_per_1000']}")


if __name__ == "__main__":
    main()
