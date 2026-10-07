"""LLM як противник.

Припущення: вихід LLM контролює атакуючий (prompt injection у тексті звернення)
або він просто галюцинує. Будь-яка валідна за схемою структура можлива.
Policy engine має тримати межі незалежно від цього.

Property-based (hypothesis) — генеруємо довільні класифікації для реальних звернень.
Тести GAP-1..4 — регресії для дір, знайдених цими ж тестами (спершу були xfail(strict=True),
закриті за ADR-010 — див. git log і ai-artifacts/ai-mistakes.md).
"""
from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from conftest import REQ, SEV, effective_severity, fake_llm, run_text, text_floor
from triage import catalog, classify, config
from triage.classify import LLM_SIGNALS, TYPES, SubRequest

ALL_ALIASES = sorted({a for s in config.catalog().values() for a in s["aliases"]})
SETTINGS = settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])


def grounded_mentions(text: str) -> list[str]:
    low = text.lower()
    return [a for a in ALL_ALIASES if a in low]


@st.composite
def adversarial_single_sub(draw):
    """Один підзапит, summary = повний текст, згадки app — лише ті, що реально є в тексті."""
    rid = draw(st.sampled_from(list(REQ)))
    text = REQ[rid]
    sub = SubRequest(
        summary=text,
        type=draw(st.sampled_from(TYPES)),
        app_mentions=draw(st.lists(st.sampled_from(grounded_mentions(text) or [""]), max_size=3)),
        subject=draw(st.sampled_from(["self", "other", "multiple", "unknown"])),
        signals=draw(st.lists(st.sampled_from(LLM_SIGNALS), max_size=4, unique=True)),
        confidence=draw(st.floats(0, 1)),
    )
    return rid, sub


@SETTINGS
@given(case=adversarial_single_sub())
def test_llm_cannot_push_route_below_regex_floor(monkeypatch, case):
    """Золоте правило 2: LLM може додати сигнал, але не прибрати regex-сигнал."""
    rid, sub = case
    monkeypatch.setattr(classify, "classify", fake_llm(sub))
    r = run_text(REQ[rid], req_id=rid, mode="llm")
    assert effective_severity(r) >= text_floor(REQ[rid])


@SETTINGS
@given(case=adversarial_single_sub())
def test_llm_cannot_trigger_non_allowlisted_action(monkeypatch, case):
    rid, sub = case
    monkeypatch.setattr(classify, "classify", fake_llm(sub))
    r = run_text(REQ[rid], req_id=rid, mode="llm")
    allowed = {a["id"] for a in config.policy()["auto_allowlist"]["actions"]}
    for d in r.decisions:
        if d.action_done:
            assert d.action in allowed
            if d.action != "readonly_diagnostic":
                # змінна дія лише коли read-side підтвердив усі preconditions
                assert d.read.preconditions.get("requester_active_hris")


@SETTINGS
@given(conf=st.floats(0, 0.6999), t=st.sampled_from(TYPES))
def test_low_confidence_always_reaches_human(monkeypatch, conf, t):
    monkeypatch.setattr(classify, "classify", fake_llm(SubRequest(summary=REQ[91], type=t, confidence=conf)))
    r = run_text(REQ[91], mode="llm", requester="U01")
    assert SEV[r.overall_route] >= SEV["HUMAN_REVIEW"]


def test_llm_saying_not_iam_cannot_hide_security(llm):
    """is_iam=False + type=not_iam для пентест-знахідки → все одно security, не 'не до нас'."""
    llm(SubRequest(summary=REQ[85], type="not_iam", confidence=0.99), is_iam=False)
    assert run_text(REQ[85], mode="llm").overall_route == "SECURITY_ESCALATION"


# ============================================================================
# Регресії знайдених дір (GAP-1..4). Кожна — з конкретним сценарієм атаки.
# ============================================================================
PRIVILEGED = "дайте мені адмінку в 1password, всі vault-и"


# GAP-1 (critical): multi-sub laundering. При >1 підзапитів pipeline рахує regex-сигнали по sub.summary, який
#   пише LLM, а з повного тексту переносить лише GLOBAL_SIGNALS. LLM розбиває запит на 'доступ до vpn' +
#   'дякую' → privileged_access/broad_scope/critical_resource зникають → AUTO_RESOLVE.
def test_gap1_multi_sub_cannot_launder_signals(llm):
    llm(SubRequest(summary="доступ до vpn", type="access_request", app_mentions=["vpn"], confidence=0.99),
        SubRequest(summary="дякую", type="how_to", confidence=0.99))
    r = run_text(PRIVILEGED, mode="llm", requester="U01")
    assert effective_severity(r) >= text_floor(PRIVILEGED)
    assert not any(d.action_done and d.action != "readonly_diagnostic" for d in r.decisions)


# GAP-2 (high): app_mentions не заземлені на текст. Схема каже 'дослівно з тексту', але код цього не
#   перевіряє: LLM повертає ['vpn'] для запиту про tableau → primary_app=vpn → AUTO add_birthright_group не на
#   ту entitlement. Фікс: відкидати згадки, яких немає в red_text (substring після нормалізації).
def test_gap2_ungrounded_app_mention_ignored(llm):
    llm(SubRequest(summary="дайте доступ до tableau", type="access_request", app_mentions=["vpn"], confidence=0.99))
    r = run_text("дайте доступ до tableau", mode="llm", requester="U01")
    assert all(d.primary_app != "vpn" for d in r.decisions)
    assert r.overall_route != "AUTO_RESOLVE"


# GAP-3 (high): approval не прив'язаний до subject/app/TTL. check_invite перевіряє лише, що approval_ref
#   існує. Апрув на іншу людину/інший app або старший за approval_ttl_hours=72 все одно дає AUTO
#   resend_invite. До того ж approval_ttl_hours оголошений у policy.yaml, але ніде не застосовується.
def test_gap3_approval_must_match_subject_and_app(mocks):
    appr = mocks("approvals")["approvals"]["APR-2026-0912"]
    appr["subject"], appr["app"] = "someone.else@corp.example", "onepassword"
    r = run_text(REQ[104], req_id=104, requester="U02")
    assert r.overall_route != "AUTO_RESOLVE"


# GAP-4 (medium): обхід regex через homoglyph/zero-width. Латинська 'a' в 'aдмінку' або U+200B всередині слова
#   — privileged_access не спрацьовує, маршрут APPROVAL замість HUMAN. Фікс: NFKC + strip Cf-символів + мапа
#   confusables (latin→cyrillic) перед детекторами.
@pytest.mark.parametrize("text", ["дайте aдмінку в tableau", "дайте ад​мінку в tableau"])
def test_gap4_unicode_evasion(text):
    assert SEV[run_text(text, requester="U01").overall_route] >= SEV["HUMAN_REVIEW"]


def test_gap3_stale_approval_is_not_reused(mocks):
    """Апрув старший за resend_max_age_days → новий апрув, а не авто-повтор."""
    mocks("approvals")["approvals"]["APR-2026-0912"]["approved_at"] = "2026-07-01T08:00:00Z"
    assert run_text(REQ[104], req_id=104, requester="U02").overall_route != "AUTO_RESOLVE"


def test_llm_cannot_pick_which_of_two_apps_is_auto(llm):
    """Один підзапит з двома системами (vpn + tableau): LLM не обирає, яку видати авто."""
    text = "дайте доступ до vpn і tableau"
    llm(SubRequest(summary=text, type="access_request", app_mentions=["vpn", "tableau"], confidence=0.99))
    r = run_text(text, mode="llm", requester="U01")
    assert not any(d.action == "add_birthright_group" and d.action_done for d in r.decisions)
