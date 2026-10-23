"""HypeCheck public API (v1) and MCP connector, for other builders' apps and agents.

    POST /v1/keys        issue a key instantly (no signup, nothing personal stored)
    POST /v1/check       Decider-only claim-fidelity check, free (300/day/key)
    POST /v1/rewrite     check + Claude rewrites of blocked sentences, each re-checked by Decider (20/day/key)
    POST /v1/calibrate   bring your own labelled pairs -> a conformal threshold with a stated false-flag rate
    GET  /v1/jobs/{id}   result of a calibration job
    GET  /v1/usage       today's usage for your key
    /mcp                 the same check and rewrite as MCP tools (streamable HTTP, same key)

Every call takes `Authorization: Bearer hc_...` (or `X-API-Key`).
"""

from __future__ import annotations

import contextvars
import threading
import time
import uuid
from typing import Any, Literal

import boto3
from botocore.config import Config
from fastapi import APIRouter, Header, HTTPException, Request
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field

from decision_pattern.calibrate import conformal_threshold
from decision_pattern.decider import Decider
from decision_pattern.fidelity import STRENGTH, check_document, overclaim_probability, split_sentences, strength
from decision_pattern.gate import zone
from decision_pattern.receipt import build_receipt, verify_receipt

from .apikeys import KeyStore, LimitExceeded
from .hypewatch import suggest

MAX_CHARS = 6000
MAX_CHECK_SENTENCES = 25
MAX_REWRITE_SENTENCES = 12
CAL_MIN, CAL_MAX = 10, 60


class Engine:
    """Shared state the web app hands over: the Decider client and the calibrated thresholds."""

    def __init__(self, decider: Decider, threshold: float, review_threshold: float) -> None:
        self.decider = decider
        self.threshold = threshold
        self.review_threshold = review_threshold
        self.keys = KeyStore()
        self.bedrock = boto3.client("bedrock-runtime", region_name="us-east-1",
                                    config=Config(retries={"max_attempts": 6, "mode": "adaptive"}))
        self.jobs: dict[str, dict[str, Any]] = {}

    # ---- the three operations, shared by REST and MCP --------------------------------------

    def check(self, source: str, text: str) -> dict[str, Any]:
        if len(split_sentences(text)) > MAX_CHECK_SENTENCES:
            raise LimitExceeded(f"at most {MAX_CHECK_SENTENCES} sentences per check", 400)
        t0, calls0 = time.perf_counter(), self.decider.calls
        v = check_document(self.decider, source, text)
        sents = [{"sentence": s.sentence, "strength": s.strength, "overclaim": round(s.p_overclaim, 4),
                  "zone": zone(s.p_overclaim, self.threshold, self.review_threshold)} for s in v.sentences]
        receipt = build_receipt(v, source=source, derived=text, threshold=self.threshold,
                                review_threshold=self.review_threshold, zones=[s["zone"] for s in sents],
                                model="strands-decider-2B-qwen3.5-v1-2610")
        return {
            "receipt": receipt,
            "source_strength": v.source_strength,
            "verdict": "block" if any(s["zone"] == "block" for s in sents) else "review" if any(s["zone"] == "review" for s in sents) else "ok",
            "sentences": sents,
            "hints": {k: v.advisory.get(k) for k in ("advice_inflated", "animal_to_human")},
            "thresholds": {"block": self.threshold, "review": self.review_threshold,
                           "basis": "split conformal, alpha 0.10 / 0.20, fitted on expert-labelled press-release pairs"},
            "decider": {"model": "strands-decider-2B-qwen3.5-v1-2610", "calls": self.decider.calls - calls0,
                        "ms": round((time.perf_counter() - t0) * 1000)},
        }

    def rewrite(self, source: str, text: str) -> tuple[dict[str, Any], dict[str, int]]:
        if len(split_sentences(text)) > MAX_REWRITE_SENTENCES:
            raise LimitExceeded(f"at most {MAX_REWRITE_SENTENCES} sentences per rewrite", 400)
        result = self.check(source, text)
        p_source = strength(self.decider, source)
        usage: dict[str, int] = {}
        out = []
        for s in result["sentences"]:
            item = dict(s)
            if s["zone"] == "block":
                item.update(suggest(self.bedrock, self.decider, source, p_source, s["sentence"], self.threshold, usage))
            out.append(item)
        result["sentences"] = out
        result["rewritten_text"] = " ".join(x.get("suggestion") if x.get("suggestion_ok") else x["sentence"] for x in out)
        result["unresolved"] = [x["sentence"] for x in out if x["zone"] == "block" and not x.get("suggestion_ok")]
        return result, usage

    def start_calibration(self, pairs: list[dict[str, str]], alpha: float) -> str:
        job = uuid.uuid4().hex
        self.jobs[job] = {"status": "running", "pairs": len(pairs), "alpha": alpha, "started": time.time()}

        def work() -> None:
            try:
                scored = []
                for p in pairs:
                    sc = overclaim_probability(strength(self.decider, p["derived"]), strength(self.decider, p["source"]))
                    scored.append((sc, p["label"]))
                faithful = [sc for sc, lab in scored if lab == "faithful"]
                over = [sc for sc, lab in scored if lab == "overclaim"]
                tau = conformal_threshold(faithful, alpha)
                in_sample_ff = sum(sc > tau for sc in faithful) / len(faithful)
                self.jobs[job].update(status="done", result={
                    "threshold": round(tau, 4), "alpha": alpha, "n_faithful": len(faithful), "n_overclaim": len(over),
                    "guarantee": f"if new pairs resemble these, at most {alpha:.0%} of faithful sentences are flagged",
                    "in_sample_false_flag": round(in_sample_ff, 4),
                    "in_sample_recall": round(sum(sc > tau for sc in over) / len(over), 4) if over else None,
                    "use_it": "pass this as `threshold` to ClaimFidelityGate (decision_pattern/README.md)",
                    "scores": [{"overclaim": round(sc, 4), "label": lab} for sc, lab in scored]})
            except Exception as exc:
                self.jobs[job].update(status="error", error=f"{type(exc).__name__}: {exc}")

        threading.Thread(target=work, daemon=True).start()
        return job


