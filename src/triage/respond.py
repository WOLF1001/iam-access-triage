"""Чернетки відповідей користувачу + внутрішня нотатка для рев'юера.

Відповіді збираються з шаблонів і статей KB, а не генеруються LLM вільно:
бот не може пообіцяти доступ, якого policy не дозволила, або вигадати інструкцію.
Формулювання для користувача нейтральні: ми не пишемо «підозрюємо соц. інженерію»,
щоб не навчати атакуючого, що саме спрацювало.
"""
from __future__ import annotations

from . import catalog, config
from .policy import Decision

USER_FACING = {
    "mirror_access": "доступи видаємо під конкретну задачу, а не «як у колеги» — так менше зайвих прав",
    "broad_scope": "запит дуже широкий, тож розберемо його на конкретні системи разом",
    "privileged_access": "це адміністративна роль, її погоджує власник системи",
    "hris_bypass": "доступи новим людям видаються після появи запису в HR-системі — так вони коректно і відкличуться",
    "offboarding": "блокування доступів робимо після підтвердження від HR, щоб не заблокувати не ту людину",
    "source_conflict": "дані в наших системах поки не збігаються з запитом — IAM-інженер звірить їх",
    "pii_request": "персональні дані співробітників/контактів ми не вивантажуємо через бот",
    "security_policy_change": "це зміна безпекової політики для всієї організації — її розглядає security",
    "third_party_connector": "нові конектори проходять перевірку безпеки (які дані і куди йдуть)",
    "shared_credential": "спільні логіни — це ризик, тож тут потрібне рішення по самому сервісу",
    "external_party": "доступи підрядникам видаються з договором, власником і строком дії",
    "approver_unavailable": "твій лід зараз у відпустці, а заміщення в HR-системі не вказане",
    "requester_not_verified": "не вдалося автоматично підтвердити твій обліковий запис",
    "low_confidence": "хочу, щоб запит точно зрозумів інженер",
    "kb_gap": "готової інструкції поки немає — інженер відповість і ми її додамо",
    "regrant_needed": "доступ зняли не через збій, тож повернення погоджує власник",
    "financial_data": "доступ до фінансових даних погоджує власник ресурсу",
}

APPROVER_LABEL = {"manager": "твій лід", "resource-owner": "власник системи", "budget-owner": "власник бюджету",
                  "security": "security"}


def _approver_text(approvers: list[str]) -> str:
    parts = []
    for a in approvers:
        role = a.split(":")[0]
        parts.append(APPROVER_LABEL.get(role, role))
    return ", ".join(dict.fromkeys(parts))


def _kb_lines(ids: list[str]) -> list[str]:
    arts = config.kb()["articles"]
    return [f"{arts[i]['summary']}\n   → {arts[i]['title']}: {arts[i]['url']}" for i in ids]


