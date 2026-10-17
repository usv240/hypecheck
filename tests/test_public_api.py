"""Offline tests for API keys, limits and the public API (fake decider, no network, no Bedrock)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import hypecheck.apikeys as ak
import hypecheck.public_api as pub
from tests.test_decision_pattern import FakeDecider


@pytest.fixture()
def store(tmp_path):
    return ak.KeyStore(tmp_path / "keys.json")


def test_keys_are_hashed_and_verifiable(store, tmp_path):
    key = store.issue("1.2.3.4")
    assert key.startswith("hc_") and key not in (tmp_path / "keys.json").read_text()
    assert store.verify(key)
    with pytest.raises(ak.LimitExceeded):
        store.verify("hc_nope")
    with pytest.raises(ak.LimitExceeded):
        store.verify(None)


def test_issue_throttle_per_network(store):
    for _ in range(ak.KEYS_PER_IP_PER_DAY):
        store.issue("5.6.7.8")
    with pytest.raises(ak.LimitExceeded):
        store.issue("5.6.7.8")
    assert store.issue("9.9.9.9")  # a different network is unaffected


def test_daily_limits_and_global_budget(store, monkeypatch):
    kid = store.verify(store.issue("1.1.1.1"))
    monkeypatch.setitem(ak.LIMITS, "rewrite", 2)
    store.spend(kid, "rewrite"); store.spend(kid, "rewrite")
    with pytest.raises(ak.LimitExceeded):
        store.spend(kid, "rewrite")
    kid2 = store.verify(store.issue("2.2.2.2"))
    monkeypatch.setattr(ak, "GLOBAL_DAILY_USD", 0.001)
    store.add_cost(1000, 1000)  # $0.018 > budget
    with pytest.raises(ak.LimitExceeded) as e:
        store.spend(kid2, "rewrite")
    assert e.value.status == 503
    store.spend(kid2, "check")  # checks are unaffected by the rewrite budget


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ak, "STATE", tmp_path)
    eng = pub.Engine.__new__(pub.Engine)
    eng.decider = FakeDecider({"prevents": 3, "associated": 1, "linked": 1})
    eng.threshold, eng.review_threshold = 0.5, 0.4
    eng.keys, eng.bedrock, eng.jobs = ak.KeyStore(tmp_path / "keys.json"), None, {}
    monkeypatch.setattr(pub, "engine", eng)
    app = FastAPI()
    app.include_router(pub.router)
    return TestClient(app)


def test_check_endpoint(client):
    assert client.post("/v1/check", json={"source": "x was associated with y.", "text": "x prevents y."}).status_code == 401
    key = client.post("/v1/keys").json()["api_key"]
    r = client.post("/v1/check", headers={"Authorization": f"Bearer {key}"},
                    json={"source": "Coffee was associated with lower risk.", "text": "Coffee prevents cancer. It was linked to risk."})
    body = r.json()
    assert r.status_code == 200 and body["verdict"] == "block"
    assert [s["zone"] for s in body["sentences"]] == ["block", "ok"]
    assert client.get("/v1/usage", headers={"X-API-Key": key}).json()["today"]["check"] == 1


def test_calibrate_needs_enough_faithful_pairs(client):
    key = client.post("/v1/keys").json()["api_key"]
    pairs = [{"source": "a was associated with b.", "derived": "a prevents b.", "label": "overclaim"}] * 10
    r = client.post("/v1/calibrate", headers={"Authorization": f"Bearer {key}"}, json={"alpha": 0.1, "pairs": pairs})
    assert r.status_code == 400 and "faithful" in r.json()["detail"]
