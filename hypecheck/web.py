"""HypeCheck web demo: paste a draft release and the paper, watch the gate and Claude work.

    uvicorn hypecheck.web:app --port 8080

Endpoints:
    POST /api/check   Decider only, no LLM: per-sentence verdicts in about a second.
    POST /api/run     starts the full agent; returns a job id.
    GET  /api/stream/{job}   server-sent events for that job.

Public deployments are guarded: one agent run at a time, a per-IP rate limit, and size caps,
because every run spends Bedrock tokens.
"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from decision_pattern.decider import Decider
from decision_pattern.fidelity import check_document, split_sentences
from decision_pattern.gate import load_threshold

from .agent import THRESHOLD_FILE, europepmc_conclusion, run_hypecheck, verdict_event

STATIC = Path(__file__).parent / "static"
MAX_CHARS = 4000
MAX_SENTENCES = 25
RUNS_PER_IP_PER_HOUR = 12

app = FastAPI(title="HypeCheck")
decider = Decider()
threshold = load_threshold(THRESHOLD_FILE, "0.1")
agent_lock = threading.Lock()
jobs: dict[str, queue.Queue] = {}
recent: dict[str, deque] = defaultdict(deque)


class CheckIn(BaseModel):
    draft: str = Field(..., max_length=MAX_CHARS)
    conclusion: str | None = Field(None, max_length=MAX_CHARS)
    pmid: str | None = Field(None, pattern=r"^\d{1,9}$")


def _validate(body: CheckIn) -> None:
    if not body.conclusion and not body.pmid:
        raise HTTPException(400, "give the paper's conclusion or a PubMed ID")
    if len(split_sentences(body.draft)) > MAX_SENTENCES:
        raise HTTPException(400, f"at most {MAX_SENTENCES} sentences")


def _rate_limit(ip: str) -> None:
    q, now = recent[ip], time.time()
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= RUNS_PER_IP_PER_HOUR:
        raise HTTPException(429, "rate limit: try again later")
    q.append(now)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"decider": decider.health(), "threshold": threshold}


@app.get("/api/examples")
def examples() -> list:
    return json.loads((STATIC / "examples.json").read_text(encoding="utf-8"))


@app.post("/api/check")
def check(body: CheckIn) -> dict:
    _validate(body)
    conclusion = body.conclusion or europepmc_conclusion(body.pmid)[1]
    t0 = time.perf_counter()
    calls0 = decider.calls
    verdict = check_document(decider, conclusion, body.draft)
    ev = verdict_event(verdict, "check", threshold, 0, body.draft)
    ev.update(conclusion=conclusion, ms=round((time.perf_counter() - t0) * 1000), decider_calls=decider.calls - calls0)
    return ev


@app.post("/api/run")
def run(body: CheckIn, request: Request) -> dict:
    _validate(body)
    _rate_limit(request.client.host if request.client else "?")
    if not agent_lock.acquire(blocking=False):
        raise HTTPException(429, "another run is in progress; try again in a minute")
    job = uuid.uuid4().hex
    q: queue.Queue = queue.Queue()
    jobs[job] = q

    def work() -> None:
        try:
            run_hypecheck(body.draft, conclusion=body.conclusion, pmid=body.pmid, emit=q.put, decider=decider,
                          threshold=threshold)
        except Exception as exc:  # surface to the page rather than hang it
            q.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            q.put(None)
            agent_lock.release()

    threading.Thread(target=work, daemon=True).start()
    return {"job": job}


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
