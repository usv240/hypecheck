"""Do Claude's summaries of the HypeWatch papers overclaim, and does the gate fix them?
See PREREGISTRATION-ai-summaries.md. Needs a Decider (STRANDS_DECIDER_URL) and Bedrock access.

    python -m research.ai_summary_eval            # resumes from items.jsonl if interrupted
    python -m research.ai_summary_eval --summary  # recompute summary.json only
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import boto3
from botocore.config import Config

from decision_pattern.decider import Decider
from decision_pattern.fidelity import check_document, overclaim_probability, split_sentences, strength
from decision_pattern.gate import zone
from hypecheck.agent import thresholds
from hypecheck.hypewatch import DATA, paper_conclusion

OUT = Path(__file__).resolve().parent / "results" / "ai-summaries"
MODELS = {"sonnet-4-6": "us.anthropic.claude-sonnet-4-6",
          "haiku-4-5": "us.anthropic.claude-haiku-4-5-20251001-v1:0"}
REWRITER = MODELS["sonnet-4-6"]
SUMMARY_PROMPT = ("Summarize the key findings of this research abstract for a general audience in three sentences. "
                  "Reply with the summary only.\n\nABSTRACT: {abstract}")
REWRITE_PROMPT = (
    "A sentence from an AI-written summary of a research paper claims more than the paper supports. Rewrite "
    "the sentence so it claims no more than the paper's conclusion supports: keep its topic and plain-language "
    "style, use association language for correlational findings and hedged language for tentative ones, and do "
    "not add facts. Reply with the rewritten sentence only.\n\nPAPER'S CONCLUSION: {paper}\n\nSENTENCE: {sentence}")
NIH_SENTENCE_BLOCK_RATE = 0.0293  # 18 of 615 HypeWatch sentences, same papers, same rule


def ask(bedrock, model: str, prompt: str, max_tokens: int, temperature: float | None = None) -> str:
    cfg = {"maxTokens": max_tokens} | ({"temperature": temperature} if temperature is not None else {})
    resp = bedrock.converse(modelId=model, messages=[{"role": "user", "content": [{"text": prompt}]}],
                            inferenceConfig=cfg)
    text = "".join(b.get("text", "") for b in resp["output"]["message"]["content"]).strip().strip('"')
    return re.sub(r"[*_#]{1,2}([^*_#]+)[*_#]{1,2}", r"\1", text)


def public_p(decider: Decider, p_sentence: list[float], p_conclusion: list[float], p_strongest: list[float]) -> float:
    return min(overclaim_probability(p_sentence, p_conclusion), overclaim_probability(p_sentence, p_strongest))


def run_paper(rec: dict, decider: Decider, bedrock, thr: float, rev: float) -> dict | None:
    paper = paper_conclusion(rec["doi"])
    if not paper or len(paper[1]) < 30 or len(paper[3]) < 200:
        return {"doi": rec["doi"], "skipped": "abstract not available"}
    _, conclusion, source, abstract = paper
    levels = [strength(decider, a) for a in split_sentences(abstract)[:14]]
    expected = lambda p: sum(i * x for i, x in enumerate(p))  # noqa: E731
    p_strongest = max(levels, key=expected) if levels else strength(decider, conclusion)
    out = {"doi": rec["doi"], "title": rec["title"], "conclusion": conclusion, "abstract_source": source,
           "summaries": {}}
    for name, model in MODELS.items():
        summary = ask(bedrock, model, SUMMARY_PROMPT.format(abstract=abstract), 300)
        verdict = check_document(decider, conclusion, summary)
        sents = []
        for s in verdict.sentences:
            p = public_p(decider, s.p_strength, verdict.p_source, p_strongest)
            item = {"text": s.sentence, "strength": s.strength, "p": round(p, 4), "zone": zone(p, thr, rev)}
            if item["zone"] == "block":
                text, ok = s.sentence, False
                for attempt in (1, 2):
                    text = ask(bedrock, REWRITER, REWRITE_PROMPT.format(paper=conclusion, sentence=text), 200, 0)
                    p2 = public_p(decider, strength(decider, text), verdict.p_source, p_strongest)
                    if p2 <= thr:
                        ok = True
                        break
                item.update(rewrite=text, rewrite_p=round(p2, 4), rewrite_ok=ok, attempts=attempt)
            sents.append(item)
        out["summaries"][name] = {"summary": summary, "sentences": sents, "advisory": verdict.advisory}
    return out


def summarize(items: list[dict], thr: float) -> dict:
    done = [i for i in items if "summaries" in i]
    res = {"papers": len(items), "checked": len(done), "skipped": len(items) - len(done),
           "nih_sentence_block_rate": NIH_SENTENCE_BLOCK_RATE, "threshold": thr, "models": {}}
    for name in MODELS:
        sums = [i["summaries"][name] for i in done]
        sents = [s for x in sums for s in x["sentences"]]
        flagged = [x for x in sums if any(s["zone"] == "block" for s in x["sentences"])]
        fixed = [x for x in flagged if all(s.get("rewrite_ok", True) for s in x["sentences"])]
        blocks = [s for s in sents if s["zone"] == "block"]
        res["models"][name] = {
            "summaries": len(sums), "sentences": len(sents),
            "summaries_with_block": round(len(flagged) / len(sums), 4) if sums else None,
            "summaries_with_review": round(sum(any(s["zone"] == "review" for s in x["sentences"]) for x in sums)
                                           / len(sums), 4) if sums else None,
            "sentence_block_rate": round(len(blocks) / len(sents), 4) if sents else None,
            "flagged_summaries_fixed_by_gate": round(len(fixed) / len(flagged), 4) if flagged else None,
            "block_sentences_fixed": round(sum(s["rewrite_ok"] for s in blocks) / len(blocks), 4) if blocks else None,
            "advice_inflated_over_half": round(sum(x["advisory"].get("advice_inflated", 0) > 0.5 for x in sums)
                                               / len(sums), 4) if sums else None,
        }
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "items.jsonl"
    items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    thr, rev = thresholds()
    if not args.summary:
        seen = {i["doi"] for i in items}
        papers = [r for r in json.loads(Path(DATA).read_text(encoding="utf-8"))["releases"] if r["doi"] not in seen]
        decider = Decider(timeout=300)
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1",
                               config=Config(retries={"max_attempts": 8, "mode": "adaptive"}))
        for n, rec in enumerate(papers[: args.limit or None], 1):
            try:
                item = run_paper(rec, decider, bedrock, thr, rev)
            except Exception as exc:  # leave it for a rerun
                print(f"failed {rec['doi']}: {type(exc).__name__}: {exc}", flush=True)
                continue
            items.append(item)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
            print(n, rec["doi"], {k: [s["zone"] for s in v["sentences"]] for k, v in item.get("summaries", {}).items()},
                  flush=True)
    (OUT / "summary.json").write_text(json.dumps(summarize(items, thr), indent=1))
    print(json.dumps(summarize(items, thr), indent=1))


if __name__ == "__main__":
    main()
