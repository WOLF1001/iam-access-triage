"""Детерміновані детектори сигналів по тексту.

Працюють завжди, незалежно від LLM. LLM може ДОДАТИ сигнали, але не прибрати ці.
Регулярки грубі навмисно: false positive тут = зайва ескалація (дешево),
false negative = небезпечна авто-дія (дорого).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

TEXT_DETECTORS: dict[str, list[str]] = {
    "secret_compromise": [r"злит", r"скомпрометов", r"leak", r"витік", r"витекл"],
    "security_finding": [r"пентест", r"вразлив", r"high-знахід", r"\bcve\b"],
    "offboarding": [r"останній день", r"звільнен", r"offboard", r"заблокуйте всі доступи", r"забрати .*підписк"],
    "hris_bypass": [r"(hrm|hris|hr-систем)\w*\s+ще не", r"у hrm ще не", r"не внес\w* в (hrm|hris)"],
    "mirror_access": [r"що у (ліда|нього|неї|колеги) було", r"як у (ліда|колеги)", r"такі ж (права|доступи)", r"все,? що у"],
    "broad_scope": [r"\bвсі\b", r"\bвсіх\b", r"\bусі\b", r"повний пакет", r"на всіх", r"все видати", r"можеш все"],
    "privileged_access": [r"адмін(ськ|к)", r"\badmin\b", r"superuser", r"права адміна"],
    "credential_reset": [r"скинути пароль", r"скинь пароль", r"reset.{0,20}парол", r"відновити пароль", r"скинути mfa"],
    "shared_credential": [r"по ньому зайшл", r"спільн\w+ (командн|акаунт)", r"шерив", r"код доступу", r"apple id",
                          r"окремий логін", r"2 аккаунт", r"два акаунт", r"кредів"],
    "pii_request": [r"номер\w* телефон", r"контакти", r"id в hr", r"статус звільнення", r"хто юзає"],
    "security_policy_change": [r"always-allow", r"always allow", r"вимкн\w* mfa"],
    "third_party_connector": [r"конектор", r"\bmcp\b", r"\bмср\b", r"підключаю .+ до"],
    "external_party": [r"підрядник", r"contractor", r"фрілансер", r"агенці"],
    "financial_data": [r"фін\w* показник", r"фінанс", r"диспут", r"billing"],
    "payment_action": [r"поповн", r"карту", r"оплат", r"extra usage", r"баланс", r"кредити"],
    "unverified_approval_claim": [r"лід в курсі", r"погоджено", r"апрув є", r"дозволив", r"\bв курсі\b"],
    "on_behalf": [r"(моїй|моєму) колез", r"колезі", r"колеги акаунт", r"ще одному колезі", r"\d+ людям",
                  r"людям з команди", r"в колеги не працює", r"співробітнику", r"нам двом", r"двом моїм колегам",
                  r"у людини", r"нова людина", r"моїй колеги", r"новенькій", r"колезі новенькій"],
    "urgency": [r"асап", r"\basap\b", r"терміново", r"до \d{1,2}\b", r"!!", r"лонч", r"сьогодні"],
    "prompt_pressure": [r"не треба документац", r"просто відповідь", r"просто (видай|дай)", r"без апрув", r"не шли доки"],
    "cost_impact": [r"ліміт", r"тариф", r"ліцензі", r"підписк", r"кредит", r"токени", r"преміум", r"місця", r"extra usage", r"квот"],
}

# Маркери відсутніх критичних даних
MISSING_DETECTORS: dict[str, list[str]] = {
    "список людей відсутній": [r"список дам", r"список нижче"],
    "деталі тільки в треді": [r"деталі в тред"],
    "конкретна система/модель не названа": [r"одн(ієї|ого|у|а|ій) (з )?(ai-модел|модел|тул|креатив|з продукт|внутрішн)", r"один з продукт",
                                            r"одн\w+ з (нових )?продукт", r"\bai-модел"],
}


@dataclass
class Signal:
    name: str
    origin: str          # text | llm | read
    evidence: str

    def to_dict(self) -> dict:
        return {"name": self.name, "origin": self.origin, "evidence": self.evidence}


def detect_text_signals(text: str) -> list[Signal]:
    low = text.lower()
    found: list[Signal] = []
    for name, pats in TEXT_DETECTORS.items():
        for p in pats:
            m = re.search(p, low)
            if m:
                found.append(Signal(name, "text", f"regex '{p}' → «{m.group(0)}»"))
                break
    return found


def detect_missing(text: str, has_thread: bool) -> list[str]:
    low = text.lower()
    missing = []
    for label, pats in MISSING_DETECTORS.items():
        if any(re.search(p, low) for p in pats):
            if label in ("деталі тільки в треді", "список людей відсутній") and has_thread:
                continue
            missing.append(label)
    return missing
