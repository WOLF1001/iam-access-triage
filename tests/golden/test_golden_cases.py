"""Golden set of dirty requests on zone boundaries (tests/golden/cases.yaml).

Three properties per case:
  1. the route matches the design expectation (exact or "not lower than");
  2. nothing that changes access is executed unless the expected zone is AUTO;
  3. determinism: the same input gives the same decision twice.
Plus fail-closed for every case when the LLM returns garbage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conftest import SEV, run_text  # noqa: E402
from triage import classify  # noqa: E402

CASES = yaml.safe_load((Path(__file__).with_name("cases.yaml")).read_text(encoding="utf-8"))["cases"]
IDS = [c["id"] for c in CASES]


def _run(c, mode="rules"):
    return run_text(c["text"], requester=c["requester"], thread=c.get("thread"), mode=mode)


def test_golden_set_shape():
    assert len(CASES) >= 25
    assert sum(1 for c in CASES if c["boundary"]) >= 10
    assert len(set(IDS)) == len(IDS)


@pytest.mark.parametrize("c", CASES, ids=IDS)
def test_route_matches_design(c):
    r = _run(c)
    exp = c["expect"]
    if "route" in exp:
        assert r.overall_route == exp["route"], c["why"]
    else:
        assert SEV[r.overall_route] >= SEV[exp["min_route"]], c["why"]
    if "priority" in exp:
        top = [d for d in r.decisions if d.route == r.overall_route]
        assert min(d.priority for d in top) == exp["priority"], c["why"]


@pytest.mark.parametrize("c", CASES, ids=IDS)
def test_no_access_change_outside_auto(c):
    r = _run(c)
    if c["expect"].get("zone") != "AUTO":
        assert not any(d.action_done and d.action != "readonly_diagnostic" for d in r.decisions), c["why"]


@pytest.mark.parametrize("c", CASES, ids=IDS)
def test_deterministic(c):
    a, b = _run(c), _run(c)
    pick = lambda r: [(d.route, d.next_route, d.action, d.priority, [x["signal"] for x in d.reasons]) for d in r.decisions]
    assert pick(a) == pick(b) and a.draft == b.draft


@pytest.mark.parametrize("garbage", ["not json at all", '{"is_iam": true, "sub_requests": [{"type": "AUTO_RESOLVE"}]}', "{}"])
def test_fail_closed_on_invalid_llm_json(monkeypatch, garbage):
    """LLM returns garbage → parse error / unknown type → every golden case ≥ HUMAN, no access change."""
    def fake_llm(text, thread=None, **kw):
        return classify._validate(json.loads(garbage))   # JSONDecodeError for non-JSON → classify() falls back
    monkeypatch.setattr(classify, "classify_llm", fake_llm)
    for c in CASES:
        r = _run(c, mode="llm")
        assert SEV[r.overall_route] >= SEV["HUMAN_REVIEW"], (c["id"], garbage)
        assert not any(d.action_done and d.action != "readonly_diagnostic" for d in r.decisions), c["id"]


@pytest.mark.xfail(strict=True, reason="ВІДОМЕ ОБМЕЖЕННЯ (critique.md §1.2): «мене зламали» без regex-тригера "
                                       "не піднімається до SECURITY у rules-режимі; залежить від того, чи LLM додасть сигнал")
def test_g30_account_takeover_claim_reaches_security():
    c = next(x for x in CASES if x["id"] == "g30")
    assert _run(c).overall_route == "SECURITY_ESCALATION"
