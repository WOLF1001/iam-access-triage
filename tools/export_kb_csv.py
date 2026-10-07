#!/usr/bin/env python3
"""config/kb.yaml → notion/iam_kb.csv для імпорту в Notion (Import → CSV → нова база).

Перша колонка (Title) стає title-властивістю бази. article_id — ключ, на який
посилаються config/app_catalog.yaml і policy (DOCS лише на існуючі article_id).
Status=Published: бот бере лише такі статті; нові статті з kb_gap прийдуть як Draft.

    python tools/export_kb_csv.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from triage import config  # noqa: E402

OUT = ROOT / "notion" / "iam_kb.csv"
REVIEWED = "2026-10-07"


def main() -> None:
    apps_by_article: dict[str, list[str]] = {}
    for app_id, spec in config.catalog().items():
        for art in spec.get("kb", []):
            apps_by_article.setdefault(art, []).append(app_id)

    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Title", "article_id", "Summary", "Keywords", "Apps", "Status", "Owner", "Last reviewed"])
        for aid, a in config.kb()["articles"].items():
            w.writerow([a["title"], aid, a["summary"], ", ".join(a.get("keywords", [])),
                        ", ".join(apps_by_article.get(aid, [])), "Published", "IAM", REVIEWED])
    print(f"{OUT.relative_to(ROOT)}: {len(config.kb()['articles'])} статей")


if __name__ == "__main__":
    main()
