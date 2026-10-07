## Runbook: додати співробітника в birthright-групу Okta

**Owner:** IAM | **Frequency:** за запитом (AUTO) | **Last Updated:** 2026-10-07 | **Дія в policy:** `add_birthright_group`

### Purpose

Видати доступ, який за правилами має кожен активний співробітник (напр., корпоративний VPN — група `vpn-users`), без апруву й без людини. Приклад: #91 «треба доступ до корп VPN + інструкція».

### Prerequisites — бот перевіряє ВСЕ, інакше дія не виконується

- [ ] Застосунок у каталозі має `birthright: true`, `risk_tier: low` і `okta_group`.
- [ ] Група — в allowlist бота (`mocks/okta.json → groups_allowlisted_for_bot`; у проді — Okta resource set custom admin role бота).
- [ ] Автор — з власного Slack-workspace (не Slack Connect) і **активний у HRIS**.
- [ ] Автор = суб'єкт (`requester_is_subject`), у запиті рівно одна система (`single_entitlement`).
- [ ] Жодного сигналу HUMAN / HUMAN-ONLY, немає missing data, впевненість ≥ 0.7.
- [ ] Бот має OAuth service app в Okta зі scope на керування групами, обмежений resource set-ом лише з allowlist-груп. TODO(verify): деталі custom admin role.

### Procedure

#### Step 1: Знайти користувача Okta за email автора
```
GET /api/v1/users/{email}
```
**Expected result:** `status = ACTIVE`, `id` користувача.
**If it fails:** 404 або статус ≠ ACTIVE → конфлікт джерел (HRIS active, Okta ні) → HUMAN_REVIEW.

#### Step 2: Перевірити, чи вже в групі
```
GET /api/v1/users/{userId}/groups
```
**Expected result:** групи `vpn-users` немає.
**If it fails / вже в групі:** дія не потрібна → маршрут DOCS (лише інструкція), запис `already_has_access`.

#### Step 3: Додати в групу
```
PUT /api/v1/groups/{groupId}/users/{userId}
```
**Expected result:** `204 No Content`.
**If it fails:**
- 403 — група поза resource set бота: це **помилка конфігурації, а не привід розширювати права бота** → HUMAN_REVIEW + алерт IAM;
- 429 — бекоф за `X-Rate-Limit-Reset`, одна повторна спроба, далі HUMAN_REVIEW.

#### Step 4: Записати дію
Запис у журнал дій: `action`, `params {group, user}`, `would_call`, `preconditions`, `idempotency_key`.

### Verification

- [ ] `GET /api/v1/users/{userId}/groups` містить `vpn-users` (перевірка читанням **після** запису, а не довіра до 204).
- [ ] Користувач отримав відповідь у треді з посиланням на KB-статтю про підключення.
- [ ] У Okta System Log є подія `group.user_membership.add` з actor = сервісний акаунт бота.

### Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Користувач у групі, але VPN не пускає | група не призначена застосунку VPN або клієнт кешує сесію | перевірити assignment застосунку; KB-стаття про підключення |
| 403 на `PUT` | resource set бота не містить групу | людина вирішує, чи група справді birthright; **не** розширювати resource set автоматично |
| Дія двічі для того самого автора | ретрай Slack без дедупу | `event_id` дедуп (`dedup.py`); ідемпотентний `PUT` сам по собі безпечний |

### Rollback

```
DELETE /api/v1/groups/{groupId}/users/{userId}
```
Безпечно: birthright-доступ, жодних даних не змінено. Потім перевірити `GET /users/{id}/groups` і записати відкат у журнал з посиланням на `idempotency_key` початкової дії.

### Escalation

| Situation | Contact | Method |
|---|---|---|
| будь-яка помилка Okta, 403, конфлікт джерел | IAM-інженер | DM + JSM-тікет (HUMAN_REVIEW) |
| > N додавань за годину (ліміт швидкості) | IAM + security | kill switch, алерт |

### History

| Date | Run By | Notes |
|---|---|---|
| 2026-10-07 | бот (dry_run) | #91 у демо: `vpn-users`, автор активний, група в allowlist |
