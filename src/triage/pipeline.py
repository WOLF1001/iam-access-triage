"""Оркестрація одного звернення: redact → classify → read-side → policy → act(mock) → draft."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import act, catalog, classify, readside, respond
from .policy import GLOBAL_SIGNALS, Decision, decide, primary
from .redact import redact
from .signals import Signal, detect_missing, detect_text_signals, normalize


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

    # 3. Заземлення виходу LLM на текст звернення (ADR-010, GAP-1/GAP-2).
    #    summary і app_mentions пише LLM → довіряємо їм лише якщо вони дослівно є у зверненні.
    source = normalize(red_text + " " + (red_thread or ""))
    subs = cls.sub_requests
    multi = len(subs) > 1
    sub_texts, sub_signals, sub_mentions = [], [], []
    for sub in subs:
        grounded = bool(sub.summary.strip()) and normalize(sub.summary) in source
        st = sub.summary if (multi or mode == "rules") and grounded else red_text
        sigs = detect_text_signals(st)
        mentions = [m for m in sub.app_mentions if m.strip() and normalize(m) in source]
        dropped = [m for m in sub.app_mentions if m not in mentions]
        if dropped:
            sigs.append(Signal("llm_ungrounded", "llm", f"згадки систем, яких немає в тексті, відкинуто: {dropped}"))
        if multi and not grounded:
            sigs.append(Signal("llm_ungrounded", "llm", "summary підзапиту не з тексту → сигнали рахуються по всьому зверненню"))
        sub_texts.append(st)
        sub_signals.append(sigs)
        sub_mentions.append(mentions)
    # Підлога: кожен regex-сигнал повного тексту має потрапити хоча б в один підзапит.
    # Якщо поділ на підзапити його «загубив» — він додається до всіх (консервативно).
    covered = {x.name for sigs in sub_signals for x in sigs}
    uncovered = [x for x in full_signals if x.name not in covered and x.name not in GLOBAL_SIGNALS]
    for sigs in sub_signals:
        sigs += [Signal(x.name, x.origin, f"{x.evidence} (з повного тексту; не атрибутовано підзапиту)") for x in uncovered]

    decisions: list[Decision] = []
    for sub, sub_text, sigs, mentions in zip(subs, sub_texts, sub_signals, sub_mentions):
        # порядок app — за текстом звернення, а не за порядком, який обрала LLM
        apps = catalog.resolve_apps(sub_text + " " + " ".join(mentions))
        if not apps and multi:   # "+ інструкція як підключитись" → контекст із сусіднього підзапиту
            apps = catalog.resolve_apps(red_text)
        missing = detect_missing(sub_text if multi else red_text, has_thread)
        p_app = primary(apps)
        # Read-side checks can only raise the route, so they run on the UNION of the LLM type and the
        # deterministic rules type: the LLM must not be able to skip e.g. the System Log check by
        # calling a login problem an access request (#42 with a local model → SECURITY lost).
        det_type, _ = classify._rules_type(sub_text)
        ctx = readside.build(requester_slack, red_thread, {sub.type, det_type}, apps, {s.name for s in full_signals}, p_app)
        d = decide(sub, sub_text, red_text, sigs, full_signals, ctx, missing, apps, has_thread)
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
                  internal_note=respond.internal_note(decisions, requester=requester_email, text=red_text,
                                                        classifier=cls.classifier), actions=actions)
