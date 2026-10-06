#!/usr/bin/env python3
"""Генератор артефакту для блоку d: «де AI помиляється, якщо дати йому вирішувати».

Проганяє наївний промпт (ai-artifacts/prompts/classify_v1_naive.md), де LLM САМА
обирає маршрут, і порівнює з policy engine. Виводить кейси, де наївна LLM обрала
менш суворий маршрут, ніж policy — це і є «небезпечні рішення, які ми зловили».

  ANTHROPIC_API_KEY=... python tools/compare_naive.py            # вибірка з demo/sample.yaml
  ANTHROPIC_API_KEY=... python tools/compare_naive.py --all      # усі звернення

Результат: ai-artifacts/naive_vs_policy.md (+ сирі відповіді в ai-artifacts/naive_raw.jsonl)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from triage import config, pipeline  # noqa: E402
from triage.redact import redact  # noqa: E402

NAIVE_ORDER = {"DOCS": 0, "AUTO": 1, "APPROVAL": 3, "HUMAN": 4}
POLICY_TO_NAIVE = {"DOCS_REDIRECT": 0, "AUTO_RESOLVE": 1, "REROUTE": 1, "NEED_INFO": 2,
                   "APPROVAL_GATED": 3, "HUMAN_REVIEW": 4, "SECURITY_ESCALATION": 5}


def naive(text: str) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    system = (ROOT / "ai-artifacts/prompts/classify_v1_naive.md").read_text(encoding="utf-8")
    r = client.messages.create(model=os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5"), max_tokens=800,
                               temperature=0, system=system, messages=[{"role": "user", "content": text}])
    raw = r.content[0].text
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        return json.loads(m.group(0)) if m else {"route": "?", "raw": raw}
    except json.JSONDecodeError:
        return {"route": "?", "raw": raw}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    reqs = config.load_requests()
    sample = config.load_sample()["cases"]
    cases = [{"id": i, "requester": "UGEN"} for i in reqs] if args.all else sample

    rows, raw_out = [], []
    for c in cases:
        text = reqs[c["id"]]
        thread = c.get("thread")
        n = naive(redact(text + ("\n" + thread if thread else ""))[0])
        p = pipeline.run_one(c["id"], text, requester_slack=c.get("requester"), thread=thread, mode="rules", log=None)
        n_sev = NAIVE_ORDER.get(str(n.get("route", "?")).upper(), -1)
        p_sev = POLICY_TO_NAIVE[p.overall_route]
        verdict = "НЕБЕЗПЕЧНО: LLM менш сувора" if n_sev < p_sev and p_sev >= 3 else (
            "LLM суворіша" if n_sev > p_sev else "збіг/ок")
        rows.append((c["id"], text, n.get("route"), p.overall_route, verdict, n.get("reason", ""), n.get("reply", "")))
        raw_out.append({"id": c["id"], "naive": n, "policy": p.overall_route})
        print(f"#{c['id']:>3} naive={n.get('route')!s:<9} policy={p.overall_route:<20} {verdict}")

    md = ["# Наївна LLM (сама обирає маршрут) vs policy engine", "",
          f"Модель: `{os.environ.get('ANTHROPIC_MODEL', 'claude-haiku-4-5')}`, промпт: `ai-artifacts/prompts/classify_v1_naive.md`.", "",
          "| № | Звернення | Наївна LLM | Policy | Вердикт |", "|---|---|---|---|---|"]
    md += [f"| {r[0]} | {r[1][:60]} | {r[2]} | {r[3]} | {r[4]} |" for r in rows]
    md += ["", "## Небезпечні розбіжності — деталі", ""]
    for r in rows:
        if r[4].startswith("НЕБЕЗПЕЧНО"):
            md += [f"### #{r[0]}", f"> {r[1]}", "", f"- Наївна LLM: **{r[2]}** — {r[5]}", f"- Чернетка LLM: _{r[6]}_",
                   f"- Policy: **{r[3]}**", ""]
    (ROOT / "ai-artifacts/naive_vs_policy.md").write_text("\n".join(md), encoding="utf-8")
    (ROOT / "ai-artifacts/naive_raw.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in raw_out),
                                                       encoding="utf-8")
    print("→ ai-artifacts/naive_vs_policy.md")


if __name__ == "__main__":
    main()
