"""Read-side: звідки бот бере сигнали для рішення.

Кожен факт несе source + mechanism, щоб у звіті було видно, ЯКИМ механізмом
отримано сигнал і наскільки йому можна довіряти. Жодне джерело не є повним:
  Slack  — хто написав (але не хто ця людина в HR-сенсі)
  HRIS   — статус/менеджер/відділ/відпустки (але не доступи)
  Okta   — SSO-призначення і System Log (але не non-SSO SaaS)
  1Password — хто має доступ до секретів і хто їх відкривав (але не де вони вживаються)
  GWS    — пошта/групи/сторонні OAuth-апки (з затримкою)
У проді кожен мок замінюється клієнтом з тим самим інтерфейсом.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from . import catalog, config
from .signals import Signal

TODAY = "2026-10-06"


@dataclass
class Fact:
    source: str
    mechanism: str
    statement: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class ReadContext:
    requester_email: str | None = None
    requester_verified: bool = False
    requester_active: bool = False
    manager_email: str | None = None
    manager_available: bool = True
    subject_email: str | None = None
    facts: list[Fact] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)
    preconditions: dict[str, bool] = field(default_factory=dict)
    diagnosis: list[str] = field(default_factory=list)
    dry_run_plan: list[dict] = field(default_factory=list)

    def add(self, source: str, mechanism: str, statement: str):
        self.facts.append(Fact(source, mechanism, statement))

    def sig(self, name: str, evidence: str):
        if not any(s.name == name and s.origin == "read" for s in self.signals):
            self.signals.append(Signal(name, "read", evidence))


def _hris(email: str | None) -> dict | None:
    if not email:
        return None
    return next((e for e in config.mock("hris")["employees"] if e["email"] == email), None)


def _okta_user(email: str | None) -> dict | None:
    return config.mock("okta")["users"].get(email or "")


def _on_leave(emp: dict) -> bool:
    lv = emp.get("leave")
    return bool(lv and lv["from"] <= TODAY <= lv["to"])


def identify_requester(ctx: ReadContext, slack_id: str | None) -> None:
    slack = config.mock("slack_users")
    u = slack["users"].get(slack_id or "")
    if not u:
        ctx.add("slack", "users.info(event.user)", f"Slack user {slack_id} не знайдений")
        ctx.sig("requester_not_verified", "Slack user не знайдений")
        return
    ctx.requester_email = u["email"]
    if u["is_stranger"] or u["team_id"] != slack["home_team_id"]:
        ctx.add("slack", "users.info → is_stranger/team_id", f"{u['email']} — зовнішній користувач (Slack Connect)")
        ctx.sig("requester_not_verified", "Slack Connect / зовнішній workspace")
        return
    emp = _hris(u["email"])
    if not emp:
        ctx.add("hris", "GET /employees?email=", f"{u['email']} відсутній у HRIS")
        ctx.sig("requester_not_verified", "немає в HRIS")
        return
    ctx.requester_verified = True
    ctx.requester_active = emp["status"] == "active"
    ctx.manager_email = emp.get("manager")
    ctx.add("hris", "GET /employees?email= (polling snapshot)",
            f"requester {emp['name']} <{emp['email']}>: status={emp['status']}, dept={emp['department']}, manager={emp['manager']}")
    mgr = _hris(emp.get("manager"))
    if mgr and _on_leave(mgr):
        ctx.manager_available = False
        lv = mgr["leave"]
        ctx.add("hris", "GET /employees/{manager}/time-off",
                f"менеджер {mgr['name']} у відпустці {lv['from']}..{lv['to']}, делегат: {lv['delegate'] or 'не призначений'}")
    ou = _okta_user(u["email"])
    if ou:
        ctx.add("okta", "GET /api/v1/users/{id}, /groups, /appLinks",
                f"Okta status={ou['status']}, groups={ou['groups']}, apps={ou['apps']}")


def _extract_email(text: str | None) -> str | None:
    if not text:
        return None
    m = re.search(r"[\w.\-]+@[\w.\-]+", text)
    return m.group(0) if m else None


def check_offboarding(ctx: ReadContext, thread: str | None) -> None:
    subj = _extract_email(thread)
    if not subj:
        ctx.add("—", "—", "суб'єкт offboarding не визначений (немає імені/email у зверненні)")
        return
    ctx.subject_email = subj
    emp = _hris(subj)
    if not emp:
        ctx.sig("source_conflict", f"{subj} немає в HRIS")
        return
    ctx.add("hris", "GET /employees?email=",
            f"subject {emp['name']}: status={emp['status']}, termination_date={emp['termination_date']}")
    if emp["status"] == "active" and not emp["termination_date"]:
        ctx.sig("source_conflict", "звернення каже 'останній день', HRIS: active без termination_date")
        ctx.diagnosis.append("HRIS не підтверджує звільнення — або HR ще не вніс, або запит некоректний/зловмисний. "
                             "Без підтвердження HR деструктивні дії не виконуються.")
    # Будуємо dry-run план по всіх джерелах — для людини, що вирішуватиме
    ou = _okta_user(subj)
    if ou:
        ctx.add("okta", "GET /users/{id}/appLinks, /groups", f"SSO apps={ou['apps']}, groups={ou['groups']}")
        ctx.dry_run_plan.append({"system": "okta", "would_call": "POST /api/v1/users/{id}/lifecycle/suspend",
                                 "effect": f"припинить SSO-доступ до {len(ou['apps'])} apps; сесії — DELETE /users/{{id}}/sessions"})
    vaults = config.mock("onepassword")["vault_access"].get(subj, [])
    if vaults:
        ctx.add("1password", "SCIM bridge: group memberships", f"vaults={vaults}")
        ctx.dry_run_plan.append({"system": "1password", "would_call": "SCIM: deactivate user",
                                 "effect": f"доступ до vaults {vaults} закриється; "
                                           "АЛЕ секрети в shared vaults, які людина бачила, треба ротувати (рішення власників)"})
    g = config.mock("gws")["users"].get(subj)
    if g:
        ctx.add("gws", "Directory API users.get + Reports API token audit",
                f"groups={g['groups']}, owned_files={g['drive_owned_files']}, third-party OAuth={g['oauth_third_party_apps']}")
        ctx.dry_run_plan.append({"system": "google_workspace", "would_call": "users.update(suspended=true) + Data Transfer API",
                                 "effect": f"передати {g['drive_owned_files']} файлів менеджеру; відкликати OAuth-токени {g['oauth_third_party_apps']}"})
    non_sso = [v for v in vaults if v in ("Market-Intel-Tools", "Meta-Ads-Billing")]
    if non_sso:
        ctx.dry_run_plan.append({"system": "non-SSO SaaS (manual)", "would_call": "—",
                                 "effect": f"за назвами vaults {non_sso} людина ймовірно має локальні акаунти/спільні креди "
                                           "поза Okta — список неповний, перевірка вручну"})


def check_login(ctx: ReadContext, app_ids: list[str]) -> None:
    email = ctx.requester_email
    logs = [e for e in config.mock("okta")["system_log"] if e.get("target") == email]
    ctx.add("okta", "GET /api/v1/logs?filter=target.alternateId eq \"{email}\"&since=-72h",
            f"{len(logs)} подій за 72 год")
    fails = [e for e in logs if e["eventType"] == "user.session.start" and e["outcome"] == "FAILURE"
             and e.get("reason") == "INVALID_CREDENTIALS"]
    locks = [e for e in logs if e["eventType"] == "user.account.lock"]
    foreign = {e["client_ip"] for e in fails if not str(e.get("geo", "")).startswith("UA")}
    if locks and foreign:
        ctx.sig("suspicious_auth_activity",
                f"{len(fails)} невдалих входів з {sorted(foreign)} + {len(locks)} блокувань акаунта, усі ввечері")
        ctx.diagnosis.append("Акаунт блокується ввечері через серію невдалих входів з IP, що не належить користувачу "
                             f"({', '.join(sorted(foreign))}, Tor). Користувач бачить наслідок (LOCKED_OUT), а не причину.")
    removals = [e for e in logs if e["eventType"] == "group.user_membership.remove"]
    for r in removals:
        ctx.sig("regrant_needed", f"{r['group']} знято: {r['actor']}")
        ctx.diagnosis.append(f"Доступ знято {r['published'][:10]} автоматично: «{r['reason']}». Це не збій — "
                             "так спрацював mover-процес. Повернення доступу = нова видача з апрувом власника.")
    if not logs:
        ctx.diagnosis.append("В Okta System Log подій по користувачу немає — проблема, ймовірно, на боці самого застосунку.")


def check_invite(ctx: ReadContext, app_ids: list[str]) -> None:
    """resend_invite — авто лише якщо апрув (з журналу апрувів, не з тексту) прив'язаний саме до
    цієї людини і цього app і не старший за вікно повторної відправки (GAP-3)."""
    ctx.preconditions["invite_previously_approved"] = False
    inv = config.mock("asana")["pending_invites"].get(ctx.requester_email or "")
    if "asana" not in app_ids or not inv:
        return
    appr = config.mock("approvals")["approvals"].get(inv["approval_ref"])
    ctx.add("asana", "GET /workspaces/{id}/memberships + pending invites",
            f"інвайт від {inv['invited_at'][:10]}, expired={inv['expired']}, approval_ref={inv['approval_ref']}")
    if not appr:
        ctx.add("approval-log", "lookup approval_ref", f"{inv['approval_ref']} не знайдено")
        return
    ctx.add("approval-log", "lookup approval_ref",
            f"апрув {inv['approval_ref']}: subject={appr['subject']}, app={appr['app']}, "
            f"{appr['approved_by']} {appr['approved_at'][:10]} via {appr['via']}")
    max_days = config.policy()["thresholds"]["resend_max_age_days"]
    age = (date.fromisoformat(TODAY) - date.fromisoformat(appr["approved_at"][:10])).days
    problems = []
    if appr.get("subject") != ctx.requester_email:
        problems.append(f"апрув на іншу людину ({appr.get('subject')})")
    if appr.get("app") != "asana":
        problems.append(f"апрув на інший app ({appr.get('app')})")
    if age > max_days:
        problems.append(f"апрув старший за {max_days} дн. ({age} дн.)")
    if problems:
        ctx.add("approval-log", "binding check", "апрув НЕ підходить: " + "; ".join(problems))
        return
    ctx.preconditions["invite_previously_approved"] = True


def check_birthright(ctx: ReadContext, app_id: str) -> None:
    spec = catalog.get(app_id)
    ou = _okta_user(ctx.requester_email) or {"groups": []}
    grp = spec.get("okta_group")
    ctx.preconditions["app_birthright"] = bool(spec.get("birthright"))
    ctx.preconditions["already_has_access"] = bool(grp and grp in ou["groups"])
    allowlisted = grp in config.mock("okta")["groups_allowlisted_for_bot"]
    ctx.preconditions["group_allowlisted_for_bot"] = allowlisted
    if grp:
        ctx.add("okta", "GET /users/{id}/groups",
                f"{'вже в групі' if ctx.preconditions['already_has_access'] else 'не в групі'} {grp}; "
                f"група {'в' if allowlisted else 'НЕ в'} allowlist бота")


def check_sod(ctx: ReadContext, app_id: str) -> None:
    """SoD: the requester must not be an approver of the resource they ask for (no self-approval)."""
    role = catalog.get(app_id).get("owner")
    holders = config.mock("owners")["roles"].get(role or "", [])
    if ctx.requester_email and ctx.requester_email in holders:
        ctx.add("role-directory", "lookup owner role", f"{ctx.requester_email} обіймає роль {role} — апрувер ресурсу {app_id}")
        ctx.sig("sod_conflict", f"автор — апрувер ресурсу ({role}); самопогодження неможливе")


def build(slack_id: str | None, thread: str | None, types: set[str], app_ids: list[str],
          text_signal_names: set[str], primary_app: str | None = None) -> ReadContext:
    ctx = ReadContext()
    identify_requester(ctx, slack_id)
    ctx.preconditions["requester_active_hris"] = ctx.requester_active
    if "offboarding" in types or "offboarding" in text_signal_names:
        check_offboarding(ctx, thread)
    if "login_diagnostic" in types:
        check_login(ctx, app_ids)
    if "invite_resend" in types:
        check_invite(ctx, app_ids)
    if "access_request" in types and primary_app:
        check_birthright(ctx, primary_app)
    if primary_app and types & {"access_request", "license_request", "api_key_request", "limits_quota", "invite_resend"}:
        check_sod(ctx, primary_app)
    if "hris_bypass" in text_signal_names:
        ctx.add("hris", "GET /employees?start_date>=today-7",
                "суб'єкта (нову людину) не можна знайти в HRIS — ім'я не вказане, запису немає; перевірити неможливо")
    return ctx
