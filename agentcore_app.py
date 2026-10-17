"""HypeCheck on Amazon Bedrock AgentCore Runtime.

The same `run_hypecheck` agent, hosted serverlessly. It calls Strands Decider on the HypeCheck EC2
box through the key-guarded pass-through (`/decider/v1/systemone`); the key is read from SSM
Parameter Store at start-up, never from environment variables.

Payload: {"draft": "...", "conclusion": "..."} or {"draft": "...", "pmid": "12345678"}
Streams every event (paper, progress, verdict, published, done) as it happens.
"""

from __future__ import annotations

import asyncio
import os
import threading

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from decision_pattern.decider import Decider
from hypecheck.agent import run_hypecheck

DECIDER_URL = os.environ.get("HYPECHECK_DECIDER_URL", "https://d174bz5yly61n4.cloudfront.net/decider")
KEY_PARAM = os.environ.get("HYPECHECK_DECIDER_KEY_PARAM", "/hypecheck/decider-key")
REGION = os.environ.get("AWS_REGION", "us-east-1")

app = BedrockAgentCoreApp()
_key: str | None = None


def decider_key() -> str:
    global _key
    if _key is None:
        _key = boto3.client("ssm", region_name=REGION).get_parameter(
            Name=KEY_PARAM, WithDecryption=True)["Parameter"]["Value"]
    return _key


@app.entrypoint
async def invoke(payload: dict, context=None):
    draft = (payload or {}).get("draft", "").strip()
    if not draft or not (payload.get("conclusion") or payload.get("pmid")):
        yield {"type": "error", "message": "payload needs 'draft' and either 'conclusion' or 'pmid'"}
        return

    loop = asyncio.get_running_loop()
    events: asyncio.Queue = asyncio.Queue()
    emit = lambda e: loop.call_soon_threadsafe(events.put_nowait, e)  # noqa: E731

    def work() -> None:
        try:
            run_hypecheck(draft, conclusion=payload.get("conclusion"), pmid=payload.get("pmid"), emit=emit,
                          decider=Decider(url=DECIDER_URL, key=decider_key(), timeout=300))
        except Exception as exc:  # report, don't hang the stream
            emit({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            emit(None)

    threading.Thread(target=work, daemon=True).start()
    while (event := await events.get()) is not None:
        yield {**event, "host": "agentcore-runtime"}


if __name__ == "__main__":
    app.run()
