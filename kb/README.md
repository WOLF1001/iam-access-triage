# kb/ — повні тексти deflection-статей

| Де | Що | Хто читає |
|---|---|---|
| `kb/*.md` | повна стаття: симптоми, кроки, що зробить бот і чого не зробить | людина (джерело для Notion) |
| `config/kb.yaml` | `article_id`, заголовок, коротке summary, ключові слова | бот у тестах і офлайн |
| Notion «IAM KB» | те саме, `Status = Published` | бот у проді (синк кожні 15 хв) |

`article_id` однаковий в усіх трьох місцях. Бот цитує лише summary й дає посилання; інструкцій «з голови» не пише (`docs/zones.md` §3).

Статті обрано за кластерами повторів із `docs/process/current-state.md` §3:

| Стаття | Тип | Покриває звернення |
|---|---|---|
| [`sso-login-troubleshooting`](sso-login-troubleshooting.md) | troubleshooting | #15, #33, #42, #69, #82 — «не пускає через Okta», «зник доступ» |
| [`access-request-process`](access-request-process.md) | how-to | #30, #39, #47, #89, #101 — «дайте доступ», «хто апрувить» |
| [`ai-limits-process`](ai-limits-process.md) | FAQ | #17, #31, #55, #67, #86, #90, #97 — ліміти, seat-и, extra usage |
| [`api-key-process`](api-key-process.md) | how-to | #5, #36, #54, #62, #83 — ключ до AI-моделі |
| [`okta-self-service-reset`](okta-self-service-reset.md) | how-to | #78, #93, #95 — пароль, MFA |

**Перед публікацією:** конкретні назви порталів, посилань і строків — заглушки. Їх звіряє власник процесу (`docs/process/raci.md`). Перегляд — щокварталу, а також після кожного `kb_gap` на ту саму тему.
