"""Інваріанти системи, які не залежать від точності класифікації.

Групи:
  1. Цілісність конфігу (policy / catalog / kb узгоджені між собою)
  2. Контракти маршрутів (кожен маршрут має все, що йому потрібно для дії)
  3. Підлога і монотонність (правила тільки піднімають; додавання ризику не знижує)
  4. Секрети (нічого сирого не виходить за межу redaction)
  5. Read-side як джерело правди для AUTO
  6. Fail-closed і детермінізм
"""
from __future__ import annotations

import json
import re

import pytest

from conftest import REQ, SEV, effective_severity, run_text, text_floor
from triage import catalog, classify, config, pipeline
from triage.act import ActionLog
from triage.classify import LLM_SIGNALS, TYPES
from triage.redact import PATTERNS, redact
from triage.respond import USER_FACING
from triage.signals import MISSING_DETECTORS, TEXT_DETECTORS

POL = config.policy()
CAT = config.catalog()
KB = config.kb()
RULE_SIGNALS = {r["signal"] for r in POL["hard_rules"]}
READ_SIGNALS = {"suspicious_auth_activity", "source_conflict", "regrant_needed", "requester_not_verified",
                "approver_unavailable"}
STRUCTURAL = {"critical_resource", "unknown_app", "missing_critical_data", "low_confidence", "multi_intent",
              "secret_in_message", "llm_ungrounded"}


@pytest.fixture(scope="module")
def full_run():
    """Усі 108 звернень у rules-режимі від «типового співробітника»."""
    return {i: run_text(t, req_id=i) for i, t in REQ.items()}


# ---------------------------------------------------------------- 1. конфіг
class TestConfigIntegrity:
    def test_every_type_has_base_route_and_reason(self):
        from triage.policy import TYPE_REASON
        assert set(TYPES) == set(POL["type_base_route"]) == set(TYPE_REASON)
        assert all(r in SEV for r in POL["type_base_route"].values())

    def test_hard_rules_reference_known_routes(self):
        for r in POL["hard_rules"]:
            assert r["min_route"] is None or r["min_route"] in SEV, r

    def test_every_hard_rule_signal_has_a_producer(self):
        """Правило без джерела сигналу — мертвий код, що створює ілюзію захисту."""
        producers = set(TEXT_DETECTORS) | set(LLM_SIGNALS) | READ_SIGNALS | STRUCTURAL
        assert RULE_SIGNALS - producers == set()

    def test_every_llm_signal_has_an_effect(self):
        """Сигнал, який LLM може повернути, але policy ігнорує, — тиха втрата інформації."""
        effective = RULE_SIGNALS | set(POL["risk_modifiers"])
        assert set(LLM_SIGNALS) - effective == set()

    def test_allowlist_and_forbidden_disjoint(self):
        allowed = {a["id"] for a in POL["auto_allowlist"]["actions"]}
        assert allowed == {"resend_invite", "add_birthright_group", "readonly_diagnostic"}
        assert allowed.isdisjoint(POL["auto_allowlist"]["forbidden_always"])

    def test_route_severity_order(self):
        order = ["DOCS_REDIRECT", "AUTO_RESOLVE", "NEED_INFO", "APPROVAL_GATED", "HUMAN_REVIEW", "SECURITY_ESCALATION"]
        assert [SEV[r] for r in order] == sorted(SEV[r] for r in order)
        assert SEV["REROUTE"] == SEV["AUTO_RESOLVE"]

    def test_catalog_schema(self):
        for app_id, spec in CAT.items():
            assert spec["risk_tier"] in ("low", "medium", "high", "critical"), app_id
            assert spec.get("aliases"), app_id
            for art in spec.get("kb", []):
                assert art in KB["articles"], f"{app_id} → неіснуюча KB-стаття {art}"

    def test_bot_writable_groups_are_low_risk_birthright(self):
        """birthright у каталозі = «базовий акаунт є в усіх» (Okta, 1Password, GWS теж).
        Межа AUTO — не прапорець birthright, а allowlist груп бота (Okta resource set).
        Тож кожна група з allowlist бота має належати low-risk birthright-app."""
        bot_groups = set(config.mock("okta")["groups_allowlisted_for_bot"])
        owners = {s.get("okta_group"): (a, s) for a, s in CAT.items() if s.get("okta_group")}
        for g in bot_groups:
            assert g in owners, f"група {g} в allowlist бота, але не в каталозі"
            app_id, spec = owners[g]
            assert spec.get("birthright") and spec["risk_tier"] == "low", app_id

    @pytest.mark.parametrize("app_id", [a for a, s in CAT.items() if s.get("birthright") and s["risk_tier"] != "low"])
    def test_high_risk_birthright_app_never_auto(self, app_id):
        alias = CAT[app_id]["aliases"][0]
        r = run_text(f"дайте доступ до {alias}", requester="U01")
        assert r.overall_route != "AUTO_RESOLVE", app_id

    def test_aliases_unique_across_apps(self):
        seen: dict[str, str] = {}
        for app_id, spec in CAT.items():
            for a in spec["aliases"]:
                assert seen.setdefault(a.lower(), app_id) == app_id, f"alias '{a}': {seen[a.lower()]} vs {app_id}"

    def test_detector_regexes_compile(self):
        for pats in list(TEXT_DETECTORS.values()) + list(MISSING_DETECTORS.values()):
            for p in pats:
                re.compile(p)

    def test_kb_articles_have_url_and_summary(self):
        for aid, a in KB["articles"].items():
            assert a.get("url") and a.get("summary") and a.get("title"), aid


