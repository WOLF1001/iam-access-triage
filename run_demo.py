#!/usr/bin/env python3
"""Запуск демо.

  python run_demo.py                        # вибірка з demo/sample.yaml, класифікатор rules (без ключа)
  python run_demo.py --classifier llm       # Claude API (потрібен ANTHROPIC_API_KEY), відповіді кешуються
  python run_demo.py --classifier replay    # тільки з кешу, без мережі — відтворюваний прогін
  python run_demo.py --all                  # + розподіл маршрутів по всіх зверненнях датасету
  python run_demo.py --ids 32 46            # конкретні звернення
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from triage import config, pipeline, report  # noqa: E402
from triage.act import ActionLog  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--classifier", choices=["rules", "llm", "replay"], default="rules")
    ap.add_argument("--all", action="store_true", help="також прогнати всі звернення датасету")
    ap.add_argument("--ids", type=int, nargs="*")
    args = ap.parse_args()

    requests = config.load_requests()
    sample = config.load_sample()
    cases = sample["cases"]
    if args.ids:
        by_id = {c["id"]: c for c in cases}
        cases = [by_id.get(i, {"id": i, "requester": None}) for i in args.ids]

    suffix = "" if args.classifier == "rules" else f"_{args.classifier}"
    log = ActionLog(config.DEMO / f"actions{suffix}.log")
    results = []
    for c in cases:
        r = pipeline.run_one(c["id"], requests[c["id"]], requester_slack=c.get("requester"),
                             thread=c.get("thread"), mode=args.classifier, log=log)
        results.append(r)
        print(f"#{r.req_id:>3}  {r.overall_route:<20} {r.text[:70]}")

    notes = {c["id"]: c.get("why_picked", "") for c in sample["cases"]}
    md = report.render(results, title="Демо: AI-assisted IAM triage", mode=args.classifier, notes=notes)
    out = config.DEMO / f"output{suffix}.md"
    out.write_text(md, encoding="utf-8")
    (config.DEMO / f"output{suffix}.jsonl").write_text(
        "\n".join(json.dumps({"id": r.req_id, "route": r.overall_route,
                              "classification": r.classification.to_dict(),
                              "decisions": [d.to_dict() for d in r.decisions],
                              "draft": r.draft}, ensure_ascii=False) for r in results), encoding="utf-8")
    print(f"\n→ {out.relative_to(config.ROOT)}  ·  {log.path.relative_to(config.ROOT)}")

    if args.all:
        full = [pipeline.run_one(i, t, requester_slack="UGEN", thread=None, mode=args.classifier, log=None)
                for i, t in requests.items()]
        p = config.DEMO / f"full_run{suffix}.md"
        p.write_text(report.render_distribution(full, args.classifier), encoding="utf-8")
        print(f"→ {p.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
