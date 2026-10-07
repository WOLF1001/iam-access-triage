"""Спільні хелпери для тестів.

Модель загроз, під яку написані тести: LLM — недовірений компонент (галюцинує або
піддається prompt injection через текст звернення). Тому класифікатор у тестах
часто підміняється «противником», який повертає будь-яку валідну за схемою структуру,
а перевіряємо ми те, що policy engine тримає межі незалежно від цього.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from triage import classify, config, pipeline  # noqa: E402
from triage.classify import Classification, SubRequest  # noqa: E402
from triage.redact import redact  # noqa: E402
from triage.signals import detect_text_signals  # noqa: E402

SEV = config.ROUTE_SEVERITY
REQ = config.load_requests()
HARD = {r["signal"]: r["min_route"] for r in config.policy()["hard_rules"] if r["min_route"]}


def run_text(text: str, *, requester: str = "UGEN", thread: str | None = None, mode: str = "rules",
             req_id: int = 999, log=None):
    return pipeline.run_one(req_id, text, requester_slack=requester, thread=thread, mode=mode, log=log)


def effective_severity(result) -> int:
    """NEED_INFO з next_route=APPROVAL — це не пониження, а gate перед апрувом (D5).
    Тому порівнюємо max(route, next_route)."""
    return max(max(SEV[d.route], SEV[d.next_route] if d.next_route else 0) for d in result.decisions)


def text_floor(text: str) -> int:
    """Мінімальна severity, яку гарантують детерміновані regex-детектори по ВСЬОМУ тексту.
    Це «підлога», нижче якої LLM не має права опустити маршрут (золоте правило 2)."""
    names = {s.name for s in detect_text_signals(redact(text)[0])}
    if "offboarding" in names:          # «всі доступи» при offboarding — очікуваний скоуп (policy.decide)
        names.discard("broad_scope")
    return max([SEV[HARD[n]] for n in names if n in HARD] or [0])


def fake_llm(*subs: SubRequest, is_iam: bool = True):
    def f(text, thread, mode):
        return Classification(is_iam=is_iam, sub_requests=[copy.deepcopy(s) for s in subs], classifier="fake-llm")
    return f


@pytest.fixture
def llm(monkeypatch):
    """llm(SubRequest(...), ...) — підмінити класифікатор на «противника»."""
    def install(*subs, is_iam=True):
        monkeypatch.setattr(classify, "classify", fake_llm(*subs, is_iam=is_iam))
    return install


@pytest.fixture
def mocks(monkeypatch):
    """Ізольована копія моків, яку тест може мутувати (lru_cache у config.mock інакше протік би між тестами)."""
    store: dict[str, dict] = {}
    orig = config.mock

    def patched(name):
        if name not in store:
            store[name] = copy.deepcopy(orig(name))
        return store[name]

    monkeypatch.setattr(config, "mock", patched)
    return patched