# ---------------------------------------------------------------- 2. контракти маршрутів
class TestRouteContracts:
    """Маршрут без потрібних атрибутів — це «напівдія»: людина отримує тікет, з яким нічого не зробиш."""

    def _decisions(self, full_run):
        return [(i, d) for i, r in full_run.items() for d in r.decisions]

    def test_every_decision_explains_itself(self, full_run):
        for i, d in self._decisions(full_run):
            assert d.reasons and d.reasons[0]["signal"].startswith("type:"), i

    def test_need_info_always_asks_something(self, full_run):
        for i, d in self._decisions(full_run):
            if d.route == "NEED_INFO":
                assert d.questions, i
                assert d.action in (None, "readonly_diagnostic"), i

    def test_docs_redirect_only_with_existing_article(self, full_run):
        for i, d in self._decisions(full_run):
            if d.route == "DOCS_REDIRECT":
                assert d.kb_articles and all(a in KB["articles"] for a in d.kb_articles), i

    def test_reroute_has_known_queue(self, full_run):
        queues = set(KB["reroute_queues"])
        for i, d in self._decisions(full_run):
            if d.route == "REROUTE":
                assert d.queue in queues, (i, d.queue)

    def test_approval_has_approvers(self, full_run):
        for i, d in self._decisions(full_run):
            if "APPROVAL_GATED" in (d.route, d.next_route):
                assert d.approvers, i

    def test_security_is_p1_to_security_queue(self, full_run):
        for i, d in self._decisions(full_run):
            if d.route == "SECURITY_ESCALATION":
                assert d.priority == "P1" and d.queue == "security", i

    def test_actions_only_on_auto_or_readonly(self, full_run):
        for i, d in self._decisions(full_run):
            if d.action_done:
                assert d.route == "AUTO_RESOLVE" or d.action == "readonly_diagnostic", i

    def test_every_route_produces_a_log_record(self, tmp_path):
        """Кожне рішення лишає слід в act-журналі (крім DOCS — там дія = відповідь у треді)."""
        log = ActionLog(tmp_path / "a.log")
        results = {i: run_text(t, req_id=i, log=log) for i, t in REQ.items()}
        entries = [json.loads(x) for x in (tmp_path / "a.log").read_text().splitlines()]
        logged = {(e["request_id"], e["sub"]) for e in entries}
        for i, r in results.items():
            for k, d in enumerate(r.decisions):
                if d.route != "DOCS_REDIRECT":
                    assert (i, k) in logged, (i, k, d.route)
        assert all(e["dry_run"] is True and e["mode"] == "SIMULATED" for e in entries)

    def test_auto_share_is_small(self, full_run):
        """Sanity-check проти «тихого» розширення AUTO при правках regex/каталогу."""
        auto = [i for i, r in full_run.items() if r.overall_route == "AUTO_RESOLVE"]
        assert len(auto) <= 0.10 * len(full_run), auto


# ---------------------------------------------------------------- 3. підлога і монотонність
class TestFloorAndMonotonicity:
    @pytest.mark.parametrize("rid", list(REQ))
    def test_route_never_below_regex_floor(self, rid):
        r = run_text(REQ[rid], req_id=rid)
        assert effective_severity(r) >= text_floor(REQ[rid])

    RISK_SUFFIXES = [" це терміново асап", " і дайте адмінку", " і ще ключ злитий", " для колеги",
                     " і на всіх спейсах"]

    @pytest.mark.parametrize("suffix", RISK_SUFFIXES)
    def test_adding_risk_never_lowers_route(self, suffix):
        """Metamorphic: f(x + ризик) ≥ f(x). Інакше атакуючий може «докинути» фразу і знизити контроль."""
        bad = []
        for rid, t in REQ.items():
            before = effective_severity(run_text(t, req_id=rid))
            after = effective_severity(run_text(t + suffix, req_id=rid))
            if after < before:
                bad.append(rid)
        assert not bad

    def test_approval_claim_does_not_lower_policy_question(self):
        """Регресія GAP-5: 'лід в курсі' піднімав policy_question до APPROVAL і обходив kb_gap → #99 HUMAN→APPROVAL."""
        before = effective_severity(run_text(REQ[99], req_id=99))
        after = effective_severity(run_text(REQ[99] + " лід в курсі", req_id=99))
        assert after >= before


