# Повний прогін: 108 звернень

Класифікатор: `rules`. У CSV немає авторів, тому для всіх звернень requester = синтетичний активний співробітник `UGEN` без особливостей (менеджер доступний, базові групи). Треди відсутні — тому «деталі в треді» коректно дають NEED_INFO.

| Маршрут | К-сть | % |
|---|---|---|
| AUTO — бот робить сам | 1 | 1% |
| DOCS — перенаправлення в документацію | 16 | 15% |
| REROUTE — не IAM, інша черга | 10 | 9% |
| NEED_INFO — уточнення | 27 | 25% |
| APPROVAL — бот готує, людина апрувить | 18 | 17% |
| HUMAN — рішення за IAM-інженером | 33 | 31% |
| SECURITY — інцидент / пейдж | 3 | 3% |

| № | Звернення | Маршрут | Типи | Ключовий сигнал |
|---|---|---|---|---|
| 1 | привіт! мені скинули лінк на композит, але я досі не можу з… | NEED_INFO | login_diagnostic | `diagnostic_inconclusive` (read) |
| 2 | у мене вікно віддаленого компа не масштабується нормально, … | REROUTE | not_iam | тип `not_iam` |
| 3 | в airtable не переносяться таски, думаю це через права. гля… | NEED_INFO | login_diagnostic | `diagnostic_inconclusive` (read) |
| 4 | чому в клоді якісь теги/спейси недоступні? мені казали що є… | DOCS_REDIRECT | policy_question | тип `policy_question` |
| 5 | треба згенерити новий api-ключ до однієї ai-моделі, це для … | NEED_INFO | api_key_request | `unverified_approval_claim` (text) |
| 6 | як отримати менеджерський ключ до стор-консолі одного з про… | DOCS_REDIRECT | how_to | тип `how_to` |
| 7 | питання по лімітах notion api — чи треба нам апати тариф що… | DOCS_REDIRECT | policy_question | тип `policy_question` |
| 8 | нам двом треба доступ в один креатив-тул, і ще в однієї кол… | NEED_INFO | access_request, login_diagnostic | `on_behalf` (text) |
| 9 | треба інвайт у тестові білди мобільного застосунку (і ios і… | APPROVAL_GATED | access_request | тип `access_request` |
| 10 | дайте будь ласка доступ до тули для транскрибації дзвінків | APPROVAL_GATED | access_request | тип `access_request` |
| 11 | мені прийшов інвайт у meta business, треба підтвердити мою … | APPROVAL_GATED | access_request | тип `access_request` |
| 12 | хочу ввімкнути always-allow для mcp-конекторів у клоді, так… | HUMAN_REVIEW | security_policy_change | `security_policy_change` (text) |
| 13 | у нас є корпоративна підписка на тулу транскрибації дзвінкі… | APPROVAL_GATED | license_request | тип `license_request` |
| 14 | а корп акаунт на дизайн-референс тулу ще живий? колись я йо… | HUMAN_REVIEW | access_request | `shared_credential` (text) |
| 15 | клод-код вилітає, просить релогін через okta і не пускає. щ… | NEED_INFO | login_diagnostic | `diagnostic_inconclusive` (read) |
| 16 | щось уперлась в ліміт, не розумію де саме. кажуть це bigque… | APPROVAL_GATED | limits_quota | тип `limits_quota` |
| 17 | треба підняти ліміти клода 5 людям з команди під ai-відео. … | NEED_INFO | limits_quota | `on_behalf` (text) |
| 18 | треба перегенерувати ключі, старі здається злиті. деталі в … | SECURITY_ESCALATION | secret_incident | `secret_compromise` (text) |
| 19 | створила новий акаунт для роботи з рекламним кабінетом, тре… | APPROVAL_GATED | access_request | тип `access_request` |
| 20 | підключаю asana до slack, а в дропдауні проєктів порожньо. … | HUMAN_REVIEW | integration_connector | `third_party_connector` (text) |
| 21 | з okta зник один з market-intel сервісів і не пускає у відд… | NEED_INFO | login_diagnostic | `diagnostic_inconclusive` (read) |
| 22 | нам треба відповідати на відгуки в сторах, яка схема доступ… | DOCS_REDIRECT | how_to | тип `how_to` |
| 23 | треба тимчасовий доступ до однієї корп пошти (лежить у 1pas… | HUMAN_REVIEW | access_request | `shared_credential` (text) |
| 24 | не заходить у фб акаунт взагалі, пробував все, не помагає. … | NEED_INFO | login_diagnostic | `precondition_failed` (read) |
| 25 | треба доступ до дашборда одного з продуктів + не виходить з… | NEED_INFO | access_request, login_diagnostic | `missing_critical_data` (text) |
| 26 | не знаю, чи це до тебе, але треба вивантажити списки людей … | HUMAN_REVIEW | data_export | `pii_request` (text) |
| 27 | потрібен viewer-доступ до аналітики залучення (tiktok, один… | NEED_INFO | access_request | `missing_critical_data` (text) |
| 28 | у нас закінчились кредити на ai-тулі і через це став дабінг… | REROUTE | billing_finance | `payment_action` (text) |
| 29 | у мене не працює adobe creative cloud, щось з підпискою. і … | HUMAN_REVIEW | license_issue, access_request | `on_behalf` (text) |
| 30 | дайте доступ до growthbook, колеги вже мають а я ні | APPROVAL_GATED | access_request | тип `access_request` |
| 31 | чому в мене ліміти на одній geminiі так швидко закінчуються… | APPROVAL_GATED | limits_quota | тип `limits_quota` |
| 32 | асап!! видаліть будь ласка нотатку в 1password зі старим ap… | SECURITY_ESCALATION | secret_incident | `secret_compromise` (text) |
| 33 | не можу зайти в airtable через okta, викидає помилку | NEED_INFO | login_diagnostic | `diagnostic_inconclusive` (read) |
| 34 | мені потрібен менеджерський ключ до app store по продукту, … | APPROVAL_GATED | api_key_request | тип `api_key_request` |
| 35 | уперлись в квоту bigquery, треба підняти, аналітика стоїть | APPROVAL_GATED | limits_quota | тип `limits_quota` |
| 36 | локалізаторам потрібен новий api-ключ до ai-моделі, зробіть… | NEED_INFO | api_key_request | `missing_critical_data` (text) |
| 37 | як правильно підключити airtable до клода через персональни… | DOCS_REDIRECT | how_to | тип `how_to` |
| 38 | треба адмінські права в app store connect і play console по… | HUMAN_REVIEW | access_request | `privileged_access` (text) |
| 39 | можна доступ до speechify? | APPROVAL_GATED | access_request | тип `access_request` |
| 40 | апрувніть будь ласка конектор make для клода, треба під авт… | HUMAN_REVIEW | integration_connector | `third_party_connector` (text) |
| 41 | у людини сьогодні останній день, треба забрати розширену пі… | HUMAN_REVIEW | offboarding | `offboarding` (text) |
| 42 | вчора ввечері не міг зайти, сьогодні теж дивно. подивіться … | NEED_INFO | login_diagnostic | `diagnostic_inconclusive` (read) |
| 43 | треба завести пошту і перенести ліцензію market-intel тули … | HUMAN_REVIEW | project_work | тип `project_work` |
| 44 | привіт, а ти вже закинув анонс у робочому каналі про степи … | REROUTE | not_iam | тип `not_iam` |
| 45 | привіт, хелпдеск тупить, можеш допомогти пушнути їх по ство… | REROUTE | not_iam | тип `not_iam` |
| 46 | не розумію які доступи мені треба - документи, драйв, api… … | HUMAN_REVIEW | access_request | `mirror_access` (text) |
| 47 | як працює апрув запитів коли звертаєшся у хелпдеск? хто має… | DOCS_REDIRECT | how_to | тип `how_to` |
| 48 | прийшов інвайт, але ліцензія не активувалась, баг якийсь. ф… | HUMAN_REVIEW | license_issue | `unknown_app` (catalog) |
| 49 | Привіт! треба зробити міграцію домену + перенос ліцензії + … | HUMAN_REVIEW | project_work, license_request, project_work | `unknown_app` (catalog) |
| 50 | як заходити у віддалене середовище для market-intel тули? н… | DOCS_REDIRECT | how_to | тип `how_to` |
| 51 | У мене зламався монітор, його мій кіт завалив, що робити? | REROUTE | not_iam | тип `not_iam` |
| 52 | терміново треба доступ через okta + поповнити баланс на тул… | NEED_INFO | access_request, billing_finance | `unknown_app` (catalog) |
| 53 | акаунт на аналітичній тулі глючить, схоже перевантажений. м… | HUMAN_REVIEW | login_diagnostic | `shared_credential` (text) |
| 54 | нова команда, треба налаштувати менеджмент api-ключа Gemini… | APPROVAL_GATED | api_key_request | тип `api_key_request` |
| 55 | хочу підняти собі ліміт у гпт, що для цього треба? лід має … | DOCS_REDIRECT | how_to | тип `how_to` |
| 56 | чому у мене 2 аккаунта для sensor tower? і щось не можу зай… | HUMAN_REVIEW | login_diagnostic | `shared_credential` (text) |
| 57 | прошу видати доступ до рекламного business manager моїй кол… | NEED_INFO | access_request | `financial_data` (text) |
| 58 | заводимо нового підрядника по виробництву серіалів — треба … | HUMAN_REVIEW | onboarding | `external_party` (text) |
| 59 | підключіть плз mcp-конектор нашої внутрішньої креатив-тули … | HUMAN_REVIEW | integration_connector | `third_party_connector` (text) |
| 60 | треба порахувати кількість користувачів у слаці на всіх наш… | HUMAN_REVIEW | usage_report | `broad_scope` (text) |
| 61 | конектор у клоді сам вимикається, не розумію чому. до кого … | HUMAN_REVIEW | integration_connector | `third_party_connector` (text) |
| 62 | треба api-ключ до ai-моделі під автоматизацію дубляжу | NEED_INFO | api_key_request | `missing_critical_data` (text) |
| 63 | мені треба доступ до всіх наших market-intel/spy тул, по пі… | HUMAN_REVIEW | license_request | `broad_scope` (text) |
| 64 | не можу залогінитись у тулу для лігал документів, чомусь не… | HUMAN_REVIEW | login_diagnostic | `shared_credential` (text) |
| 65 | можна пошерити vault в 1password двом моїм колегам? | HUMAN_REVIEW | access_request | `critical_resource` (catalog) |
| 66 | треба корпоративний apple id для testflight і дев-задач | HUMAN_REVIEW | unclear | `shared_credential` (text) |
| 67 | поповніть extra usage на клоді будь ласка | REROUTE | billing_finance | `payment_action` (text) |
| 68 | дайте мені перегляд (view) до внутрішнього проекту продукті… | APPROVAL_GATED | access_request | тип `access_request` |
| 69 | пропав доступ до tableau, через okta не пускає | NEED_INFO | login_diagnostic | `diagnostic_inconclusive` (read) |
| 70 | треба api-ключ до тула аналітики з команди Drama, який скоу… | NEED_INFO | api_key_request | `unknown_app` (catalog) |
| 71 | дайте доступ до tableau, і чи можна перейти на дешевний рід… | APPROVAL_GATED | access_request, billing_finance | тип `access_request` |
| 72 | питання по ліцензуванню coda — скільки коштує доступ док-ме… | REROUTE | billing_finance | тип `billing_finance` |
| 73 | треба доступ через okta до композитів | NEED_INFO | access_request | `unknown_app` (catalog) |
| 74 | я знайшов 2 ліцензії, якими ніхто не користується, бо перей… | REROUTE | billing_finance | тип `billing_finance` |
| 75 | виходить нова людина, це неплановий вихід, у HRM ще не внес… | HUMAN_REVIEW | onboarding | `hris_bypass` (text) |
| 76 | треба інвайт в n8n | APPROVAL_GATED | access_request | тип `access_request` |
| 77 | підніміть ліміти на моєму api-ключі, і питання по підписці,… | NEED_INFO | api_key_request, billing_finance | `unknown_app` (catalog) |
| 78 | допоможіть налаштувати 2fa на корп пошті | DOCS_REDIRECT | credential_reset | тип `credential_reset` |
| 79 | Підкажи, як замовити нову техніку собі? | REROUTE | not_iam | тип `not_iam` |
| 80 | тула пише що закінчились токени, а їх начебто має бути. гля… | NEED_INFO | limits_quota | `unknown_app` (catalog) |
| 81 | можна виставити ліміт витрат на моєму api-ключі, щоб не пер… | NEED_INFO | api_key_request | `unknown_app` (catalog) |
| 82 | не заходить у tableau, крутиться і все | NEED_INFO | login_diagnostic | `diagnostic_inconclusive` (read) |
| 83 | треба токени до двох ai-моделей (gemini і claude api) | NEED_INFO | api_key_request | `missing_critical_data` (text) |
| 84 | в колеги не працює доступ до tableau, можете глянути його п… | NEED_INFO | login_diagnostic | `on_behalf` (text) |
| 85 | прийшов звіт від пентестерів, там High-знахідка по одному з… | SECURITY_ESCALATION | not_iam | `security_finding` (text) |
| 86 | треба підняти ліміти клода 9 людям, список нижче | NEED_INFO | limits_quota | `on_behalf` (text) |
| 87 | треба доступ до розділу диспутів у платіжці, на всіх спейсах | HUMAN_REVIEW | access_request | `broad_scope` (text) |
| 88 | проходжу безпековий тест і там помилки в блоці про паролі/ф… | REROUTE | not_iam | тип `not_iam` |
| 89 | дайте доступ до аналітичного середовища ще одному колезі | NEED_INFO | access_request | `on_behalf` (text) |
| 90 | можна підняти ліміт клода на нашому спільному командному ак… | HUMAN_REVIEW | limits_quota | `shared_credential` (text) |
| 91 | треба доступ до корп vpn + інструкція як підключитись | AUTO_RESOLVE | access_request, how_to | тип `access_request`, дія `add_birthright_group` |
| 92 | терміново заблокуйте всі доступи співробітнику — сьогодні о… | HUMAN_REVIEW | offboarding | `offboarding` (text) |
| 93 | як налаштувати MFA у мене на андроїд? щось не розумію | DOCS_REDIRECT | credential_reset | тип `credential_reset` |
| 94 | поясніть як влаштовані права в клоді на рівні організації | DOCS_REDIRECT | how_to | тип `how_to` |
| 95 | у нас сьогодні лонч і мене вибило, терміново треба скинути … | DOCS_REDIRECT | credential_reset | `credential_reset` (text) |
| 96 | можеш інструкцію закинути, як працювати з 1pass? до цього н… | DOCS_REDIRECT | how_to | тип `how_to` |
| 97 | треба інвайт у нашу організацію клода з преміумом (2 місця)… | APPROVAL_GATED | license_request, limits_quota | тип `license_request` |
| 98 | уточніть будь ласка статус звільнення співробітника і її id… | HUMAN_REVIEW | usage_report | `offboarding` (text) |
| 99 | я тести нормально пройшла, для чого читати цей документ з і… | HUMAN_REVIEW | policy_question | `kb_gap` (kb) |
| 100 | чому по цій ai-тулі такі великі витрати за місяць? можеш за… | HUMAN_REVIEW | usage_report | `pii_request` (text) |
| 101 | дайте доступ до market-intel тули | APPROVAL_GATED | access_request | тип `access_request` |
| 102 | додайте мені в окту ai-тулу, якою команда креаторів користу… | HUMAN_REVIEW | access_request | `shared_credential` (text) |
| 103 | мені треба адмінка в одному внутрішньому інструменті сапорт… | HUMAN_REVIEW | access_request | `privileged_access` (text) |
| 104 | інвайт у асану деактивувався поки я дійшла, надішліть ще ра… | APPROVAL_GATED | invite_resend | `precondition_failed` (read) |
| 105 | як підключити coda до клода через мср? можеш гайд закинути … | HUMAN_REVIEW | how_to | `third_party_connector` (text) |
| 106 | підкажи, а як взагалі зайти у окту і що це таке? | DOCS_REDIRECT | how_to | тип `how_to` |
| 107 | як мені авторизуватись у слак? | DOCS_REDIRECT | how_to | тип `how_to` |
| 108 | можеш підказати, як створити проект у асані, щоб доступ був… | DOCS_REDIRECT | how_to | тип `how_to` |