engine: Engine | None = None
router = APIRouter(prefix="/v1", tags=["public API"])


def _key(authorization: str | None, x_api_key: str | None) -> str:
    raw = x_api_key or (authorization[7:] if authorization and authorization.lower().startswith("bearer ") else None)
    try:
        return engine.keys.verify(raw)
    except LimitExceeded as exc:
        raise HTTPException(exc.status, str(exc)) from None


def _spend(kid: str, action: str) -> None:
    try:
        engine.keys.spend(kid, action)
    except LimitExceeded as exc:
        raise HTTPException(exc.status, str(exc)) from None


class TextIn(BaseModel):
    source: str = Field(..., min_length=10, max_length=MAX_CHARS,
                        description="What the text must not exceed, e.g. the paper's conclusion")
    text: str = Field(..., min_length=3, max_length=MAX_CHARS, description="The derived text to check")


class ReceiptIn(BaseModel):
    receipt: dict = Field(..., description="A receipt returned by /v1/check, /v1/rewrite, the agent, or an outbox file")


class Pair(BaseModel):
    source: str = Field(..., max_length=2000)
    derived: str = Field(..., max_length=2000)
    label: Literal["faithful", "overclaim"]


class CalibrateIn(BaseModel):
    pairs: list[Pair] = Field(..., min_length=CAL_MIN, max_length=CAL_MAX)
    alpha: float = Field(0.10, ge=0.05, le=0.5, description="largest share of faithful sentences you accept being flagged")


@router.post("/keys", summary="Get an API key (instant, no signup)")
def new_key(request: Request) -> dict:
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() or (request.client.host if request.client else "?")
    try:
        key = engine.keys.issue(ip)
    except LimitExceeded as exc:
        raise HTTPException(exc.status, str(exc)) from None
    return {"api_key": key, "shown_once": True, "limits": engine.keys.usage(engine.keys.verify(key))["limits"],
            "docs": "/developers"}


@router.post("/check", summary="Check text against its source (Decider only, free)")
def v1_check(body: TextIn, authorization: str | None = Header(None), x_api_key: str | None = Header(None)) -> dict:
    kid = _key(authorization, x_api_key)
    _spend(kid, "check")
    try:
        return engine.check(body.source, body.text)
    except LimitExceeded as exc:
        raise HTTPException(exc.status, str(exc)) from None


@router.post("/rewrite", summary="Check, then have Claude rewrite blocked sentences; Decider verifies each rewrite")
def v1_rewrite(body: TextIn, authorization: str | None = Header(None), x_api_key: str | None = Header(None)) -> dict:
    kid = _key(authorization, x_api_key)
    _spend(kid, "rewrite")
    try:
        result, usage = engine.rewrite(body.source, body.text)
    except LimitExceeded as exc:
        raise HTTPException(exc.status, str(exc)) from None
    cost = engine.keys.add_cost(usage.get("input_tokens", 0), usage.get("output_tokens", 0))
    result["claude"] = {"model": "us.anthropic.claude-sonnet-4-6", **usage, "cost_usd": round(cost, 5)}
    return result


