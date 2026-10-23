"""A decision receipt: the facts behind one verdict, written by code, hashed, and attached to the result.

Every number a person might question is in it: which checkpoint answered, the probability on each
rung for the source and for every sentence, the overclaim score, the thresholds and their basis, the
zone, and the policy that turned scores into an action. The receipt is canonical JSON, so the same
decision always gives the same hash, and anyone with the per-sentence probabilities can recompute
the overclaim score and the zone without a model.

Credit for the device: several entries in the same hackathon ship a per-decision receipt
(Changeset Second Opinion, Heal or Halt's "facts inserted by code"). Standard library only.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .fidelity import STRENGTH, DocumentVerdict, overclaim_probability

POLICY = ("zone(p) = block if p > block_threshold else review if p > review_threshold else ok; "
          "action = guide if any block and rounds <= max_rounds, confirm if any block after max_rounds, "
          "proceed if no block; deny if the source is empty or Decider is unreachable")
RECEIPT_VERSION = 1


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_receipt(verdict: DocumentVerdict, *, source: str, derived: str, threshold: float,
                  review_threshold: float | None, zones: list[str], action: str | None = None,
                  model: str = "unknown", round_no: int | None = None, host: str | None = None) -> dict[str, Any]:
    """Return the receipt dict. Its `hash` is the SHA-256 of the canonical JSON of everything else."""
    body: dict[str, Any] = {
        "receipt_version": RECEIPT_VERSION,
        "issued_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decider": {"model": model, "question": "strength", "options": STRENGTH},
        "source": {"sha256": sha256(source), "chars": len(source), "strength": verdict.source_strength,
                   "p": [round(x, 5) for x in verdict.p_source]},
        "derived": {"sha256": sha256(derived), "chars": len(derived)},
        "thresholds": {"block": threshold, "review": review_threshold,
                       "basis": "split conformal, alpha 0.10 / 0.20, on expert-labelled press-release pairs"},
        "policy": POLICY,
        "sentences": [{"i": i, "sha256": sha256(s.sentence), "strength": s.strength, "p": [round(x, 5) for x in s.p_strength],
                       "overclaim": round(s.p_overclaim, 5), "zone": z}
                      for i, (s, z) in enumerate(zip(verdict.sentences, zones))],
        "advisory": verdict.advisory,
    }
    if action is not None:
        body["action"] = action
    if round_no is not None:
        body["round"] = round_no
    if host:
        body["host"] = host
    body["hash"] = sha256(_canonical(body))
    return body


def verify_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Recompute what can be recomputed without a model. Returns {ok, hash_ok, scores_ok, zones_ok, problems}."""
    body = {k: v for k, v in receipt.items() if k != "hash"}
    problems: list[str] = []
    hash_ok = sha256(_canonical(body)) == receipt.get("hash")
    if not hash_ok:
        problems.append("hash does not match the receipt body")
    p_src = receipt["source"]["p"]
    thr, rev = receipt["thresholds"]["block"], receipt["thresholds"]["review"]
    scores_ok = zones_ok = True
    for s in receipt["sentences"]:
        p = overclaim_probability(s["p"], p_src)
        if abs(p - s["overclaim"]) > 1e-4:
            scores_ok = False
            problems.append(f"sentence {s['i']}: overclaim {s['overclaim']} but the rung probabilities give {p:.5f}")
        z = "block" if s["overclaim"] > thr else "review" if rev is not None and s["overclaim"] > rev else "ok"
        if z != s["zone"]:
            zones_ok = False
            problems.append(f"sentence {s['i']}: zone {s['zone']} but the thresholds give {z}")
    return {"ok": hash_ok and scores_ok and zones_ok, "hash_ok": hash_ok, "scores_ok": scores_ok,
            "zones_ok": zones_ok, "problems": problems}


__all__ = ["build_receipt", "verify_receipt", "sha256", "POLICY", "RECEIPT_VERSION"]
