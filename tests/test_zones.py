"""Phase 5: zone boundaries from docs/zones.md and ADR-0003.

Covers the four HUMAN-ONLY extensions accepted on 2026-10-07 (on_behalf, financial_data, prod_access,
sod_conflict), "HUMAN-ONLY wins over everything", queue priorities, dedup and prompt-cache invalidation.
"""
from __future__ import annotations

import pytest

from conftest import REQ, SEV, run_text
from triage import catalog, classify, config
from triage.classify import SubRequest
from triage.dedup import DedupStore

POL = config.policy()
HUMAN_ONLY = sorted(r["signal"] for r in POL["hard_rules"]
                    if r["min_route"] and SEV[r["min_route"]] >= SEV["HUMAN_REVIEW"])


def no_change_action(r) -> bool:
    return not any(d.action_done and d.action != "readonly_diagnostic" for d in r.decisions)


# ---------------------------------------------------------------- 4 accepted extensions
def test_on_behalf_grant_is_human_even_from_subjects_manager():
    """U08 (Kateryna) is Olena's manager in HRIS — still HUMAN-ONLY (zones.md §6, decision 1)."""
    r = run_text("дайте доступ до tableau моїй колезі olena.marchenko@corp.example", requester="U08")
    assert r.overall_route == "HUMAN_REVIEW" and no_change_action(r)


def test_on_behalf_has_no_type_exemption():
    """Even a how-to for a colleague goes to a human: the type is chosen by the LLM, so a type-based exemption
    would let the LLM drop a regex signal (ai-mistakes #22). Over-escalation is the accepted cost."""
    r = run_text("як моїй колезі підключитись до vpn? інструкція", requester="U01")
    assert r.overall_route == "HUMAN_REVIEW"


def test_financial_data_is_human():
    assert run_text(REQ[57], req_id=57, requester="U17").overall_route == "HUMAN_REVIEW"


@pytest.mark.parametrize("text", ["дайте доступ до growthbook", "треба доступ до github", "дайте доступ на прод у aws"])
def test_prod_access_is_human(text):
    r = run_text(text, requester="U01")
    assert r.overall_route == "HUMAN_REVIEW"
    assert "prod_access" in {s.name for d in r.decisions for s in d.signals}


def test_sod_from_text():
    r = run_text("дайте мені права в tableau, щоб я міг сам собі апрувити заявки", requester="U01")
    assert r.overall_route == "HUMAN_REVIEW"
    assert "sod_conflict" in {s.name for d in r.decisions for s in d.signals}


def test_sod_from_read_side_requester_is_resource_approver():
    """U18 (Pavlo) holds engineering-lead = owner/approver of GitHub → cannot approve own access."""
    r = run_text("дайте доступ до github", requester="U18")
    sigs = {(s.name, s.origin) for d in r.decisions for s in d.signals}
    assert ("sod_conflict", "read") in sigs and r.overall_route == "HUMAN_REVIEW"


@pytest.mark.parametrize("app", ["github", "aws", "figma", "amplitude"])
def test_new_catalog_apps_resolve(app):
    assert catalog.resolve_apps(f"дайте доступ до {config.catalog()[app]['aliases'][0]}") == [app]


# ---------------------------------------------------------------- HUMAN-ONLY wins over everything
@pytest.mark.parametrize("signal", [s for s in HUMAN_ONLY if s in classify.LLM_SIGNALS])
def test_human_only_signal_beats_auto_candidate(llm, signal):
    """VPN for an active employee is the AUTO candidate; any HUMAN-ONLY signal must override it."""
    llm(SubRequest(summary="треба доступ до корп vpn", type="access_request", app_mentions=["vpn"],
                   signals=[signal], confidence=0.99))
    r = run_text("треба доступ до корп vpn", mode="llm", requester="U01")
    assert SEV[r.overall_route] >= SEV["HUMAN_REVIEW"], signal
    assert no_change_action(r), signal


