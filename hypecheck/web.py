"""HypeCheck web demo: paste a draft release and the paper, watch the gate and Claude work.

    uvicorn hypecheck.web:app --port 8080

Endpoints:
    POST /api/check   Decider only, no LLM. Returns a job id.
    POST /api/run     the full agent (Decider + Claude on Bedrock). Returns a job id.
    GET  /api/stream/{job}   server-sent events for that job, including its queue position.
    GET  /api/evidence       the measured numbers, read from research/results (one source of truth).
    POST /decider/v1/systemone   key-guarded pass-through to the local Decider, used by the
                                 copy of the agent hosted on Amazon Bedrock AgentCore Runtime.

Jobs run one at a time in arrival order (Decider is a single local model), and a waiting job
reports its place in the queue instead of being turned away. Size caps and a per-IP rate limit
protect the Bedrock budget on a public URL.
"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
import urllib.request
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from decision_pattern.decider import Decider
from decision_pattern.fidelity import check_document, split_sentences

from .agentcore_client import stream_events as agentcore_events
from .hypewatch import summarize
from .agent import ROOT, europepmc_conclusion, run_hypecheck, sentence_dict, thresholds, verdict_event

STATIC = Path(__file__).parent / "static"
RESULTS = ROOT / "research" / "results"
MAX_CHARS = 4000
MAX_SENTENCES = 25
RUNS_PER_IP_PER_HOUR = 20
DECIDER_KEY = os.environ.get("HYPECHECK_DECIDER_KEY", "")

app = FastAPI(title="HypeCheck")
decider = Decider()
threshold, review_threshold = thresholds()

work: queue.Queue = queue.Queue()
jobs: dict[str, queue.Queue] = {}
waiting: deque = deque()
waiting_lock = threading.Lock()
recent: dict[str, deque] = defaultdict(deque)


class CheckIn(BaseModel):
    draft: str = Field(..., max_length=MAX_CHARS)
    engine: Literal["agentcore", "local"] = "agentcore"
    conclusion: str | None = Field(None, max_length=MAX_CHARS)
    pmid: str | None = Field(None, pattern=r"^\d{1,9}$")


def client_ip(request: Request) -> str:
    # Behind CloudFront every request arrives from an edge address; the viewer is first in the chain.
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")


def _validate(body: CheckIn) -> None:
    if not body.draft.strip():
        raise HTTPException(400, "paste a draft press release first")
    if not (body.conclusion or "").strip() and not body.pmid:
        raise HTTPException(400, "give the paper's conclusion, or a PubMed ID so it can be fetched")
    if len(split_sentences(body.draft)) > MAX_SENTENCES:
        raise HTTPException(400, f"at most {MAX_SENTENCES} sentences per check")


def _rate_limit(ip: str) -> None:
    q, now = recent[ip], time.time()
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= RUNS_PER_IP_PER_HOUR:
        raise HTTPException(429, "rate limit reached for this hour; the 'Check with Decider only' button still works")
    q.append(now)


def _check_job(body: CheckIn, emit) -> None:
    conclusion = (body.conclusion or "").strip()
    if not conclusion:
        title, conclusion = europepmc_conclusion(body.pmid)
        emit({"type": "paper", "pmid": body.pmid, "title": title, "conclusion": conclusion})
    else:
        emit({"type": "paper", "pmid": None, "title": "", "conclusion": conclusion})
    emit({"type": "round_start", "round": 0, "text": body.draft})
    t0, calls0 = time.perf_counter(), decider.calls
    verdict = check_document(
        decider, conclusion, body.draft,
        on_sentence=lambda i, n, s: emit({"type": "progress", "round": 0, "index": i, "total": n,
                                          **sentence_dict(s, threshold, review_threshold)}))
    ev = verdict_event(verdict, "check", threshold, 0, body.draft, review_threshold)
    emit(ev)
    emit({"type": "done", "mode": "check", "decider_calls": decider.calls - calls0,
          "decider_ms": round((time.perf_counter() - t0) * 1000), "llm_ms": 0, "rounds": 0,
          "published": False, "review": [s["sentence"] for s in ev["sentences"] if s["zone"] == "review"]})


def _agentcore_job(body: CheckIn, emit) -> None:
    """Run on the AgentCore-hosted copy; fall back to this box if AgentCore fails before any event."""
    payload = {"draft": body.draft, **({"pmid": body.pmid} if body.pmid else {"conclusion": body.conclusion})}
    got_any = False
    try:
        emit({"type": "host", "host": "agentcore-runtime"})
        for e in agentcore_events(payload):
            got_any = True
            emit(e)
    except Exception as exc:
        if got_any:
            raise
        emit({"type": "host", "host": "local", "note": f"AgentCore unavailable ({type(exc).__name__}); ran on the demo server instead"})
        run_hypecheck(body.draft, conclusion=body.conclusion, pmid=body.pmid, emit=emit,
                      decider=decider, threshold=threshold, review_threshold=review_threshold)


def _worker() -> None:
    while True:
        job, kind, body = work.get()
        q = jobs.get(job)
        with waiting_lock:
            if job in waiting:
                waiting.remove(job)
            for pos, other in enumerate(waiting, start=1):
                if other in jobs:
                    jobs[other].put({"type": "queued", "position": pos})
        if q is None:
            continue
        q.put({"type": "started", "mode": kind})
        try:
            if kind == "check":
                _check_job(body, q.put)
            elif body.engine == "agentcore":
                _agentcore_job(body, q.put)
            else:
                run_hypecheck(body.draft, conclusion=body.conclusion, pmid=body.pmid, emit=q.put,
                              decider=decider, threshold=threshold, review_threshold=review_threshold)
        except Exception as exc:  # surface to the page rather than hang it
            q.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            q.put(None)


threading.Thread(target=_worker, daemon=True).start()


def _enqueue(kind: str, body: CheckIn) -> dict[str, Any]:
    job = uuid.uuid4().hex
    jobs[job] = queue.Queue()
    with waiting_lock:
        waiting.append(job)
        position = len(waiting)
    jobs[job].put({"type": "queued", "position": position})
    work.put((job, kind, body))
    return {"job": job, "position": position}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


HYPEWATCH = Path(os.environ.get("HYPEWATCH_DATA", Path(__file__).resolve().parent / "hypewatch.json"))


@app.get("/hypewatch")
def hypewatch_page() -> FileResponse:
    return FileResponse(STATIC / "hypewatch.html")


@app.get("/api/hypewatch")
def hypewatch_data() -> dict:
    """Releases checked so far, plus summary numbers computed here so the page and article agree."""
    if not HYPEWATCH.exists():
        return {"releases": [], "summary": {}}
    store = json.loads(HYPEWATCH.read_text(encoding="utf-8"))
    return {"summary": summarize(store, threshold, review_threshold), "releases": store["releases"]}


@app.get("/architecture.svg")
def architecture() -> FileResponse:
    return FileResponse(STATIC / "architecture.svg", media_type="image/svg+xml")


@app.get("/favicon.svg")
def favicon() -> FileResponse:
    return FileResponse(STATIC / "favicon.svg", media_type="image/svg+xml")


@app.get("/api/health")
def health() -> dict:
    return {"decider": decider.health(), "threshold": threshold, "review_threshold": review_threshold,
            "queue": len(waiting)}


@app.get("/api/examples")
def examples() -> list:
    return json.loads((STATIC / "examples.json").read_text(encoding="utf-8"))


@app.get("/api/evidence")
def evidence() -> dict:
    """The site's numbers come from the same files the article cites."""
    def load(p: str) -> Any:
        f = RESULTS / p
        return json.loads(f.read_text()) if f.exists() else None
    return {"spike": load("spike-v1/summary.json"), "calibration": load("calibration/summary.json"),
            "insciout": load("insciout/summary.json"), "haiku": load("baseline-haiku45/summary.json"),
            "sonnet": load("baseline-sonnet-4-6/summary.json"), "opus": load("baseline-opus-4-6/summary.json")}