def draft_for(d: Decision) -> str:
    app = catalog.get(d.primary_app)["name"] if d.primary_app else None
    reasons = [USER_FACING[r["signal"]] for r in d.reasons if r["signal"] in USER_FACING]
    why = (" — " + reasons[0]) if reasons else ""
    q = config.kb()["reroute_queues"]

    if d.route == "DOCS_REDIRECT":
        return "\n".join(_kb_lines(d.kb_articles)) or "Інструкція в KB."
    if d.route == "AUTO_RESOLVE":
        if d.action == "add_birthright_group":
            body = f"Готово: додав тебе до групи {catalog.get(d.primary_app).get('okta_group')} ({app})."
        elif d.action == "resend_invite":
            body = f"Надіслав інвайт у {app} ще раз (попередній погоджений апрув досі дійсний). Прийми його протягом 7 днів."
        elif d.action == "readonly_diagnostic":
            body = "Перевірив журнали входу. " + " ".join(d.read.diagnosis if d.read else [])
        else:
            body = "Готово."
        kb = _kb_lines(d.kb_articles)
        return body + ("\n" + "\n".join(kb) if kb else "")
    if d.route == "NEED_INFO":
        lines = ["Щоб обробити запит, мені бракує кількох деталей:"] + [f"• {x}" for x in d.questions]
        if d.next_route == "APPROVAL_GATED":
            lines.append("Як тільки уточниш — сформую запит на апрув"
                         + (f" ({_approver_text(d.approvers)})" if d.approvers else "") + ".")
        if any(r["signal"] == "unverified_approval_claim" for r in d.reasons):
            lines.append("P.S. Погодження в тексті повідомлення не рахується — апрувер отримає кнопку в Slack.")
        if d.action == "readonly_diagnostic" and d.read and d.read.diagnosis:
            lines.insert(0, "Перевірив журнали входу: " + " ".join(d.read.diagnosis))
        return "\n".join(lines)
    if d.route == "APPROVAL_GATED":
        lines = []
        if d.action == "readonly_diagnostic" and d.read and d.read.diagnosis:
            lines.append("Перевірив журнали входу. " + " ".join(d.read.diagnosis))
        lines.append(f"Підготував запит на доступ{(' до ' + app) if app else ''}"
                     f"{' (мінімальна роль: ' + catalog.get(d.primary_app)['least_privilege_role'] + ')' if d.primary_app and catalog.get(d.primary_app).get('least_privilege_role') else ''}. "
                     f"Потрібне погодження: {_approver_text(d.approvers)}. Після апруву видам автоматично і напишу тут.")
        if any(r["signal"] == "unverified_approval_claim" for r in d.reasons):
            lines.append("Погодження в тексті повідомлення не рахується — апрувер отримає кнопку в Slack.")
        return "\n".join(lines)
    if d.route == "REROUTE":
        qq = q.get(d.queue or "helpdesk")
        if d.queue == "personal":
            return "(Не тікет — особисте повідомлення IAM-інженеру. Бот не відповідає, лише позначає для людини.)"
        return f"Це не до IAM — цим займається {qq['name']} ({qq['channel']}). Я переслав туди твоє повідомлення з посиланням на цей тред."
    if d.route == "HUMAN_REVIEW":
        tail = (". " + reasons[0][0].upper() + reasons[0][1:]) if reasons else ""
        return f"Передав запит IAM-інженеру{tail}. Відповідь буде в цьому треді." + \
               (f" Пріоритет: {d.priority}." if d.priority != "P3" else "")
    if d.route == "SECURITY_ESCALATION":
        names = {r["signal"] for r in d.reasons}
        if names & {"secret_compromise", "secret_in_message"}:
            return ("Передав у security з пріоритетом P1. Важливо: видалення нотатки в 1Password НЕ відкликає ключ — "
                    "його треба відкликати у провайдера і випустити новий, цим зараз займеться security. "
                    "Нотатку поки не чіпай (вона потрібна для розслідування), і не пересилай ключ у чати — "
                    "якщо він є в цьому треді, я його приховав, а повідомлення варто видалити.")
        if "suspicious_auth_activity" in names:
            return ("Подивився журнали: твій акаунт блокується через серію невдалих спроб входу не з твоїх пристроїв. "
                    "Передав у security (P1). Поки що: не підтверджуй push-запити Okta Verify, яких ти не ініціював, "
                    "і чекай повідомлення від security щодо зміни пароля.")
        if "security_finding" in names:
            return ("Це не IAM-запит, але важливий: передав у security з пріоритетом P1. "
                    "Будь ласка, не пересилай звіт пентесту у відкриті канали — тільки в #security-incidents.")
        return "Передав у security з пріоритетом P1."
    return ""


def compose(decisions: list[Decision]) -> str:
    if len(decisions) == 1:
        return draft_for(decisions[0])
    parts = []
    for i, d in enumerate(decisions, 1):
        parts.append(f"{i}) {d.sub.summary}:\n{draft_for(d)}")
    return "\n\n".join(parts)


def internal_note(decisions: list[Decision]) -> str | None:
    lines = []
    for d in decisions:
        if d.route not in ("HUMAN_REVIEW", "SECURITY_ESCALATION", "APPROVAL_GATED"):
            continue
        lines.append(f"[{d.route} {d.priority}] {d.sub.summary}")
        for r in d.reasons:
            lines.append(f"  - {r['signal']} ({r['origin']}): {r['evidence']}")
        if d.read and d.read.diagnosis:
            lines += [f"  * діагноз: {x}" for x in d.read.diagnosis]
        if d.read and d.read.dry_run_plan:
            lines.append("  * dry-run план (НЕ виконано):")
            lines += [f"      {p['system']}: {p['effect']}" for p in d.read.dry_run_plan]
    return "\n".join(lines) or None