# ---------------------------------------------------------------- priorities
@pytest.mark.parametrize("rid,requester,level", [
    (32, "U12", "P1"),          # secret compromise → SECURITY
    (92, "U08", "P1"),          # offboarding
    (93, "UGEN", "P4"),         # DOCS — bot closes it
    (51, "U14", "P4"),          # REROUTE
    (46, "U03", "P2"),          # HUMAN + «асап»
    (12, "U18", "P3"),          # HUMAN, no urgency
])
def test_priorities(rid, requester, level):
    r = run_text(REQ[rid], req_id=rid, requester=requester)
    assert max(d.priority for d in r.decisions if d.route == r.overall_route) == level


def test_urgency_changes_priority_not_route():
    base = run_text("дайте доступ до tableau", requester="U01")
    urgent = run_text("дайте доступ до tableau асап", requester="U01")
    assert urgent.overall_route == base.overall_route
    assert urgent.decisions[0].priority == "P2" and base.decisions[0].priority == "P3"


def test_human_route_still_asks_for_missing_data():
    """HUMAN-ONLY must not bring back the clarification round-trip to the engineer (current-state.md §3)."""
    r = run_text(REQ[17], req_id=17)
    assert r.overall_route == "HUMAN_REVIEW" and "список" in r.draft


# ---------------------------------------------------------------- dedup
def _result(app="tableau", typ="access_request"):
    return {"route": "APPROVAL_GATED", "decisions": [{"type": typ, "primary_app": app}]}


def test_dedup_slack_retry_returns_cached():
    store = DedupStore()
    res = _result()
    store.record("Ev1", "a@corp.example", res, now=1000)
    assert store.cached("Ev1", now=1060) is res
    assert store.cached("Ev1", now=1000 + 25 * 3600) is None   # outside event window


def test_dedup_repeat_of_same_requester_type_system():
    store = DedupStore()
    store.record("Ev1", "a@corp.example", _result(), now=1000)
    assert store.record("Ev2", "a@corp.example", _result(), now=2000)["repeat_of"] == "Ev1"
    assert store.record("Ev3", "b@corp.example", _result(), now=2000)["repeat_of"] is None


def test_dedup_pattern_across_requesters():
    store = DedupStore()
    for i, who in enumerate(["a", "b", "c"]):
        info = store.record(f"Ev{i}", f"{who}@corp.example", _result("claude_org", "limits_quota"), now=1000 + i)
    assert info["patterns"] == [{"type": "limits_quota", "system": "claude_org", "requesters": 3}]


# ---------------------------------------------------------------- LLM cache
def test_prompt_edit_invalidates_llm_cache(tmp_path, monkeypatch):
    (tmp_path / "p.md").write_text("v1", encoding="utf-8")
    monkeypatch.setattr(config, "PROMPTS", tmp_path)
    k1 = classify._cache_key("m", classify._prompt_version("p.md"), "t", None)
    (tmp_path / "p.md").write_text("v2", encoding="utf-8")
    k2 = classify._cache_key("m", classify._prompt_version("p.md"), "t", None)
    assert k1 != k2


# ---------------------------------------------------------------- human handoff (templates/human-handoff.md)
@pytest.mark.parametrize("rid,requester", [(92, "U08"), (46, "U03"), (32, "U12"), (69, "U05")])
def test_handoff_has_required_sections(rid, requester):
    from conftest import REQ as R
    sample = {c["id"]: c for c in config.load_sample()["cases"]}
    r = run_text(R[rid], req_id=rid, requester=requester, thread=sample.get(rid, {}).get("thread"))
    note = r.internal_note
    for section in ("HANDOFF ·", "Автор:", "Звернення (після redaction)", "Розбір:", "Чому не авто:", "Що потрібно від тебе:"):
        assert section in note, (rid, section)
    assert "sk-ant-" not in note