@router.post("/verify", summary="Verify a decision receipt without a model (no key needed)")
def v1_verify(body: ReceiptIn) -> dict:
    """Recomputes the hash, every overclaim score and every zone from the receipt's own rung probabilities."""
    try:
        return verify_receipt(body.receipt)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(400, f"not a HypeCheck receipt: {exc}") from None


@router.post("/calibrate", status_code=202, summary="Bring your own labelled pairs; get a conformal threshold")
def v1_calibrate(body: CalibrateIn, authorization: str | None = Header(None), x_api_key: str | None = Header(None)) -> dict:
    kid = _key(authorization, x_api_key)
    faithful = sum(p.label == "faithful" for p in body.pairs)
    need = int(1 / body.alpha)  # ceil((n+1)(1-a)) <= n needs n >= 1/a - 1
    if faithful < need:
        raise HTTPException(400, f"alpha {body.alpha} needs at least {need} faithful pairs; got {faithful}")
    _spend(kid, "calibrate")
    job = engine.start_calibration([p.model_dump() for p in body.pairs], body.alpha)
    return {"job": job, "poll": f"/v1/jobs/{job}", "eta_seconds": len(body.pairs) * 2}


@router.get("/jobs/{job}", summary="Result of a calibration job")
def v1_job(job: str, authorization: str | None = Header(None), x_api_key: str | None = Header(None)) -> dict:
    _key(authorization, x_api_key)
    if job not in engine.jobs:
        raise HTTPException(404, "unknown job")
    return engine.jobs[job]


@router.get("/usage", summary="Today's usage and limits for your key")
def v1_usage(authorization: str | None = Header(None), x_api_key: str | None = Header(None)) -> dict:
    return engine.keys.usage(_key(authorization, x_api_key))


# ---------------------------------------------------------------------------------- MCP

current_key: contextvars.ContextVar[str] = contextvars.ContextVar("hypecheck_key")
mcp = MCPServer(
    name="hypecheck",
    title="HypeCheck claim-fidelity gate",
    instructions="Use check_claims before publishing text derived from a source (summaries, press releases, "
                 "patient leaflets, RAG answers). Sentences in zone 'block' claim more than the source; use "
                 "suggest_rewrites to get Decider-verified fixes.",
    website_url="https://d174bz5yly61n4.cloudfront.net/developers",
)


def _mcp_spend(action: str) -> None:
    engine.keys.spend(current_key.get(), action)


@mcp.tool(description="Check every sentence of `text` against `source` (e.g. a paper's conclusion). Returns each "
                      "sentence's claim strength, overclaim probability and zone (block / review / ok). Free.")
def check_claims(source: str, text: str) -> dict:
    _mcp_spend("check")
    return engine.check(source, text)


@mcp.tool(description="Verify a HypeCheck decision receipt offline: recomputes its hash, overclaim scores and zones "
                      "from the rung probabilities it carries. Free, no model.")
def verify_decision_receipt(receipt: dict) -> dict:
    return verify_receipt(receipt)


@mcp.tool(description="Like check_claims, then Claude on Amazon Bedrock rewrites each blocked sentence so it claims "
                      "no more than the source, and Strands Decider re-checks every rewrite. Limited per day.")
def suggest_rewrites(source: str, text: str) -> dict:
    _mcp_spend("rewrite")
    result, usage = engine.rewrite(source, text)
    result["claude"] = {**usage, "cost_usd": round(engine.keys.add_cost(usage.get("input_tokens", 0),
                                                                        usage.get("output_tokens", 0)), 5)}
    return result


mcp_app = mcp.streamable_http_app(streamable_http_path="/", stateless_http=True, json_response=True,
                                  transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))


class MCPGateway:
    """ASGI wrapper: requires a valid key on /mcp, then hands the request to the MCP app."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and (scope["path"] == "/mcp" or scope["path"].startswith("/mcp/")):
            headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            auth = headers.get("authorization", "")
            raw = headers.get("x-api-key") or (auth[7:] if auth.lower().startswith("bearer ") else None)
            try:
                kid = engine.keys.verify(raw)
            except LimitExceeded as exc:
                body = ('{"error":"%s"}' % str(exc).replace('"', "'")).encode()
                await send({"type": "http.response.start", "status": exc.status,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": body})
                return
            token = current_key.set(kid)
            try:
                sub = dict(scope, path="/" + scope["path"][len("/mcp"):].lstrip("/"), root_path=scope.get("root_path", "") + "/mcp")
                await mcp_app(sub, receive, send)
            finally:
                current_key.reset(token)
            return
        await self.app(scope, receive, send)


def lifespan_context():
    """The MCP app's session manager must run for the server's lifetime."""
    return mcp_app.router.lifespan_context(mcp_app)


__all__ = ["Engine", "router", "MCPGateway", "lifespan_context", "STRENGTH"]
