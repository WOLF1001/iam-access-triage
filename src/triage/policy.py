"""Policy engine: детермінований вибір маршруту.

Інваріанти (перевіряються тестами):
  1. Маршрут може лише ПІДНІМАТИСЬ правилами; жоден сигнал не знижує маршрут.
  2. AUTO_RESOLVE можливий лише для дії з allowlist І коли всі preconditions
     підтверджені read-side (а не текстом/LLM).
  3. Сигнали з тексту (regex) не можуть бути скасовані LLM.
  4. Бракує критичних даних → спершу NEED_INFO, навіть якщо далі потрібен апрув.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import catalog, config
from .classify import SubRequest
from .readside import ReadContext
from .signals import Signal

TYPE_REASON = {
    "how_to": "Питання 'як зробити' — відповідь має бути в KB.",
    "policy_question": "Питання про правила/ліміти — відповідь має бути в KB.",
    "access_request": "Будь-яка видача доступу за замовчуванням іде через апрув.",
    "invite_resend": "Повторний інвайт — кандидат на авто, якщо оригінальний апрув підтверджений.",
    "login_diagnostic": "Діагностика входу — read-only перевірка журналів, без змін.",
    "license_request": "Ліцензія = гроші: апрув менеджера + бюджет-власника.",
    "license_issue": "Збій ліцензії: потрібна перевірка в admin console вендора — read-side конектора в прототипі немає.",
    "limits_quota": "Підняття лімітів = витрати: апрув бюджет-власника.",
    "billing_finance": "Оплата/тарифи — не IAM, а finance/procurement.",
    "api_key_request": "API-ключ = секрет з білінгом: апрув ліда + власника платформи, видача через 1Password.",
    "secret_incident": "Робота з скомпрометованими секретами — завжди security.",
    "offboarding": "Деструктивна дія — лише людина після підтвердження HR.",
    "onboarding": "Пакет доступів для нової людини — лише після запису в HRIS, вирішує людина.",
    "integration_connector": "Нова інтеграція = новий потік даних — security review.",
    "security_policy_change": "Зміни org-wide політики — рішення security.",
    "data_export": "Вивантаження даних — потрібна правова підстава і власник даних.",
    "credential_reset": "Скидання облікових даних — тільки self-service, не через чат.",
    "usage_report": "Звіти про використання іншими людьми — приватність, вирішує людина.",
    "project_work": "Проєктна робота (міграції, DMARC) — планується, а не тікет.",
    "not_iam": "Не IAM — перенаправлення в правильну чергу.",
    "unclear": "Неясно, що просять — уточнюємо.",
}

MISSING_Q = {
    "список людей відсутній": "Хто саме ці люди (список корпоративних email)?",
    "деталі тільки в треді": "Напиши деталі тут у треді: кого/що це стосується.",
    "конкретна система/модель не названа": "Яка саме модель/тула/продукт (точна назва або посилання)?",
    "ім'я/email людини, для якої запит": "Для кого запит (ім'я та корпоративний email)?",
}
TYPE_Q = {
    "api_key_request": ["Для якої команди і задачі ключ, хто буде його власником, який місячний spend limit поставити?"],
    "access_request": ["Для якої задачі потрібен доступ і на який строк?"],
    "license_request": ["Для якої задачі потрібна ліцензія і на який строк?"],
    "limits_quota": ["Скільки потрібно, на який строк і для якої задачі?"],
}

NEEDS_APP = {"access_request", "license_request", "api_key_request", "invite_resend", "limits_quota", "license_issue"}
GLOBAL_SIGNALS = {"urgency", "prompt_pressure", "secret_in_message", "secret_compromise", "unverified_approval_claim"}
ACCESS_LIKE = {"access_request", "license_request", "api_key_request", "limits_quota", "onboarding", "integration_connector"}


@dataclass
class Decision:
    sub: SubRequest
    apps: list[str]
    primary_app: str | None
    route: str
    next_route: str | None = None
    action: str | None = None
    action_done: bool = False
    approvers: list[str] = field(default_factory=list)
    reasons: list[dict] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)
    risk_score: int = 0
    priority: str = "P3"
    kb_articles: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    queue: str | None = None
    read: ReadContext | None = None

    def to_dict(self) -> dict:
        return {
            "summary": self.sub.summary, "type": self.sub.type, "apps": self.apps, "primary_app": self.primary_app,
            "route": self.route, "next_route": self.next_route, "action": self.action, "action_done": self.action_done,
            "approvers": self.approvers, "priority": self.priority, "risk_score": self.risk_score,
            "signals": [s.to_dict() for s in self.signals], "reasons": self.reasons,
            "kb": self.kb_articles, "questions": self.questions, "queue": self.queue,
        }


CONTEXT_ONLY_APPS = {"okta", "hris"}   # згадуються як механізм/контекст ("через okta", "у HRM ще не"), не як ціль


def primary(apps: list[str]) -> str | None:
    non_idp = [a for a in apps if a not in CONTEXT_ONLY_APPS]
    return non_idp[0] if non_idp else None


def _kw_match(kw: str, low: str) -> bool:
    """Ключова фраза матчиться, якщо кожне її слово (за стемом ~5 символів) є в тексті — стійко до відмінювання."""
    return all(w[:5] in low for w in kw.lower().split())


def match_kb(text: str, app_id: str | None, sub_type: str) -> list[str]:
    low = text.lower()
    arts = config.kb()["articles"]
    hits = [aid for aid, a in arts.items() if any(_kw_match(k, low) for k in a.get("keywords", []))]
    if sub_type == "credential_reset" and "okta-self-service-reset" not in hits and "mfa" not in low and "2fa" not in low:
        hits.append("okta-self-service-reset")
    if sub_type in ("how_to", "policy_question", "credential_reset") and app_id and not hits:
        hits += [a for a in catalog.get(app_id).get("kb", []) if a in arts]
    if sub_type == "how_to" and re.search(r"апрув|підтверджувати", low):
        hits.append("access-request-process")
    return list(dict.fromkeys(hits))[:2]


def pick_queue(sub: SubRequest, sig_names: set[str], text: str) -> str:
    low = text.lower()
    if sig_names & {"security_finding", "secret_compromise", "secret_in_message", "suspicious_auth_activity"}:
        return "security"
    if sig_names & {"payment_action"} or sub.type == "billing_finance":
        return "finance" if not re.search(r"коштує|знижк|ліцензі", low) else "procurement"
    if re.search(r"статус звільнення|hr-систем", low):
        return "hr"
    if sub.type == "project_work":
        return "infra"
    if re.search(r"коштує|знижк|ліцензі", low):
        return "procurement"
    if re.search(r"анонс|ти вже закинув", low):
        return "personal"
    return "helpdesk"


def _approvers(app_id: str | None, sig_names: set[str], ctx: ReadContext) -> list[str]:
    out: list[str] = []
    spec = catalog.get(app_id) if app_id else {}
    appr = spec.get("approval", "manager")
    if "manager" in appr or "on_behalf" in sig_names:
        out.append(f"manager:{ctx.manager_email or '?'}" + ("" if ctx.manager_available else " (НЕДОСТУПНИЙ)"))
    if "owner" in appr or "financial_data" in sig_names:
        out.append(f"resource-owner:{spec.get('owner', '?')}")
    if appr == "security":
        out.append("security")
    if spec.get("cost") or "cost_impact" in sig_names:
        out.append("budget-owner")
    return list(dict.fromkeys(out))


def decide(sub: SubRequest, sub_text: str, full_text: str, text_signals_sub: list[Signal],
           text_signals_full: list[Signal], ctx: ReadContext, missing: list[str],
           apps: list[str], has_thread: bool) -> Decision:
    pol = config.policy()
    thr = pol["thresholds"]
    p_app = primary(apps)
    d = Decision(sub=sub, apps=apps, primary_app=p_app, route=pol["type_base_route"][sub.type], read=ctx)
    d.reasons.append({"signal": f"type:{sub.type}", "origin": "policy", "evidence": f"тип запиту = {sub.type}",
                      "min_route": d.route, "reason": TYPE_REASON.get(sub.type, "Базовий маршрут для цього типу")})
    if sub.type in ("not_iam", "secret_incident", "how_to", "policy_question", "credential_reset"):
        missing = []

    # --- 1. Збір сигналів: text(sub) ∪ text(global) ∪ llm ∪ read ∪ structural
    sigs: list[Signal] = list(text_signals_sub)
    sigs += [s for s in text_signals_full if s.name in GLOBAL_SIGNALS and all(x.name != s.name for x in sigs)]
    for name in sub.signals:
        if all(x.name != name for x in sigs):
            sigs.append(Signal(name, "llm", "витягнуто LLM (неперевірений сигнал)"))
    sigs += ctx.signals
    if p_app and catalog.get(p_app)["risk_tier"] == "critical" and sub.type in ACCESS_LIKE | {"invite_resend"}:
        sigs.append(Signal("critical_resource", "catalog", f"{p_app}: risk_tier=critical"))
    if sub.type in NEEDS_APP and not p_app:
        sigs.append(Signal("unknown_app", "catalog", "жодна згадка не змаплена на каталог"))
    names = {s.name for s in sigs}
    if "offboarding" in names:   # "всі доступи" для offboarding — очікуваний скоуп, а не over-granting
        sigs = [s for s in sigs if s.name != "broad_scope"]
        names.discard("broad_scope")
    if "on_behalf" in names and not ctx.subject_email:
        missing = missing + ["ім'я/email людини, для якої запит"]
    if missing:
        sigs.append(Signal("missing_critical_data", "text", "; ".join(missing)))
    if sub.confidence < thr["llm_min_confidence"]:
        sigs.append(Signal("low_confidence", "classifier", f"confidence={sub.confidence:.2f} < {thr['llm_min_confidence']}"))
    names = {s.name for s in sigs}

    # --- 2. Birthright-виняток для access_request (єдине місце, де базовий маршрут нижчий)
    if sub.type == "access_request" and p_app:
        spec = catalog.get(p_app)
        if spec.get("birthright") and ctx.preconditions.get("group_allowlisted_for_bot"):
            d.route = "AUTO_RESOLVE"
            d.action = "add_birthright_group"

    # --- 3. Approver availability — лише якщо маршрут вимагає менеджера
    if not ctx.manager_available and (sub.type in ACCESS_LIKE or "mirror_access" in names):
        sigs.append(Signal("approver_unavailable", "read", "менеджер requester'а у відпустці за HRIS, делегата немає"))
        names.add("approver_unavailable")

    # --- 4. Hard rules: тільки вгору
    for rule in pol["hard_rules"]:
        if rule["signal"] in names:
            ev = next(s for s in sigs if s.name == rule["signal"])
            d.reasons.append({"signal": rule["signal"], "origin": ev.origin, "evidence": ev.evidence,
                              "min_route": rule["min_route"], "reason": rule["reason"]})
            if rule["min_route"]:
                d.route = config.max_route(d.route, rule["min_route"])

    # --- 5. AUTO: allowlist + preconditions з read-side
    if d.route == "AUTO_RESOLVE":
        pre = dict(ctx.preconditions)
        pre["requester_is_subject"] = sub.subject == "self" and "on_behalf" not in names
        # одна entitlement на підзапит: інакше «яку саме видати автоматично» вирішував би порядок згадок
        pre["single_entitlement"] = len([a for a in apps if a not in CONTEXT_ONLY_APPS]) <= 1
        if sub.type == "invite_resend":
            d.action = "resend_invite"
            need = ["requester_is_subject", "requester_active_hris", "invite_previously_approved", "single_entitlement"]
        elif sub.type == "login_diagnostic":
            d.action = "readonly_diagnostic"
            need = ["requester_is_subject"]
            if p_app and catalog.get(p_app)["sso"] == "none":
                pre["read_side_coverage"] = False
                need.append("read_side_coverage")
        elif d.action == "add_birthright_group":
            need = ["requester_is_subject", "requester_active_hris", "app_birthright", "single_entitlement"]
        else:
            need = ["__not_in_allowlist__"]
        failed = [n for n in need if not pre.get(n)]
        if failed:
            fallback = "NEED_INFO" if failed == ["read_side_coverage"] else (
                "APPROVAL_GATED" if sub.type in ACCESS_LIKE | {"invite_resend"} else "HUMAN_REVIEW")
            d.reasons.append({"signal": "precondition_failed", "origin": "read", "evidence": ", ".join(failed),
                              "min_route": fallback, "reason": "AUTO неможливий: preconditions не підтверджені read-side"})
            d.route = fallback
            if failed == ["read_side_coverage"]:
                d.questions.append("Скинь, будь ласка, скрін помилки і приблизний час, коли не пускає.")
            d.action = None if sub.type != "login_diagnostic" else d.action
        elif sub.type == "login_diagnostic" and not (ctx.signals or [x for x in ctx.diagnosis if "подій" not in x]):
            d.route = "NEED_INFO"
            d.questions.append("Скинь, будь ласка, скрін помилки, назву системи і приблизний час, коли не пускає.")
            d.reasons.append({"signal": "diagnostic_inconclusive", "origin": "read", "evidence": "у read-side джерелах немає пояснення",
                              "min_route": "NEED_INFO", "reason": "Діагностика нічого не знайшла — не вгадуємо, просимо деталі"})
        elif d.action == "add_birthright_group" and pre.get("already_has_access"):
            d.action = None
            d.route = "DOCS_REDIRECT"
            d.reasons.append({"signal": "already_has_access", "origin": "read", "evidence": "користувач уже в групі",
                              "min_route": "DOCS_REDIRECT", "reason": "Доступ уже є → лише інструкція"})
    # read-only діагностика виконується і тоді, коли маршрут далі піднявся (вона нічого не змінює)
    if sub.type == "login_diagnostic" and d.action is None and sub.subject == "self" and ctx.diagnosis:
        d.action = "readonly_diagnostic"
    d.action_done = bool(d.action) and (d.route == "AUTO_RESOLVE" or d.action == "readonly_diagnostic")

    # --- 6. NEED_INFO як gate перед апрувом/авто
    if names & {"missing_critical_data", "unknown_app"} and d.route in ("AUTO_RESOLVE", "APPROVAL_GATED", "DOCS_REDIRECT") \
            and sub.type not in ("how_to", "policy_question", "credential_reset"):
        d.next_route = d.route if d.route != "DOCS_REDIRECT" else None
        d.route = "NEED_INFO"
        if d.action != "readonly_diagnostic":
            d.action, d.action_done = None, False
    if d.route == "NEED_INFO":
        qs = [MISSING_Q.get(m, f"Уточни: {m}.") for m in missing]
        if "unknown_app" in names and MISSING_Q["конкретна система/модель не названа"] not in qs:
            qs.insert(0, "Яка саме система/тула (точна назва або посилання)?")
        qs += [m if m.endswith("?") else f"{m}?" for m in sub.missing_info]
        qs += TYPE_Q.get(sub.type, [])
        d.questions = list(dict.fromkeys(d.questions + qs))

    # --- 7. DOCS лише якщо стаття реально існує в KB; інакше — KB-gap → людина
    d.kb_articles = match_kb(sub_text, p_app, sub.type)
    # GAP-5: перевіряємо від базового маршруту типу, а не від поточного — інакше сигнал, що підняв
    # маршрут вище DOCS (напр. «лід в курсі»), «обходив» kb_gap і маршрут ставав м'якшим.
    if not d.kb_articles and (d.route == "DOCS_REDIRECT" or pol["type_base_route"][sub.type] == "DOCS_REDIRECT"):
        d.route = config.max_route(d.route, "HUMAN_REVIEW")
        d.reasons.append({"signal": "kb_gap", "origin": "kb", "evidence": "немає статті в KB",
                          "min_route": "HUMAN_REVIEW", "reason": "Бот не генерує інструкції 'з голови': відповідає людина, стаття → в backlog KB"})

    # --- 8. Апрувери, черга, ризик, пріоритет
    if "APPROVAL_GATED" in (d.route, d.next_route) or d.route == "HUMAN_REVIEW" and sub.type in ACCESS_LIKE:
        d.approvers = _approvers(p_app, names, ctx)
    if d.route in ("REROUTE", "SECURITY_ESCALATION"):
        d.queue = pick_queue(sub, names, sub_text)
    if d.route == "SECURITY_ESCALATION":
        d.queue = "security"
    risk = 0
    if p_app:
        risk += {"low": 0, "medium": 1, "high": 2, "critical": 3}[catalog.get(p_app)["risk_tier"]]
    risk += sum(1 for n in names if n in {r["signal"] for r in pol["hard_rules"]})
    risk += sum(1 for n in names if n in pol["risk_modifiers"])
    d.risk_score = risk
    if d.route == "SECURITY_ESCALATION" or "offboarding" in names:
        d.priority = "P1"
    elif "urgency" in names:
        d.priority = "P2"
    d.signals = sigs
    return d