# ---------------------------------------------------------------- 4. секрети
FAKE_SECRETS = {
    "anthropic_api_key": "sk-ant-api03-" + "Q" * 40,
    "openai_api_key": "sk-proj-" + "Q" * 30,
    "aws_access_key": "AKIA" + "Q" * 16,
    "google_api_key": "AIza" + "Q" * 35,
    "github_token": "ghp_" + "Q" * 36,
    "slack_token": "xoxb-" + "1234567890-QQQQQQQQQQ",
    "jwt": "eyJ" + "Q" * 12 + "." + "Q" * 12 + "." + "Q" * 12,
    "private_key": "-----BEGIN RSA PRIVATE KEY-----",
    "password_inline": "пароль: QQQQ-hunter2",
}


class TestSecrets:
    def test_fixtures_cover_every_pattern(self):
        assert set(FAKE_SECRETS) == {n for n, _ in PATTERNS}

    @pytest.mark.parametrize("kind,secret", FAKE_SECRETS.items())
    def test_redact_detects_and_is_idempotent(self, kind, secret):
        out, found = redact(f"ось {secret} не працює")
        assert kind in found and secret not in out
        assert redact(out) == (out, [])

    @pytest.mark.parametrize("where", ["text", "thread"])
    @pytest.mark.parametrize("kind,secret", FAKE_SECRETS.items())
    def test_secret_never_leaves_redaction_boundary(self, monkeypatch, tmp_path, where, kind, secret):
        seen = []
        monkeypatch.setattr(classify, "classify",
                            lambda t, th, m: (seen.append((t, th)), classify.classify_rules(t, th))[1])
        text = f"дайте доступ до tableau {secret}" if where == "text" else "дайте доступ до tableau"
        thread = f"ось {secret}" if where == "thread" else None
        log = ActionLog(tmp_path / "a.log")
        r = run_text(text, thread=thread, log=log, requester="U01")
        everything = json.dumps({
            "llm_input": seen, "redacted": r.redacted_text, "thread": r.thread_redacted, "draft": r.draft,
            "note": r.internal_note, "decisions": [d.to_dict() for d in r.decisions],
            "facts": [f.to_dict() for d in r.decisions for f in (d.read.facts if d.read else [])],
        }, ensure_ascii=False) + (tmp_path / "a.log").read_text()
        assert secret not in everything
        assert r.overall_route == "SECURITY_ESCALATION"

    def test_draft_never_echoes_secret_type_names(self):
        """Користувачу кажемо нейтрально; не розкриваємо, який сканер спрацював (D9)."""
        r = run_text("ось ключ " + FAKE_SECRETS["aws_access_key"], requester="U01")
        assert "aws_access_key" not in r.draft


# ---------------------------------------------------------------- 5. read-side
class TestReadSideTrust:
    def test_inactive_requester_never_auto(self, mocks):
        for e in mocks("hris")["employees"]:
            if e["email"] == "olena.marchenko@corp.example":
                e["status"] = "terminated"
        r = run_text(REQ[91], requester="U01")
        assert all(not (d.action_done and d.action != "readonly_diagnostic") for d in r.decisions)

    def test_unknown_slack_user_is_not_verified(self):
        r = run_text(REQ[91], requester="U_NOBODY")
        assert r.overall_route == "HUMAN_REVIEW"
        assert "requester_not_verified" in {s.name for d in r.decisions for s in d.signals}

    def test_already_member_gets_docs_not_action(self, mocks):
        """VPN уже є → лише інструкція; повторне додавання = шум у журналі і хибний аудит."""
        okta = mocks("okta")["users"]["olena.marchenko@corp.example"]
        if "vpn-users" not in okta["groups"]:
            okta["groups"].append("vpn-users")
        r = run_text(REQ[91], requester="U01")
        assert not any(d.action == "add_birthright_group" and d.action_done for d in r.decisions)

    def test_offboarding_confirmed_by_hris_still_human(self, mocks):
        """Навіть підтверджене звільнення — деструктивна дія; бот готує план, людина натискає."""
        for e in mocks("hris")["employees"]:
            if e["email"] == "andrii.koval@corp.example":
                e["status"], e["termination_date"] = "terminated", "2026-10-06"
        r = run_text(REQ[92], requester="U08",
                     thread="Андрій Коваль (andrii.koval@corp.example), сьогодні останній день")
        assert r.overall_route in ("HUMAN_REVIEW", "SECURITY_ESCALATION")
        assert not any(d.action_done and d.action != "readonly_diagnostic" for d in r.decisions)
        assert r.decisions[0].read.dry_run_plan

    def test_manager_on_leave_comes_from_hris_not_text(self):
        """'лід у відпустці' в тексті нічого не доводить; approver_unavailable ставить лише read-side."""
        r = run_text("дайте доступ до tableau, лід у відпустці", requester="U01")
        assert not any(s.name == "approver_unavailable" and s.origin != "read"
                       for d in r.decisions for s in d.signals)


