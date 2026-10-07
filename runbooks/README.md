# runbooks/ — AUTO-дії бота

Бот виконує сам лише три дії з allowlist (`config/policy.yaml → auto_allowlist`; критерії — `docs/zones.md` §2). На кожну є runbook:
- що бот перевіряє перед дією;
- які виклики робить;
- як перевірити результат;
- як відкотити;
- як людині зробити те саме вручну, якщо бот вимкнено.

| Runbook | Дія | Що змінює | Відкат |
|---|---|---|---|
| [`add-birthright-group.md`](add-birthright-group.md) | `add_birthright_group` | членство в Okta-групі з allowlist бота (`vpn-users`) | видалити з групи |
| [`resend-invite.md`](resend-invite.md) | `resend_invite` | повторний інвайт в Asana за чинним апрувом | видалити користувача / відкликати інвайт |
| [`readonly-diagnostic.md`](readonly-diagnostic.md) | `readonly_diagnostic` | нічого (лише читання System Log) | не потрібен |

**Спільне для всіх:**
- **Прототип:** дія — лише запис у `demo/actions*.log` з `dry_run: true`. Виклики API нижче — те, що бот зробив би в проді.
- **Kill switch (прод):** одна змінна (наприклад, `AUTO_ACTIONS_ENABLED=false`) переводить усі AUTO-дії в APPROVAL. У прототипі ще не реалізовано (`docs/critique.md` §4).
- **Ліміт швидкості (прод):** не більше N змінних дій на годину на групу або застосунок. Перевищення — стоп і алерт IAM.
- **Ідемпотентність:** кожна дія має `idempotency_key`; повтор події Slack не дублює дію (`src/triage/dedup.py`).
- **Ескалація:** будь-яка помилка на будь-якому кроці → маршрут HUMAN_REVIEW, повідомлення IAM у DM. Бот не повторює змінну дію без людини.
