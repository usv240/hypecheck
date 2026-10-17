"""Client for the copy of HypeCheck hosted on Amazon Bedrock AgentCore Runtime.

Used by the web app (engine="agentcore") and runnable on its own:

    python -m hypecheck.agentcore_client --draft examples/referral_release.txt \
        --conclusion "Use of the urgent referral pathway could be efficacious."
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

import boto3
from botocore.config import Config

HERE = Path(__file__).resolve().parent


def stream_events(payload: dict, arn: str | None = None, region: str = "us-east-1") -> Iterator[dict]:
    """Yield HypeCheck events from the AgentCore-hosted agent as they arrive."""
    arn = arn or json.loads((HERE / "agentcore.json").read_text())["agentRuntimeArn"]
    client = boto3.client("bedrock-agentcore", region_name=region,
                          config=Config(read_timeout=600, retries={"max_attempts": 2}))
    resp = client.invoke_agent_runtime(agentRuntimeArn=arn, runtimeSessionId=f"hypecheck-{uuid.uuid4().hex}",
                                       payload=json.dumps(payload).encode(), contentType="application/json",
                                       accept="text/event-stream")
    body = resp["response"]
    if "text/event-stream" not in resp.get("contentType", ""):
        data = json.loads(body.read())
        yield from (data if isinstance(data, list) else [data])
        return
    for raw in body.iter_lines():
        line = raw.decode("utf-8").strip()
        if line.startswith("data:"):
            item = json.loads(line[5:].strip())
            yield json.loads(item) if isinstance(item, str) else item


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", type=Path, required=True)
    ap.add_argument("--conclusion")
    ap.add_argument("--pmid")
    args = ap.parse_args()
    payload = {"draft": args.draft.read_text(encoding="utf-8")}
    payload.update({k: v for k, v in (("conclusion", args.conclusion), ("pmid", args.pmid)) if v})
    for e in stream_events(payload):
        if e.get("type") == "verdict":
            print(f"[{e.get('host')}] round {e['round']} -> {e['action']}:",
                  [(s['zone'], round(s['p_overclaim'], 2)) for s in e["sentences"]])
        elif e.get("type") == "done":
            print(f"[{e.get('host')}] done: published={e['published']} rounds={e['rounds']} "
                  f"decider_calls={e['decider_calls']} decider_ms={e['decider_ms']} llm_ms={e['llm_ms']}")
        elif e.get("type") in ("error", "published", "paper"):
            print(f"[{e.get('host')}] {e['type']}: {str(e.get('message') or e.get('file') or e.get('conclusion'))[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
