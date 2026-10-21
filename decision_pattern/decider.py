"""Minimal synchronous client for a running `strands-decider serve`.

Standard library only, so the decision pattern can be copied into any agent without new
dependencies. One state, many typed questions, one round trip: the server encodes the state
once and every extra question costs only its own tokens, so ask everything at once.

Backups: pass several servers, comma-separated (`STRANDS_DECIDER_URL="http://gpu:8099,http://cpu:8099"`).
If one stops answering, the client moves to the next and stays there.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

DEFAULT_URL = os.environ.get("STRANDS_DECIDER_URL", "http://127.0.0.1:8099")
# Optional shared secret, sent as x-hypecheck-key, for a Decider behind a guarded proxy.
DEFAULT_KEY = os.environ.get("STRANDS_DECIDER_KEY", "")


class DeciderUnavailable(RuntimeError):
    """Nothing is answering at any configured URL."""


class Decider:
    def __init__(self, url: str = DEFAULT_URL, timeout: float = 120.0, key: str = DEFAULT_KEY) -> None:
        self.urls = [u.strip().rstrip("/") for u in url.split(",") if u.strip()]
        self.url = self.urls[0]  # the server currently in use
        self.key = key
        self.timeout = timeout
        self.calls = 0
        self.total_ms = 0.0

    def ask(self, state: str, questions: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        body = json.dumps({"state": state, "questions": questions}).encode()
        headers = {"content-type": "application/json"}
        if self.key:
            headers["x-hypecheck-key"] = self.key
        start = self.urls.index(self.url)
        order = self.urls[start:] + self.urls[:start]
        for i, url in enumerate(order):
            req = urllib.request.Request(f"{url}/v1/systemone", body, headers)
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    out = json.load(r)
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                if i == len(order) - 1:
                    raise DeciderUnavailable(
                        f"no decider at {', '.join(self.urls)}; start one with "
                        "`strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8099`"
                    ) from exc
        self.url = url
        self.calls += 1
        self.total_ms += (time.perf_counter() - t0) * 1000
        return out["answers"]

    def health(self) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(f"{self.url}/health", timeout=5) as r:
                return json.load(r)
        except urllib.error.URLError as exc:
            raise DeciderUnavailable(f"no decider at {self.url}") from exc
