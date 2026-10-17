"""Self-serve API keys with daily limits and a global spend ceiling.

Keys are issued instantly with no signup and no personal data. Only a SHA-256 hash of each key is
stored, so the file cannot be used to recover keys. Counters reset at midnight UTC. Claude
rewrites spend real Bedrock money, so they have a per-key cap and a global daily dollar ceiling
on top.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path

STATE = Path(os.environ.get("HYPECHECK_STATE", Path(__file__).resolve().parents[1] / "state"))

LIMITS = {
    "check": 300,          # Decider-only checks per key per day (no LLM cost)
    "rewrite": 20,         # Claude rewrite calls per key per day
    "calibrate": 3,        # calibration jobs per key per day
}
KEYS_PER_IP_PER_DAY = 3
GLOBAL_DAILY_USD = float(os.environ.get("HYPECHECK_DAILY_BUDGET_USD", "2.0"))
# Bedrock list price for the rewrite model (Claude Sonnet 4.6), USD per token.
PRICE_IN, PRICE_OUT = 3.0 / 1e6, 15.0 / 1e6


class LimitExceeded(Exception):
    def __init__(self, message: str, status: int = 429) -> None:
        super().__init__(message)
        self.status = status


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class KeyStore:
    def __init__(self, path: Path = STATE / "apikeys.json") -> None:
        self.path = path
        self.lock = threading.Lock()
        self.data = json.loads(path.read_text()) if path.exists() else {"keys": {}, "ips": {}, "spend": {}}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data))
        tmp.replace(self.path)

    def issue(self, ip: str) -> str:
        with self.lock:
            day = _today()
            ip_h = _hash(ip)[:16]  # issuance throttle only; the address itself is not stored
            seen = self.data["ips"].setdefault(day, {})
            if seen.get(ip_h, 0) >= KEYS_PER_IP_PER_DAY:
                raise LimitExceeded(f"at most {KEYS_PER_IP_PER_DAY} new keys per day from one network")
            for old in [d for d in self.data["ips"] if d != day]:
                del self.data["ips"][old]
            seen[ip_h] = seen.get(ip_h, 0) + 1
            key = "hc_" + secrets.token_urlsafe(24)
            self.data["keys"][_hash(key)] = {"created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                             "usage": {}, "total": {}}
            self._save()
            return key

    def verify(self, key: str | None) -> str:
        if not key:
            raise LimitExceeded("missing API key: send 'Authorization: Bearer hc_…' (get one at /developers)", 401)
        kid = _hash(key.strip())
        if kid not in self.data["keys"]:
            raise LimitExceeded("unknown API key", 401)
        return kid

    def spend(self, kid: str, action: str, n: int = 1) -> dict:
        """Count one use of `action` against the key's daily limit, or raise."""
        with self.lock:
            rec = self.data["keys"][kid]
            day = _today()
            usage = rec["usage"] if rec.get("usage_day") == day else {}
            if usage.get(action, 0) + n > LIMITS[action]:
                raise LimitExceeded(f"daily limit reached for {action} ({LIMITS[action]} per key per day)")
            if action == "rewrite" and self.data["spend"].get(day, 0.0) >= GLOBAL_DAILY_USD:
                raise LimitExceeded("today's shared budget for Claude rewrites is used up; /v1/check still works", 503)
            usage[action] = usage.get(action, 0) + n
            rec["usage"], rec["usage_day"] = usage, day
            rec["total"][action] = rec["total"].get(action, 0) + n
            self._save()
            return dict(usage)

    def add_cost(self, input_tokens: int, output_tokens: int) -> float:
        cost = input_tokens * PRICE_IN + output_tokens * PRICE_OUT
        with self.lock:
            day = _today()
            self.data["spend"] = {d: v for d, v in self.data["spend"].items() if d == day}
            self.data["spend"][day] = self.data["spend"].get(day, 0.0) + cost
            self._save()
        return cost

    def usage(self, kid: str) -> dict:
        rec = self.data["keys"][kid]
        today = rec["usage"] if rec.get("usage_day") == _today() else {}
        return {"today": {a: today.get(a, 0) for a in LIMITS}, "limits": LIMITS, "all_time": rec["total"],
                "created": rec["created"], "resets": "00:00 UTC",
                "shared_rewrite_budget_usd": {"limit": GLOBAL_DAILY_USD,
                                              "used": round(self.data["spend"].get(_today(), 0.0), 4)}}
