"""Класифікатори: структурований розбір звернення.

Три режими:
  rules  — детермінований keyword-baseline (працює без ключа; також — fallback,
           якщо LLM недоступна, і точка порівняння для LLM)
  llm    — Claude через tool use зі строгою JSON-схемою; відповіді кешуються
  replay — лише з кешу (cache/llm_cache.json), без мережі — для відтворюваності

Вихід класифікатора НЕ містить маршруту. Маршрут — справа policy engine.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field

from . import config

TYPES = list(config.policy()["type_base_route"].keys())
LLM_SIGNALS = [
    "secret_compromise", "security_finding", "offboarding", "hris_bypass", "mirror_access", "broad_scope",
    "privileged_access", "credential_reset", "shared_credential", "pii_request", "security_policy_change",
    "third_party_connector", "external_party", "financial_data", "payment_action", "unverified_approval_claim",
    "on_behalf", "urgency", "prompt_pressure", "cost_impact",
]


@dataclass
class SubRequest:
    summary: str
    type: str
    app_mentions: list[str] = field(default_factory=list)
    subject: str = "self"                 # self | other | multiple | unknown
    requested_scope: str | None = None
    missing_info: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Classification:
    is_iam: bool
    sub_requests: list[SubRequest]
    classifier: str
    raw: dict | None = None

    def to_dict(self) -> dict:
        return {"is_iam": self.is_iam, "classifier": self.classifier,
                "sub_requests": [s.to_dict() for s in self.sub_requests]}


# ---------------------------------------------------------------------------
# Rules baseline
# ---------------------------------------------------------------------------
SPLIT_RE = re.compile(r"\s\+\s|,?\s+і ще\s+|\.\s+і ще\s+|,\s+і чи\s+|,\s+і питання\s+|\.\s+і\s+(?=треба)")

# порядок важливий: перший збіг перемагає
TYPE_RULES: list[tuple[str, list[str]]] = [
    ("secret_incident", [r"злит", r"скомпрометов"]),
    ("not_iam", [r"монітор", r"замовити нову техніку", r"масштабується", r"анонс", r"пентест",
                 r"безпековий тест", r"хелпдеск тупить"]),
    ("data_export", [r"вивантажити", r"експорт", r"списки людей"]),
    ("usage_report", [r"хто юзає", r"порахувати кількість", r"статус звільнення"]),
    ("offboarding", [r"останній день", r"заблокуйте всі доступи"]),
    ("onboarding", [r"нова людина", r"нового підрядника", r"заводимо нового"]),
    ("credential_reset", [r"скинути пароль", r"налаштувати 2fa", r"налаштувати mfa", r"як налаштувати mfa"]),
    ("security_policy_change", [r"always-allow"]),
    ("project_work", [r"міграці\w* домену", r"dmarc", r"на новий домен", r"сервісних пошт"]),
    ("how_to", [r"^як ", r"як мені", r"як правильно", r"як працює", r"як заходити", r"як підключити", r"як створити",
                r"підкажи", r"інструкці", r"гайд", r"поясніть", r"що таке", r"що для цього треба", r"як отримати",
                r"яка схема", r"як влаштовані"]),
    ("integration_connector", [r"конектор", r"\bmcp\b", r"підключаю"]),
    ("invite_resend", [r"інвайт.*деактив", r"надішліть ще раз"]),
    ("api_key_request", [r"api-ключ", r"api ключ", r"\bключ", r"токени до", r"\bpat\b"]),
    ("policy_question", [r"питання по лімітах", r"мені казали що є обмеження"]),
    ("billing_finance", [r"поповн", r"карту", r"коштує", r"знижк", r"витрати", r"тариф", r"ніхто не користується"]),
    ("limits_quota", [r"ліміт", r"квот", r"токени", r"extra usage", r"кредит"]),
    ("license_issue", [r"ліцензія не активув", r"щось з підпискою", r"підписка .*злетіла"]),
    ("license_request", [r"ліцензі", r"преміум", r"підписк", r"місця"]),
    ("login_diagnostic", [r"не можу зайти", r"не заходить", r"не пускає", r"викидає", r"залогін", r"вибило",
                          r"релогін", r"пропав доступ", r"глючить", r"вилітає", r"заблокован", r"не працює доступ",
                          r"проблеми", r"\bзник", r"не переносяться", r"вимикається", r"порожньо", r"недоступні"]),
    ("access_request", [r"доступ", r"інвайт", r"дайте", r"видати", r"додайте", r"адмін", r"права", r"акаунт",
                        r"пошерити", r"підключіть", r"апрувніть", r"апрув", r"завести", r"заведіть", r"схвалив",
                        r"підтвердити", r"перегляд", r"можна"]),
    ("policy_question", [r"чому", r"питання по", r"що з ними робити", r"це баг чи фіча", r"для чого", r"чи є"]),
]


def _rules_type(text: str) -> tuple[str, float]:
    from .signals import normalize
    low = normalize(text)
    for t, pats in TYPE_RULES:
        if any(re.search(p, low) for p in pats):
            return t, 0.8
    return "unclear", 0.4


def classify_rules(text: str, thread: str | None = None) -> Classification:
    parts = [p.strip(" ,.") for p in SPLIT_RE.split(text) if p and p.strip(" ,.")]
    subs = []
    for p in parts:
        t, conf = _rules_type(p)
        subj = "other" if re.search(r"колез|колег\w* акаунт|людям|людини|нова людина|новенькій|співробітнику|підрядник", p.lower()) else "self"
        subs.append(SubRequest(summary=p, type=t, subject=subj, confidence=conf))
    is_iam = not all(s.type == "not_iam" for s in subs)
    return Classification(is_iam=is_iam, sub_requests=subs, classifier="rules")


# ---------------------------------------------------------------------------
# LLM (Claude, tool use)
# ---------------------------------------------------------------------------
TOOL_SCHEMA = {
    "name": "record_triage",
    "description": "Записати структурований розбір звернення. НЕ обирати маршрут і НЕ вирішувати, чи видавати доступ.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_iam": {"type": "boolean", "description": "Чи стосується звернення доступів/ідентичності/секретів/ліцензій/лімітів SaaS"},
            "sub_requests": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string", "description": "Короткий опис підзапиту українською"},
                        "type": {"type": "string", "enum": TYPES},
                        "app_mentions": {"type": "array", "items": {"type": "string"},
                                          "description": "Сирі згадки систем ДОСЛІВНО з тексту. Не вигадувати і не нормалізувати."},
                        "subject": {"type": "string", "enum": ["self", "other", "multiple", "unknown"]},
                        "requested_scope": {"type": ["string", "null"]},
                        "missing_info": {"type": "array", "items": {"type": "string"}},
                        "signals": {"type": "array", "items": {"type": "string", "enum": LLM_SIGNALS}},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["summary", "type", "app_mentions", "subject", "missing_info", "signals", "confidence"],
                },
            },
        },
        "required": ["is_iam", "sub_requests"],
    },
}


def _cache_path():
    return config.CACHE / "llm_cache.json"


def _load_cache() -> dict:
    p = _cache_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save_cache(cache: dict) -> None:
    """Помилка запису кешу не має перетворювати вже оплачену відповідь LLM на rules-fallback."""
    try:
        config.CACHE.mkdir(parents=True, exist_ok=True)
        _cache_path().write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        import sys
        print(f"WARN: кеш LLM не записано ({e}); результат використано без кешу", file=sys.stderr)


def _cache_key(model: str, prompt_version: str, text: str, thread: str | None) -> str:
    return hashlib.sha256(f"{model}|{prompt_version}|{text}|{thread or ''}".encode()).hexdigest()[:24]


def _validate(raw: dict) -> Classification:
    """Строга валідація: будь-яке відхилення від схеми → fail-closed."""
    subs = []
    for s in raw.get("sub_requests", []):
        t = s.get("type")
        sigs = [x for x in s.get("signals", []) if x in LLM_SIGNALS]
        conf = float(s.get("confidence", 0))
        if t not in TYPES:
            t, conf = "unclear", 0.0
        subs.append(SubRequest(
            summary=str(s.get("summary", ""))[:300], type=t,
            app_mentions=[str(a)[:60] for a in s.get("app_mentions", [])][:10],
            subject=s.get("subject") if s.get("subject") in ("self", "other", "multiple", "unknown") else "unknown",
            requested_scope=s.get("requested_scope"),
            missing_info=[str(m)[:200] for m in s.get("missing_info", [])][:10],
            signals=sigs, confidence=max(0.0, min(conf, 1.0)),
        ))
    if not subs:
        subs = [SubRequest(summary="(LLM не повернула підзапитів)", type="unclear", confidence=0.0)]
    return Classification(is_iam=bool(raw.get("is_iam", True)), sub_requests=subs, classifier="llm", raw=raw)


def classify_llm(text: str, thread: str | None = None, *, replay_only: bool = False,
                 prompt_file: str = "classify_v2.md") -> Classification:
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
    prompt_version = prompt_file
    key = _cache_key(model, prompt_version, text, thread)
    cache = _load_cache()
    if key in cache:
        c = _validate(cache[key]["output"])
        c.classifier = f"llm-cache:{model}"
        return c
    if replay_only:
        raise LookupError(f"replay: немає запису в кеші для ключа {key}. Запусти спершу з --classifier llm.")

    import anthropic  # імпорт тут, щоб rules/replay працювали без пакета

    system = (config.PROMPTS / prompt_file).read_text(encoding="utf-8")
    user_block = f"<request>\n{text}\n</request>"
    if thread:
        user_block += f"\n<thread>\n{thread}\n</thread>"
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=1500,
        temperature=0,
        system=system,
        tools=[TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": "record_triage"},
        messages=[{"role": "user", "content": user_block}],
    )
    tool_use = next((b for b in resp.content if b.type == "tool_use"), None)
    raw = tool_use.input if tool_use else {"is_iam": True, "sub_requests": []}
    cache[key] = {"model": model, "prompt": prompt_version, "input": user_block, "output": raw,
                  "usage": {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens}}
    _save_cache(cache)
    c = _validate(raw)
    c.classifier = f"llm:{model}"
    return c


# ---------------------------------------------------------------------------
# Локальна модель (Ollama) — та сама схема, та сама валідація, той самий кеш.
# Використання: OLLAMA_URL=http://<gpu-host>:11434 OLLAMA_MODEL=qwen3:14b --classifier ollama
# Структурований вихід через `format` (JSON Schema) у /api/chat; tool use не потрібен.
# ---------------------------------------------------------------------------
OLLAMA_SUFFIX = ("\n\n## Формат відповіді\nІнструментів немає. Поверни ОДИН JSON-об'єкт за схемою `record_triage` "
                 "(поля is_iam і sub_requests) і нічого більше.")


def _ollama_key(text: str, thread: str | None, prompt_file: str) -> tuple[str, str]:
    model = os.environ.get("OLLAMA_MODEL", "qwen3:14b")
    return model, _cache_key(f"ollama:{model}", prompt_file, text, thread)


def classify_ollama(text: str, thread: str | None = None, *, prompt_file: str = "classify_v2.md") -> Classification:
    import urllib.request

    model, key = _ollama_key(text, thread, prompt_file)
    cache = _load_cache()
    if key in cache:
        c = _validate(cache[key]["output"])
        c.classifier = f"ollama-cache:{model}"
        return c
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    system = (config.PROMPTS / prompt_file).read_text(encoding="utf-8") + OLLAMA_SUFFIX
    user_block = f"<request>\n{text}\n</request>" + (f"\n<thread>\n{thread}\n</thread>" if thread else "")
    body = {"model": model, "stream": False, "format": TOOL_SCHEMA["input_schema"],
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_block}],
            "options": {"temperature": 0, "num_ctx": int(os.environ.get("OLLAMA_NUM_CTX", "8192"))}}
    if os.environ.get("OLLAMA_THINK") in ("0", "false"):
        body["think"] = False          # для «думаючих» моделей (qwen3) — швидше; TODO(verify) для кожної моделі
    req = urllib.request.Request(f"{url}/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=float(os.environ.get("OLLAMA_TIMEOUT", "180"))) as r:
        resp = json.load(r)
    raw = json.loads(resp["message"]["content"])    # невалідний JSON → виняток → fail-closed у classify()
    cache[key] = {"model": f"ollama:{model}", "prompt": prompt_file, "input": user_block, "output": raw,
                  "usage": {"in": resp.get("prompt_eval_count"), "out": resp.get("eval_count"),
                            "seconds": round(resp.get("total_duration", 0) / 1e9, 2)}}
    _save_cache(cache)
    c = _validate(raw)
    c.classifier = f"ollama:{model}"
    return c


def classify(text: str, thread: str | None, mode: str) -> Classification:
    if mode == "rules":
        return classify_rules(text, thread)
    if mode == "replay":
        # офлайн-відтворення: спершу кеш Claude, потім кеш локальної моделі
        try:
            return classify_llm(text, thread, replay_only=True)
        except LookupError:
            model, key = _ollama_key(text, thread, "classify_v2.md")
            if key in _load_cache():
                return classify_ollama(text, thread)
            raise
    if mode in ("llm", "ollama"):
        try:
            return classify_llm(text, thread) if mode == "llm" else classify_ollama(text, thread)
        except LookupError:
            raise
        except Exception as e:  # мережа/ключ/квота → не падаємо, а деградуємо на rules + low confidence
            c = classify_rules(text, thread)
            for s in c.sub_requests:
                s.confidence = min(s.confidence, 0.5)
            c.classifier = f"rules-fallback ({type(e).__name__})"
            return c
    raise ValueError(mode)
