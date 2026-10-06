"""Оркестрація одного звернення: redact → classify → read-side → policy → act(mock) → draft."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import act, catalog, classify, readside, respond
from .policy import Decision, decide
from .redact import redact
from .signals import Signal, detect_missing, detect_text_signals


@dataclass
class Result:
    req_id: int
    text: str
    redacted_text: str
    thread_redacted: str | None
    redaction_findings: list[str]
    requester: str | None
    classification: classify.Classification
    decisions: list[Decision]
    overall_route: str
    draft: str
    internal_note: str | None
    actions: list[dict] = field(default_factory=list)


def run_one(req_id: int, text: str, *, requester_slack: str | None, thread: str | None,
            mode: str, log: act.ActionLog | None) -> Result:
    # 1. Redaction ДО LLM і ДО логів
    red_text, f1 = redact(text)
    red_thread, f2 = redact(thread) if thread else (None, [])
    findings = f1 + f2

    # 2. Класифікація (LLM бачить лише відредагований текст)
    cls = classify.classify(red_text, red_thread, mode)

    full_signals = detect_text_signals(red_text + " " + (red_thread or ""))
    if findings:
        full_signals.append(Signal("secret_in_message", "text", f"secret scanner: {findings}"))
    has_thread = bool(thread)

    decisions: list[Decision] = []
    for sub in cls.sub_requests:
        sub_text = sub.summary if mode == "rules" else red_text
        if len(cls.sub_requests) > 1:
            sub_text = sub.summary
        apps = catalog.resolve_apps(" ".join(sub.app_mentions + [sub_text]))
        if not apps and len(cls.sub_requests) > 1:   # "+ інструкція як підключитись" → контекст із сусіднього підзапиту
            apps = catalog.resolve_apps(red_text)
        sub_signals = detect_text_signals(sub_text)
        missing = detect_missing(sub_text if len(cls.sub_requests) > 1 else red_text, has_thread)
        from .policy import primary
        p_app = primary(apps)
        ctx = readside.build(requester_slack, red_thread, {sub.type}, apps, {s.name for s in full_signals}, p_app)
        d = decide(sub, sub_text, red_text, sub_signals, full_signals, ctx, missing, apps, has_thread)
        decisions.append(d)

    if len(decisions) > 1:
        for d in decisions:
            d.reasons.append({"signal": "multi_intent", "origin": "classifier",
                              "evidence": f"{len(decisions)} підзапити", "min_route": None,
                              "reason": "Кожен підзапит маршрутизовано окремо; загальний маршрут = найсуворіший"})

    from .config import max_route
    overall = max_route(*[d.route for d in decisions])
    requester_email = decisions[0].read.requester_email if decisions and decisions[0].read else None

    actions = []
    if log:
        for i, d in enumerate(decisions):
            actions += act.execute(req_id, i, d, requester_email, log)

    return Result(req_id=req_id, text=text, redacted_text=red_text, thread_redacted=red_thread,
                  redaction_findings=findings, requester=requester_email, classification=cls,
                  decisions=decisions, overall_route=overall, draft=respond.compose(decisions),
                  internal_note=respond.internal_note(decisions), actions=actions)
