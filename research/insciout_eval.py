"""Second test: the advisory checks on full, real 2011 UK press releases coded by Sumner et al.

See PREREGISTRATION-insciout.md. Needs the InSciOut archive (figshare 903704, CC BY 4.0)
unzipped somewhere; pass its `open data` folder.

    python research/insciout_eval.py --insciout "path/to/open data"
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

import docx
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from decision_pattern.decider import Decider  # noqa: E402
from research.calibration_eval import wilson  # noqa: E402
from research.spike import auroc, macro_f1  # noqa: E402

ANIMAL_Q = {
    "type": "noul",
    "instructions": "Does the press release present the finding as if it applied to people?",
    "criteria": {
        "true": "the press release talks about people, patients or humans as if the study had shown "
        "the effect in them",
        "false": "the press release keeps clear that the finding is in animals, cells or a lab model",
    },
}

ADVICE_LEVELS = ["no_advice", "implicit", "explicit_indirect", "explicit_direct"]
ADVICE_Q = {
    "type": "choice",
    "instructions": "What is the strongest advice or recommendation this text gives?",
    "criteria": {
        "no_advice": "no advice or recommendation of any kind",
        "implicit": "only implies what might be done, e.g. 'has implications for treatment', "
        "'could help doctors'",
        "explicit_indirect": "explicitly recommends what others should do, e.g. 'doctors should', "
        "'policy makers need to', 'parents ought to'",
        "explicit_direct": "explicitly tells the reader what to do, e.g. 'you should', 'eat more', "
        "'avoid', 'people should take'",
    },
}


def label_rows(book, sheet: str) -> dict[int, tuple[int, int]]:
    out = {}
    for r in list(book[sheet].iter_rows(values_only=True))[5:]:
        if isinstance(r[0], (int, float)) and r[3] is not None:
            out[int(r[0])] = (int(r[2]), int(r[3]))
    return out


def release_text(folder: Path, files: list[str], article_id: int) -> str:
    d = docx.Document(str(folder / files[article_id - 1]))
    return "\n".join(p.text for p in d.paragraphs if p.text.strip())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--insciout", type=Path, required=True)
    args = ap.parse_args()
    out_dir = ROOT / "research" / "results" / "insciout"
    out_dir.mkdir(parents=True, exist_ok=True)

    book = openpyxl.load_workbook(args.insciout / "2. data" / "Tables for GEE analysis.xlsx", read_only=True)
    pr_dir = args.insciout / "5. Press releases"
    files = sorted(os.listdir(pr_dir))
    decider = Decider()

    animal = []
    for aid, (journal, pr) in sorted(label_rows(book, "non-numan").items()):
        if journal != 0:
            continue
        state = ("The study this press release reports was done in animals, cells or a lab model, "
                 f"not in people.\n\nPRESS RELEASE:\n{release_text(pr_dir, files, aid)}")
        p = decider.ask(state, {"q": ANIMAL_Q})["q"]["noul"]
        animal.append({"article_id": aid, "file": files[aid - 1], "gold_pr_code": pr, "gold_human": int(pr > 0), "p_human": round(p, 4)})

    advice = []
    for aid, (journal, pr) in sorted(label_rows(book, "advice").items()):
        ans = decider.ask(release_text(pr_dir, files, aid), {"q": ADVICE_Q})["q"]
        probs = [ans["probabilities"][k] for k in ADVICE_LEVELS]
        advice.append({"article_id": aid, "file": files[aid - 1], "gold_journal": journal, "gold_pr": pr,
                       "gold_inflated": int(pr > journal), "pred_pr": ADVICE_LEVELS.index(ans["choice"]),
                       "p_explicit": round(probs[2] + probs[3], 4),
                       "p_inflated": round(sum(probs[i] for i in range(4) if i > journal), 4)})

    for name, rows in (("animal_items.csv", animal), ("advice_items.csv", advice)):
        with (out_dir / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    hum = [r for r in animal if r["gold_human"]]
    faith = [r for r in animal if not r["gold_human"]]
    summary = {
        "animal": {
            "n": len(animal), "n_human_inferred": len(hum),
            "auroc": round(auroc([r["gold_human"] for r in animal], [r["p_human"] for r in animal]), 4),
            "at_0.5": {"recall": round(sum(r["p_human"] >= 0.5 for r in hum) / len(hum), 4),
                       "recall_95ci": wilson(sum(r["p_human"] >= 0.5 for r in hum), len(hum)),
                       "false_flag": round(sum(r["p_human"] >= 0.5 for r in faith) / len(faith), 4),
                       "false_flag_95ci": wilson(sum(r["p_human"] >= 0.5 for r in faith), len(faith))},
        },
        "advice": {
            "n": len(advice),
            "macro_f1_4class": round(macro_f1([r["gold_pr"] for r in advice], [r["pred_pr"] for r in advice], [0, 1, 2, 3]), 4),
            "auroc_explicit": round(auroc([int(r["gold_pr"] >= 2) for r in advice], [r["p_explicit"] for r in advice]), 4),
            "auroc_inflated": round(auroc([r["gold_inflated"] for r in advice], [r["p_inflated"] for r in advice]), 4),
            "n_inflated": sum(r["gold_inflated"] for r in advice),
        },
        "decider_calls": decider.calls,
        "decider_median_ms": round(decider.total_ms / max(1, decider.calls), 1),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
