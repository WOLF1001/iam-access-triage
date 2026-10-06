"""Markdown-звіт: вхід → вихід для кожного звернення + зведення."""
from __future__ import annotations

from collections import Counter

from .pipeline import Result

ROUTE_LABEL = {
    "AUTO_RESOLVE": "AUTO — бот робить сам",
    "DOCS_REDIRECT": "DOCS — перенаправлення в документацію",
    "REROUTE": "REROUTE — не IAM, інша черга",
    "NEED_INFO": "NEED_INFO — уточнення",
    "APPROVAL_GATED": "APPROVAL — бот готує, людина апрувить",
    "HUMAN_REVIEW": "HUMAN — рішення за IAM-інженером",
    "SECURITY_ESCALATION": "SECURITY — інцидент / пейдж",
}
ORDER = list(ROUTE_LABEL)


def _short(t: str, n: int = 70) -> str:
    return t if len(t) <= n else t[: n - 1] + "…"


def _key_signal(r: Result) -> str:
    for d in r.decisions:
        strong = [x for x in d.reasons if x["signal"] != "multi_intent" and not x["signal"].startswith("type:")]
        if strong:
            top = max(strong, key=lambda x: {"SECURITY_ESCALATION": 5, "HUMAN_REVIEW": 4, "APPROVAL_GATED": 3,
                                             "NEED_INFO": 2, "REROUTE": 1, "AUTO_RESOLVE": 1,
                                             "DOCS_REDIRECT": 0, None: -1}.get(x["min_route"], 0))
            return f"`{top['signal']}` ({top['origin']})"
    d = r.decisions[0]
    return f"тип `{d.sub.type}`" + (f", дія `{d.action}`" if d.action else "")


def render(results: list[Result], *, title: str, mode: str, notes: dict[int, str] | None = None) -> str:
    notes = notes or {}
    out = [f"# {title}", "",
           f"Класифікатор: `{mode}`. Дії — **симуляція** (див. `demo/actions.log`). "
           "Requester/тред — синтетичні (у CSV їх немає), див. `demo/sample.yaml`.", ""]
    cnt = Counter(r.overall_route for r in results)
    out += ["## Зведення", "", "| Маршрут | К-сть |", "|---|---|"]
    out += [f"| {ROUTE_LABEL[k]} | {cnt.get(k, 0)} |" for k in ORDER]
    out += ["", "| № | Звернення | Маршрут | Ключовий сигнал |", "|---|---|---|---|"]
    for r in results:
        out.append(f"| {r.req_id} | {_short(r.text)} | **{r.overall_route}** | {_key_signal(r)} |")
    out.append("")

    for r in results:
        out += [f"---", f"## #{r.req_id} → {ROUTE_LABEL[r.overall_route]}", ""]
        if r.req_id in notes:
            out += [f"_Чому в вибірці: {notes[r.req_id]}_", ""]
        out += ["**Вхід**", "", f"> {r.text}", ""]
        if r.thread_redacted:
            out += [f"> _тред:_ {r.thread_redacted}", ""]
        if r.redaction_findings:
            out += [f"**Secret scanner до LLM:** знайдено `{r.redaction_findings}` → у LLM і логи пішов `[REDACTED]`.", ""]
        out += [f"**Requester:** {r.requester or '—'} · **класифікатор:** `{r.classification.classifier}`", ""]
        for i, d in enumerate(r.decisions):
            hdr = f"**Підзапит {i + 1}/{len(r.decisions)}:** " if len(r.decisions) > 1 else ""
            out += [f"{hdr}тип `{d.sub.type}` · app: `{d.primary_app or '—'}` "
                    f"(усі згадки: {d.apps or '—'}) · subject: `{d.sub.subject}` · confidence {d.sub.confidence:.2f}", ""]
            out += [f"- **Маршрут:** `{d.route}`" + (f" → далі `{d.next_route}`" if d.next_route else "")
                    + f" · пріоритет {d.priority} · risk {d.risk_score}"]
            if d.action:
                out.append(f"- **Дія:** `{d.action}` ({'виконано (SIMULATED)' if d.action_done else 'не виконано'})")
            if d.approvers:
                out.append(f"- **Апрув потрібен від:** {', '.join(d.approvers)}")
            if d.queue:
                out.append(f"- **Черга:** {d.queue}")
            if d.reasons:
                out.append("- **Чому (правила, що спрацювали):**")
                for x in d.reasons:
                    out.append(f"  - `{x['signal']}` [{x['origin']}] — {x['evidence']} → min `{x['min_route']}`. {x['reason']}")
            if d.read and d.read.facts:
                out.append("- **Read-side факти (джерело · механізм):**")
                seen = set()
                for f in d.read.facts:
                    k = (f.source, f.statement)
                    if k in seen:
                        continue
                    seen.add(k)
                    out.append(f"  - `{f.source}` · {f.mechanism}: {f.statement}")
            out.append("")
        out += ["**Чернетка відповіді користувачу**", "", "```text", r.draft, "```", ""]
        if r.internal_note:
            out += ["<details><summary>Внутрішня нотатка для рев'юера</summary>", "", "```text", r.internal_note, "```",
                    "", "</details>", ""]
        if r.actions:
            out += ["<details><summary>Записи act-side (mock)</summary>", "", "```json"]
            import json
            out += [json.dumps(a, ensure_ascii=False) for a in r.actions]
            out += ["```", "", "</details>", ""]
    return "\n".join(out)


def render_distribution(results: list[Result], mode: str) -> str:
    cnt = Counter(r.overall_route for r in results)
    total = len(results)
    out = [f"# Повний прогін: {total} звернень", "",
           f"Класифікатор: `{mode}`. У CSV немає авторів, тому для всіх звернень requester = синтетичний "
           "активний співробітник `UGEN` без особливостей (менеджер доступний, базові групи). Треди відсутні — "
           "тому «деталі в треді» коректно дають NEED_INFO.", "",
           "| Маршрут | К-сть | % |", "|---|---|---|"]
    out += [f"| {ROUTE_LABEL[k]} | {cnt.get(k, 0)} | {100 * cnt.get(k, 0) / total:.0f}% |" for k in ORDER]
    out += ["", "| № | Звернення | Маршрут | Типи | Ключовий сигнал |", "|---|---|---|---|---|"]
    for r in results:
        types = ", ".join(d.sub.type for d in r.decisions)
        out.append(f"| {r.req_id} | {_short(r.text, 60)} | {r.overall_route} | {types} | {_key_signal(r)} |")
    return "\n".join(out)
