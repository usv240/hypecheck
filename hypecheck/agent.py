"""HypeCheck: a press-office agent that will not publish a health release claiming more than its paper.

Claude on Amazon Bedrock fetches the paper and publishes the release. Before `publish_release`
runs, ClaimFidelityGate has Strands Decider score every sentence against the paper's conclusion;
overclaims send Claude back to rewrite, and the rewrite is checked again.

    python -m hypecheck.agent --draft examples/referral_release.txt --conclusion "Use of ... could be efficacious."
    python -m hypecheck.agent --draft draft.txt --pmid 12345678
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from strands import Agent, tool

from decision_pattern.decider import Decider, DeciderUnavailable
from decision_pattern.fidelity import DocumentVerdict
from decision_pattern.gate import ClaimFidelityGate, load_threshold

ROOT = Path(__file__).resolve().parents[1]
OUTBOX = Path(os.environ.get("HYPECHECK_OUTBOX", ROOT / "outbox"))
MODEL = os.environ.get("HYPECHECK_MODEL", "us.anthropic.claude-sonnet-4-6")
THRESHOLD_FILE = ROOT / "research" / "results" / "calibration" / "summary.json"

SYSTEM = (
    "You are a university press-office assistant. You publish health press releases with the "
    "publish_release tool. When the user gives you a PubMed ID, call fetch_paper first. "
    "Publish the user's draft as written. If publishing is blocked with feedback, rewrite only "
    "the sentences named in the feedback so they claim no more than the paper does, keep the "
    "rest of the release unchanged, and call publish_release again with the full revised text. "
    "Never add claims the paper does not make."
)

Emit = Callable[[dict[str, Any]], None]


def europepmc_conclusion(pmid: str) -> tuple[str, str]:
    """Title and conclusion of a paper from Europe PMC's open REST API."""
    q = urllib.parse.quote(f"EXT_ID:{pmid} AND SRC:MED")
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={q}&resultType=core&format=json"
    with urllib.request.urlopen(url, timeout=30) as r:
        hits = json.load(r)["resultList"]["result"]
    if not hits:
        raise ValueError(f"PMID {pmid} not found in Europe PMC")
    abstract = re.sub(r"<[^>]+>", " ", hits[0].get("abstractText", ""))
    m = re.search(r"(?:CONCLUSIONS?|INTERPRETATION|Conclusions?)\s*[:.]?\s*(.+)$", abstract, re.S)
    conclusion = m.group(1) if m else " ".join(re.split(r"(?<=[.!?])\s+", abstract.strip())[-2:])
    return hits[0].get("title", ""), " ".join(conclusion.split())


def verdict_event(verdict: DocumentVerdict, action: str, threshold: float, round_no: int, text: str) -> dict[str, Any]:
    return {
        "type": "verdict", "round": round_no, "action": action, "threshold": threshold,
        "paper_strength": verdict.source_strength, "text": text,
        "sentences": [{"sentence": s.sentence, "strength": s.strength, "p_overclaim": round(s.p_overclaim, 4),
                       "flagged": s.p_overclaim > threshold, "advisory": s.advisory} for s in verdict.sentences],
    }