# ---------------------------------------------------------------- 6. fail-closed, детермінізм
class TestFailClosedAndDeterminism:
    def test_llm_outage_degrades_up_not_down(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("503")
        monkeypatch.setattr(classify, "classify_llm", boom)
        for rid, t in REQ.items():
            r = run_text(t, req_id=rid, mode="llm")
            assert SEV[r.overall_route] >= SEV["HUMAN_REVIEW"], rid
            assert not any(d.action_done and d.action != "readonly_diagnostic" for d in r.decisions), rid

    @pytest.mark.parametrize("raw", [
        {},                                                                      # порожньо
        {"is_iam": True, "sub_requests": []},                                    # без підзапитів
        {"is_iam": True, "sub_requests": [{"type": "access_request"}]},          # без confidence
        {"is_iam": True, "sub_requests": [{"type": "AUTO_RESOLVE", "confidence": 1}]},   # маршрут замість типу
        {"is_iam": True, "sub_requests": [{"type": "access_request", "confidence": 7, "subject": "root"}]},
    ])
    def test_malformed_llm_output_is_fail_closed(self, raw):
        c = classify._validate(raw)
        assert all(s.type in TYPES and 0 <= s.confidence <= 1 for s in c.sub_requests)
        assert all(s.subject in ("self", "other", "multiple", "unknown") for s in c.sub_requests)
        if not raw.get("sub_requests") or "confidence" not in raw["sub_requests"][0] \
                or raw["sub_requests"][0]["type"] not in TYPES:
            assert all(s.confidence < POL["thresholds"]["llm_min_confidence"] for s in c.sub_requests)

    def test_non_numeric_confidence_falls_back(self, monkeypatch):
        monkeypatch.setattr(classify, "classify_llm",
                            lambda *a, **k: classify._validate({"sub_requests": [{"type": "how_to", "confidence": "high"}]}))
        r = run_text(REQ[91], mode="llm", requester="U01")
        assert SEV[r.overall_route] >= SEV["HUMAN_REVIEW"]

    def test_deterministic_and_idempotent(self, tmp_path):
        a, b = ActionLog(tmp_path / "a.log"), ActionLog(tmp_path / "b.log")
        for rid in (91, 104, 92, 32):
            run_text(REQ[rid], req_id=rid, requester="U01", log=a)
            run_text(REQ[rid], req_id=rid, requester="U01", log=b)

        def strip(p):
            return [{k: v for k, v in json.loads(x).items() if k != "ts"} for x in p.read_text().splitlines()]
        assert strip(tmp_path / "a.log") == strip(tmp_path / "b.log")
        keys = [e["idempotency_key"] for e in strip(tmp_path / "a.log") if "idempotency_key" in e]
        assert len(keys) == len(set(keys))


# ---------------------------------------------------------------- 7. відповідь користувачу
class TestUserFacingDraft:
    INTERNAL = re.compile(r"\b(" + "|".join(sorted(RULE_SIGNALS | READ_SIGNALS, key=len, reverse=True)) + r")\b")

    def test_draft_has_no_internal_signal_ids(self, full_run):
        leaked = {i: self.INTERNAL.findall(r.draft) for i, r in full_run.items() if self.INTERNAL.search(r.draft)}
        assert not leaked

    def test_draft_never_mentions_social_engineering_or_regex(self, full_run):
        for i, r in full_run.items():
            low = r.draft.lower()
            assert "соц" not in low and "regex" not in low and "інженері" not in low, i

    def test_every_user_facing_signal_text_is_neutral(self):
        for name, phrase in USER_FACING.items():
            assert "атак" not in phrase and "підозр" not in phrase, name

    def test_draft_never_promises_access_unless_auto(self, full_run):
        for i, r in full_run.items():
            if r.overall_route != "AUTO_RESOLVE":
                assert not re.search(r"(видав|додав|надав) (тобі )?доступ", r.draft.lower()), i
