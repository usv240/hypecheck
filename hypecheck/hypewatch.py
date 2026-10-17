"""HypeWatch: HypeCheck run over real NIH news releases, against the papers they cite.

NIH news releases are works of the US government (public domain) and end with a reference to the
paper they report. For each release this:

1. fetches the release (one request per second, identified user agent, robots.txt-permitted pages);
2. finds the cited paper's conclusion from its abstract (Europe PMC, then OpenAlex, then Semantic
   Scholar);
3. has Strands Decider score the headline, subtitle and opening sentences against it;
4. asks Claude on Amazon Bedrock for a faithful rewrite of each blocked sentence, and has Decider
   check the rewrite.

Every flag is the model's reading, shown next to the paper's own words so a reader can judge.

    python -m hypecheck.hypewatch backfill --pages 30          # the archive, newest first
    python -m hypecheck.hypewatch update                        # new items from the RSS feed
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config

from decision_pattern.decider import Decider
from decision_pattern.fidelity import check_document, split_sentences, strength, overclaim_probability, STRENGTH

from .agent import thresholds
from decision_pattern.gate import zone

BASE = "https://www.nih.gov"
FEED = f"{BASE}/news-releases/feed.xml"
LISTING = f"{BASE}/news-events/news-releases?page={{}}"
UA = "HypeCheck/1.0 (research; https://github.com/usv240/hypecheck)"
DATA = Path(os.environ.get("HYPEWATCH_DATA", Path(__file__).resolve().parent / "hypewatch.json"))
MODEL = os.environ.get("HYPECHECK_MODEL", "us.anthropic.claude-sonnet-4-6")
LEDE_SENTENCES = 6
_last_fetch = 0.0


def get(url: str, polite: bool = True) -> str:
    global _last_fetch
    if polite:
        wait = 1.0 - (time.monotonic() - _last_fetch)
        if wait > 0:
            time.sleep(wait)
        _last_fetch = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", errors="replace")


def text_of(fragment: str) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", " ", fragment))
    return re.sub(r"\s+", " ", t.replace(" ", " ").replace(" ", " ")).strip()


# ----------------------------------------------------------------------------- releases

def listing_urls(page: int) -> list[str]:
    s = get(LISTING.format(page))
    seen, out = set(), []
    for path in re.findall(r'href="(/news-events/news-releases/[a-z0-9\-]+)"', s):
        if path not in seen:
            seen.add(path)
            out.append(BASE + path)
    return out


def feed_urls() -> list[str]:
    root = ET.fromstring(get(FEED))
    return [it.findtext("link").strip() for it in root.findall(".//item") if it.findtext("link")]


def parse_release(url: str) -> dict[str, Any] | None:
    s = get(url)
    a = s.find("<article")
    if a < 0:
        return None
    art = s[a:]
    title = text_of(re.search(r"<h1[^>]*>(.*?)</h1>", art, re.S).group(1)) if re.search(r"<h1", art) else ""
    date = text_of(m.group(1)) if (m := re.search(r'class="nih-pretitle"[^>]*>(.*?)</p>', art, re.S)) else ""
    subtitle = text_of(m.group(1)) if (m := re.search(r'class="nih-subtitle"[^>]*>(.*?)</p>', art, re.S)) else ""
    body = []
    for attrs, p in re.findall(r"<p(\s[^>]*)?>(.*?)</p>", art, re.S):
        if "nih-pretitle" in (attrs or "") or "nih-subtitle" in (attrs or ""):
            continue
        t = text_of(p)
        if not t:
            continue
        if re.match(r"^(NIH (supported|funded)|About the|This (study|research|work) was (supported|funded)|NIH…|NIH\.\.\.)", t):
            break
        body.append(t)
    ref = s[s.find("Reference"):] if "Reference" in s else ""
    doi = m.group(0).rstrip(".") if (m := re.search(r"10\.\d{4,9}/[^\s\"<>&]+", ref)) else None
    institute = text_of(m.group(1)) if (m := re.search(r"Institute/Center</[^>]+>\s*(?:<[^>]+>\s*)*([^<]{3,160})", s)) else ""
    return {"url": url, "title": title, "subtitle": subtitle, "date": date, "body": body, "doi": doi,
            "institute": institute}


# ----------------------------------------------------------------------------- papers

def _conclusion_from_abstract(abstract: str) -> str:
    abstract = text_of(abstract)
    heads = list(re.finditer(r"(?:^|(?<=[.\s]))(?:CONCLUSIONS?(?: AND RELEVANCE)?|INTERPRETATION|Conclusions?(?: and [Rr]elevance)?|Interpretation)\s*[:.]?\s+(?=[A-Z])", abstract))
    if heads:
        return abstract[heads[-1].end():].strip()
    sents = split_sentences(abstract)
    return " ".join(sents[-2:]) if sents else ""


def _with_abstract(title: str, abstract: str, source: str) -> tuple[str, str, str, str]:
    return title, _conclusion_from_abstract(abstract), source, text_of(abstract)


def paper_conclusion(doi: str) -> tuple[str, str, str, str] | None:
    """(title, conclusion, source, full abstract) for a DOI, or None if no abstract is found."""
    q = urllib.parse.quote(f'DOI:"{doi}"')
    try:
        hits = json.loads(get(f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={q}&resultType=core&format=json",
                              polite=False))["resultList"]["result"]
        if hits and hits[0].get("abstractText"):
            return _with_abstract(hits[0].get("title", ""), hits[0]["abstractText"], "Europe PMC")
    except Exception:
        pass
    try:
        w = json.loads(get(f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi)}", polite=False))
        if ii := w.get("abstract_inverted_index"):
            words = sorted((p, t) for t, ps in ii.items() for p in ps)
            return _with_abstract(w.get("title", ""), " ".join(t for _, t in words), "OpenAlex")
    except Exception:
        pass
    try:
        p = json.loads(get(f"https://api.semanticscholar.org/graph/v1/paper/DOI:{urllib.parse.quote(doi)}?fields=title,abstract",
                           polite=False))
        if p.get("abstract"):
            return _with_abstract(p.get("title", ""), p["abstract"], "Semantic Scholar")
    except Exception:
        pass
    return None


# ----------------------------------------------------------------------------- checking

REWRITE_PROMPT = (
    "A sentence from a health press release claims more than the paper it reports. Rewrite the sentence "
    "so it claims no more than the paper's conclusion supports: keep its topic and plain-language style, "
    "use association language for correlational findings and hedged language for tentative ones, and do "
    "not add facts. Reply with the rewritten sentence only.\n\nPAPER'S CONCLUSION: {paper}\n\nSENTENCE: {sentence}"
)


def suggest(bedrock, decider: Decider, paper: str, p_paper: list[float], sentence: str, threshold: float) -> dict:
    """Claude proposes a rewrite; Decider checks it. Up to two attempts."""
    feedback = ""
    for attempt in (1, 2):
        resp = bedrock.converse(
            modelId=MODEL,
            messages=[{"role": "user", "content": [{"text": REWRITE_PROMPT.format(paper=paper, sentence=sentence) + feedback}]}],
            inferenceConfig={"maxTokens": 200, "temperature": 0})
        text = "".join(b.get("text", "") for b in resp["output"]["message"]["content"]).strip().strip('"')
        text = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"", text)  # plain text, no markdown emphasis
        p = overclaim_probability(strength(decider, text), p_paper)
        if p <= threshold:
            return {"suggestion": text, "suggestion_p": round(p, 4), "suggestion_ok": True, "attempts": attempt}
        feedback = f"\n\nYour previous rewrite still overclaims: \"{text}\". Hedge it further."
    return {"suggestion": text, "suggestion_p": round(p, 4), "suggestion_ok": False, "attempts": 2}


def iso_date(d: str) -> str:
    """'Wednesday, October 14, 2026' -> '2026-10-14'; tolerates prefixes such as 'Media Advisory'."""
    m = re.search(r"[A-Z][a-z]+day, [A-Z][a-z]+ \d{1,2}, \d{4}", d or "")
    try:
        return datetime.strptime(m.group(0), "%A, %B %d, %Y").date().isoformat() if m else ""
    except ValueError:
        return ""


def check_release(rel: dict, paper: tuple[str, str, str], decider: Decider, bedrock, thr: float, rev: float) -> dict:
    lede, seen = [], {rel["title"].strip(" ."), rel["subtitle"].strip(" .")}
    for para in rel["body"]:
        for sent in split_sentences(para):
            if sent.strip(" .") not in seen:   # releases often repeat the subtitle as the first line
                seen.add(sent.strip(" ."))
                lede.append(sent)
        if len(lede) >= LEDE_SENTENCES:
            break
    parts = [("headline", rel["title"])] + ([("subtitle", rel["subtitle"])] if rel["subtitle"] else [])
    parts += [("quote" if re.search(r"[“\"]", s) else "body", s) for s in lede[:LEDE_SENTENCES]]
    roles = [r for r, _ in parts]
    # Headlines and subtitles rarely end in a full stop; add one so the splitter keeps them whole.
    derived = " ".join(t if t.rstrip().endswith((".", "!", "?")) else t.rstrip() + "." for _, t in parts)
    verdict = check_document(decider, paper[1], derived)
    # Public flags on real releases get a stricter rule than the benchmark: a sentence must claim more
    # than the conclusion AND more than the strongest claim anywhere in the abstract (e.g. an animal
    # result stated earlier). Taking the minimum can only remove flags, so the calibrated false-flag
    # rate stays an upper bound.
    abstract_levels = [strength(decider, a) for a in split_sentences(paper[3])[:14]] or [verdict.p_source]
    expected = lambda p: sum(i * x for i, x in enumerate(p))  # noqa: E731
    p_strongest = max(abstract_levels, key=expected)
    sents = verdict.sentences
    out = []
    for i, s in enumerate(sents):
        p_vs_abstract = overclaim_probability(s.p_strength, p_strongest)
        p = min(s.p_overclaim, p_vs_abstract)
        z = zone(p, thr, rev)
        item = {"text": s.sentence, "role": roles[i] if i < len(roles) else "body", "strength": s.strength,
                "p": round(p, 4), "p_vs_conclusion": round(s.p_overclaim, 4),
                "p_vs_abstract": round(p_vs_abstract, 4), "zone": z}
        if z == "block" and bedrock is not None:
            item.update(suggest(bedrock, decider, paper[1], verdict.p_source, s.sentence, thr))
        out.append(item)
    return {
        "url": rel["url"], "title": rel["title"], "date": rel["date"], "date_iso": iso_date(rel["date"]),
        "institute": rel["institute"],
        "doi": rel["doi"], "paper_title": paper[0], "paper_conclusion": paper[1], "conclusion_source": paper[2],
        "paper_strength": verdict.source_strength,
        "abstract_strongest": STRENGTH[p_strongest.index(max(p_strongest))], "sentences": out, "advisory": verdict.advisory,
        "max_p": round(max((s["p"] for s in out), default=0.0), 4),
        "flagged": sum(s["zone"] == "block" for s in out), "review": sum(s["zone"] == "review" for s in out),
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# ----------------------------------------------------------------------------- summary

def summarize(store: dict, threshold: float, review_threshold: float) -> dict:
    """The numbers the page, the article and the pre-registration report, from one place."""
    rel = store["releases"]
    sents = [s for r in rel for s in r["sentences"]]
    heads = [s for s in sents if s["role"] == "headline"]
    body = [s for s in sents if s["role"] != "headline"]
    sugg = [s for s in sents if "suggestion_ok" in s]
    skipped = store.get("skipped", {}).values()

    def share(xs, f):
        return round(sum(map(f, xs)) / len(xs), 4) if xs else None

    def mean(xs, key):
        return round(sum(x[key] for x in xs) / len(xs), 4) if xs else None

    return {
        "releases": len(rel), "sentences": len(sents),
        "skipped_no_paper": sum("no paper" in v for v in skipped),
        "skipped_no_abstract": sum("abstract" in v for v in skipped),
        "releases_with_block": share(rel, lambda r: r["flagged"] > 0),
        "releases_with_block_benchmark_rule": share(rel, lambda r: any(s["p_vs_conclusion"] > threshold for s in r["sentences"])),
        "releases_with_review": share(rel, lambda r: r["review"] > 0),
        "headline_block_rate": share(heads, lambda s: s["zone"] == "block"),
        "body_block_rate": share(body, lambda s: s["zone"] == "block"),
        "headline_mean_p": mean(heads, "p"), "body_mean_p": mean(body, "p"),
        "headline_mean_p_benchmark_rule": mean(heads, "p_vs_conclusion"),
        "body_mean_p_benchmark_rule": mean(body, "p_vs_conclusion"),
        "rewrites": len(sugg), "rewrites_verified": share(sugg, lambda s: s["suggestion_ok"]),
        "rewrites_first_try": share(sugg, lambda s: s["suggestion_ok"] and s["attempts"] == 1),
        "first_date": min((r["date_iso"] for r in rel if r.get("date_iso")), default=None),
        "last_date": max((r["date_iso"] for r in rel if r.get("date_iso")), default=None),
        "updated": store.get("updated"), "threshold": threshold, "review_threshold": review_threshold,
    }


# ----------------------------------------------------------------------------- store

def load() -> dict:
    if DATA.exists():
        return json.loads(DATA.read_text(encoding="utf-8"))
    return {"releases": [], "skipped": {}}


def save(store: dict) -> None:
    store["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    tmp = DATA.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(DATA)


def process(urls: list[str], store: dict, rewrite: bool = True, log=print) -> int:
    known = {r["url"] for r in store["releases"]} | set(store["skipped"])
    decider = Decider(timeout=300)
    thr, rev = thresholds()
    bedrock = boto3.client("bedrock-runtime", region_name="us-east-1",
                           config=Config(retries={"max_attempts": 8, "mode": "adaptive"})) if rewrite else None
    added = 0
    for url in urls:
        if url in known:
            continue
        try:
            rel = parse_release(url)
        except Exception as exc:
            store["skipped"][url] = f"fetch failed: {type(exc).__name__}"
            continue
        if not rel or not rel["doi"]:
            store["skipped"][url] = "no paper reference (announcement, not a study)"
            continue
        paper = paper_conclusion(rel["doi"])
        if not paper or len(paper[1]) < 30 or len(paper[3]) < 200:
            store["skipped"][url] = "paper abstract not available yet"
            continue
        try:
            rec = check_release(rel, paper, decider, bedrock, thr, rev)
        except Exception as exc:  # e.g. Decider restarting; leave it for the next run, don't crash the job
            log(f"check failed, will retry next run: {type(exc).__name__}: {rel['title'][:60]}")
            continue
        store["releases"].append(rec)
        added += 1
        log(f"[{added}] {rec['flagged']} block / {rec['review']} review  max {rec['max_p']:.2f}  {rec['title'][:80]}")
        if added % 5 == 0:
            save(store)
    store["releases"].sort(key=lambda r: r.get("date_iso") or "", reverse=True)
    save(store)
    return added


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backfill")
    b.add_argument("--pages", type=int, default=30)
    b.add_argument("--start", type=int, default=0)
    sub.add_parser("update")
    sub.add_parser("summary")
    ap.add_argument("--no-rewrite", action="store_true")
    args = ap.parse_args()
    store = load()
    if args.cmd == "summary":
        print(json.dumps(summarize(store, *thresholds()), indent=1))
        return 0
    if args.cmd == "backfill":
        urls = []
        for page in range(args.start, args.start + args.pages):
            urls += listing_urls(page)
    else:
        urls = feed_urls()
    n = process(urls, store, rewrite=not args.no_rewrite)
    print(f"added {n}; total {len(store['releases'])}; skipped {len(store['skipped'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
