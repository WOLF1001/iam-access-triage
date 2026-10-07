"""Secret scanner, що працює ДО будь-якого виклику LLM і ДО логування.

У проді — gitleaks/trufflehog-правила; тут мінімальний набір regex.
Повертаємо відредагований текст і список знахідок (тип, без значення).
"""
from __future__ import annotations

import re

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("anthropic_api_key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("openai_api_key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{20,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("password_inline", re.compile(r"(?i)(?:пароль|password|pass|pwd)\s*[:=]\s*\S+")),
    # password in prose: «пароль від тули Qwerty123», «password is Hunter2024!» — a token with letters AND digits
    # within a few words after the keyword. Over-redaction is the safe side: it escalates to security.
    ("password_prose", re.compile(r"(?i)(?:пароль|password)(?:\s+[^\s]+){0,3}?\s+(?:—\s+)?"
                                  r"(?=[^\s@/]*\d)(?=[^\s@/]*[a-zа-яіїєґ])[^\s@/]{8,}")),
]


def redact(text: str) -> tuple[str, list[str]]:
    findings: list[str] = []
    out = text
    for name, pat in PATTERNS:
        if pat.search(out):
            findings.append(name)
            out = pat.sub(f"[REDACTED:{name}]", out)
    return out, findings