def run_hypecheck(draft: str, *, conclusion: str | None = None, pmid: str | None = None,
                  emit: Emit = lambda e: None, decider: Decider | None = None, model: str = MODEL,
                  threshold: float | None = None, max_rounds: int = 3) -> dict[str, Any]:
    """Run the agent once. Every step is reported through `emit`; the summary is returned."""
    decider = decider or Decider()
    threshold = threshold if threshold is not None else load_threshold(THRESHOLD_FILE, "0.1")
    paper = {"conclusion": conclusion or "", "title": ""}
    published: dict[str, str] = {}

    @tool
    def fetch_paper(pmid: str) -> str:
        """Fetch a paper's title and abstract conclusion from Europe PMC.

        Args:
            pmid: the PubMed ID of the paper the press release reports.
        """
        paper["title"], paper["conclusion"] = europepmc_conclusion(pmid)
        emit({"type": "paper", "pmid": pmid, "title": paper["title"], "conclusion": paper["conclusion"]})
        return f"TITLE: {paper['title']}\nCONCLUSION: {paper['conclusion']}"

    @tool
    def publish_release(text: str) -> str:
        """Publish the press release to the newsroom outbox.

        Args:
            text: the full text of the press release.
        """
        OUTBOX.mkdir(parents=True, exist_ok=True)
        path = OUTBOX / f"release-{datetime.now():%Y%m%d-%H%M%S-%f}.txt"
        path.write_text(text, encoding="utf-8")
        published["text"], published["file"] = text, path.name
        emit({"type": "published", "text": text, "file": path.name})
        return f"Published to {path.name}."

    pending: dict[str, Any] = {}

    def on_verdict(verdict: DocumentVerdict, action: str) -> None:
        emit(verdict_event(verdict, action, threshold, gate.rounds, pending.get("text", "")))

    class RecordingGate(ClaimFidelityGate):
        def before_tool_call(self, event, **kwargs):
            if event.tool_use["name"] == self.tool_name:
                pending["text"] = (event.tool_use.get("input") or {}).get(self.text_arg, "")
            return super().before_tool_call(event, **kwargs)

    gate = RecordingGate(decider, lambda: paper["conclusion"], threshold=threshold,
                         max_rounds=max_rounds, on_verdict=on_verdict)
    agent = Agent(model=model, tools=[fetch_paper, publish_release], interventions=[gate],
                  system_prompt=SYSTEM, callback_handler=None)

    if pmid:
        ask = f"Publish this press release about PMID {pmid}:\n\n{draft}"
    else:
        emit({"type": "paper", "pmid": None, "title": "", "conclusion": conclusion})
        ask = f"The paper's conclusion is: {conclusion}\nNo fetch is needed. Publish this press release:\n\n{draft}"

    # The decider client may be shared across runs (the web app keeps one), so count from here.
    calls0, ms0 = decider.calls, decider.total_ms
    t0 = time.perf_counter()
    result = agent(ask)
    wall_ms = (time.perf_counter() - t0) * 1000
    decider_ms = decider.total_ms - ms0
    summary = {
        "type": "done", "published": bool(published), "final_text": published.get("text"),
        "rounds": gate.rounds, "history": gate.history, "agent_reply": str(result),
        "decider_calls": decider.calls - calls0, "decider_ms": round(decider_ms),
        "wall_ms": round(wall_ms), "llm_ms": round(wall_ms - decider_ms),
        "usage": dict(result.metrics.accumulated_usage) if getattr(result, "metrics", None) else {},
    }
    emit(summary)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", type=Path, required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pmid")
    src.add_argument("--conclusion")
    ap.add_argument("--model", default=MODEL)
    args = ap.parse_args()

    decider = Decider()
    try:
        decider.health()
    except DeciderUnavailable as exc:
        print(exc)
        return 1

    def show(e: dict[str, Any]) -> None:
        if e["type"] == "verdict":
            print(f"\n[HypeCheck] round {e['round']}: paper claims {e['paper_strength']}")
            for s in e["sentences"]:
                print(f"  {'!!' if s['flagged'] else 'ok'} {s['p_overclaim']:.2f}  {s['strength']:<18} {s['sentence'][:90]}")
            print(f"[HypeCheck] -> {e['action']}", flush=True)
        elif e["type"] == "done":
            print(f"\n--- agent ---\n{e['agent_reply']}\n\n[HypeCheck] rounds={e['rounds']} "
                  f"decider_calls={e['decider_calls']} decider_ms={e['decider_ms']} llm_ms={e['llm_ms']}")

    run_hypecheck(args.draft.read_text(encoding="utf-8"), conclusion=args.conclusion, pmid=args.pmid,
                  emit=show, decider=decider, model=args.model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