@app.post("/api/check")
def check(body: CheckIn) -> dict:
    _validate(body)
    return _enqueue("check", body)


@app.post("/api/run")
def run(body: CheckIn, request: Request) -> dict:
    _validate(body)
    _rate_limit(client_ip(request))
    return _enqueue("run", body)


@app.get("/api/stream/{job}")
def stream(job: str) -> StreamingResponse:
    q = jobs.get(job)
    if q is None:
        raise HTTPException(404, "unknown job")

    def events():
        while True:
            try:
                item = q.get(timeout=15)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue
            if item is None:
                jobs.pop(job, None)
                yield "event: end\ndata: {}\n\n"
                return
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/decider/v1/systemone")
async def decider_proxy(request: Request) -> Response:
    """Pass-through for the AgentCore-hosted agent. Disabled unless HYPECHECK_DECIDER_KEY is set."""
    if not DECIDER_KEY or request.headers.get("x-hypecheck-key") != DECIDER_KEY:
        return JSONResponse({"detail": "forbidden"}, status_code=403)
    body = await request.body()
    if len(body) > 64_000:
        return JSONResponse({"detail": "too large"}, status_code=413)
    req = urllib.request.Request(f"{decider.url}/v1/systemone", body, {"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return Response(r.read(), media_type="application/json")
