# Материалы по проекту

### 3.4.4 — отдельный лимит AI-запросов

- [ ] При необходимости: [Redis — INCR](https://redis.io/docs/latest/commands/incr/), только Pattern: Rate limiter и первый пример Rate limiter 1. Для текущего участка использовать существующий check_rate_limit; новый limiter/Lua не требуется. Общий лимит IP и лимит AI по пользователю имеют разные ключи.

### 3.4.4 — исчерпанные повторы AI

- [ ] [Tenacity — Error Handling](https://tenacity.readthedocs.io/en/latest/#error-handling): только раздел Error Handling до следующего заголовка, включая reraise=True. По умолчанию после исчерпания попыток выбрасывается RetryError; reraise=True сохраняет последнее исходное исключение. Выбор остаётся пользователю.

### 3.4.4 — общий таймаут AI

- [ ] [Python — asyncio.timeout](https://docs.python.org/3.12/library/asyncio-task.html#asyncio.timeout). Описание и два первых примера, до описания класса asyncio.Timeout. Обратить внимание: async context manager, отмена ожидаемой операции, TimeoutError ловится снаружи контекста. Один контекст вокруг всей операции включает и паузы повторов; контекст внутри каждой попытки задаёт другой бюджет. Не гарантия прекращения вычислений на удалённом сервере.

### 3.4.4 — заполнение шаблона запроса AI

- [ ] [Python — Format String Syntax](https://docs.python.org/3.12/library/string.html#format-string-syntax): вступление до формальной грамматики, особенно {{ и }} для буквальных скобок. При вставке примера JSON в шаблон его скобки нужно экранировать; подставляемые значения повторно не форматируются. Остальную страницу читать не требуется.

### 3.4.2 — ограничения значений и сочетания полей

- [ ] [Pydantic — Fields](https://docs.pydantic.dev/latest/concepts/fields/): только Numeric Constraints и Decimal Constraints. Сопоставить с уже существующими DealName, DealCreate и DealUpdate в schemas/deal.py.
- [ ] [Pydantic — Model validators](https://docs.pydantic.dev/latest/concepts/validators/#model-validators): вступление и первый пример After validators; before/wrap пока пропустить. Нужен для правил, зависящих сразу от нескольких полей; использовать именно этот механизм не обязательно.

### 3.4.2 — ошибка разбора ответа провайдера

- [ ] [Pydantic — Validating data](https://docs.pydantic.dev/latest/concepts/models/#validating-data): описание model_validate_json и примеры его ValidationError (невалидный JSON и неверные типы). Остановиться перед Validating data with context. Важное различие: ValidationError внешнего ответа здесь превращаем в 502, это не RequestValidationError входного запроса FastAPI.

## 3.4.2 — безопасный выбор сделки из ответа AI

- [ ] [Python — Common Sequence Operations](https://docs.python.org/3.12/library/stdtypes.html#common-sequence-operations): только строка таблицы s[i] и примечания 1–2 о начале индексации и отрицательных индексах. Цель: -1 выбирает последний элемент, а не вызывает ошибку.
- [ ] При необходимости повторить HTTPException из материалов 3.4.1. Ответ внешнего провайдера, непригодный для обработки, в этом участке возвращает 502; неверный вход пользователя остаётся 422.

## Текущая 3.4.1 — доступ и вход AI-заметки

- [ ] Только при необходимости: [FastAPI — Use HTTPException](https://fastapi.tiangolo.com/tutorial/handling-errors/#use-httpexception). Читать Use HTTPException с Raise an HTTPException in your code, остановиться перед Add custom headers. Проверка должна останавливать запрос до внешнего вызова.
- [ ] Только описание [Python — str.strip](https://docs.python.org/3.12/library/stdtypes.html#str.strip), без соседних методов. Строка из пробелов проходит min_length, но после strip становится пустой. Нового инструмента для этой задачи нет.

## Текущая 3.3.6 — текстовое письмо, 20 октября 2026

- [ ] [Python — email examples](https://docs.python.org/3.12/library/email.examples.html). Только первый пример от начала страницы до «Here's an example of how to send the entire contents of a directory». Изучить EmailMessage, set_content и заголовки Subject/From/To; чтение файла и отправку через smtplib переносить не требуется.
- [ ] [aiosmtplib — The send Coroutine](https://aiosmtplib.readthedocs.io/en/stable/usage.html). Раздел The send Coroutine и подразделы о TLS/STARTTLS; multipart, HTML и OAuth пропустить. Цель: await send с EmailMessage, параметры SMTP и различие TLS/STARTTLS. Не включать use_tls и start_tls одновременно; режим определяется сервером. В сигнатуре send отдельно посмотреть timeout.

Первый участок — письмо и SMTP-адаптер, без подключения к HTTP, реальных рассылок и повторов. Чтение пользователь отмечает сам.

## Актуальные материалы после изменения плана 16 октября 2026

3.3.1 и 3.3.2 завершены. Celery отложен до будущих уведомлений/напоминаний. Старые материалы ниже сохранены с отметками как история: разделы 3.3.3, 3.3.4, 3.3.6 и проверки воркера 3.3.8 больше не являются обязательным чтением этого этапа. Актуальные восемь задач — в handoff-stage-3.3.md.

### Текущая 3.3.3 — подтверждение демооплаты обычным POST

- [ ] Повторение при необходимости: [FastAPI — Use HTTPException](https://fastapi.tiangolo.com/tutorial/handling-errors/#use-httpexception). Только Use HTTPException с Raise an HTTPException in your code; остановиться перед Add custom headers. Цель: единый 404 недоступной ссылки и 409 доменного отказа при оплате.
- [ ] Повторение: [SQLAlchemy — Managing Transactions](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html). Пример `with session.begin():` и следующий абзац; остановиться перед «The session may also be used in a commit-as-you-go approach». Цель: сервис оплаты уже владеет транзакцией; SELECT при проверке ссылки запускает autobegin, границы должны быть согласованы, без вложенного begin на занятой сессии.

### 3.3.4 — инвалидация кэша после оплаты

- [ ] [Python — Logging HOWTO: When to use logging](https://docs.python.org/3.12/howto/logging.html#when-to-use-logging). Читать этот подраздел с таблицей уровней, остановиться перед **A simple example**. Цель: выбрать уровень события; сообщение журнала не является HTTP-ответом.
- [ ] [Python — Logger.exception](https://docs.python.org/3.12/library/logging.html#logging.Logger.exception). Только описание метода, до следующего метода. Цель: запись ERROR с текущим traceback из обработчика исключения; не путать с raise.

- [ ] Повторение при необходимости: [Redis — DEL](https://redis.io/docs/latest/commands/del/). Описание команды и **Examples**, остальные разделы пропустить. Отсутствующий ключ не является ошибкой; повторная инвалидация допустима.
- [ ] [redis-py — Exceptions](https://redis.readthedocs.io/en/stable/exceptions.html). Только описания **ConnectionError**, **TimeoutError** и **RedisError**; остальные классы пропустить. Цель: отделить сбой Redis после commit от отказа оплаты и ошибок программирования, не маскировать все исключения общим перехватом.

Для 3.3.5 остаются Templates/Fetch, но ожидание — HTTP-ответа, без опроса Celery. Материалы SMTP применимы к новым 3.3.6–7; точный материал выбирается при постановке после выбора клиента. Для 3.3.8 проверка настоящего воркера отложена.

## Исторические материалы 3.3 до переноса Celery (отметки сохранены)

Подготовлено 14 октября 2026. Читать только материалы к текущей задаче, не весь список заранее. План и контракт работы: [handoff-stage-3.3.md](./handoff-stage-3.3.md). Все новые отметки оставлены пустыми; это отметки чтения, не реализации.

### 3.3.1. Платёжная ссылка и её жизненный цикл

- [ ] [Python 3.12 — secrets](https://docs.python.org/3.12/library/secrets.html#generating-tokens). Читать от **Generating tokens** до конца **How many bytes should tokens use?**, остановиться перед **Other functions**. Затем отдельно описание `compare_digest` в **Other functions**, без **Recipes and best practices**.
  - Цель: случайный секрет для URL, размер случайности, безопасное сравнение. Не путать случайный токен с ID счёта.
- [ ] [OWASP — Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html#url-tokens). Читать **URL Tokens** целиком, остановиться перед **PINs**.
  - Цель: привязка секрета к объекту, защищённая ссылка, доверенный адрес сайта, утечка через Referer. Это аналогия с секретной ссылкой: не переносить сюда смену пароля и правило одноразовости буквально. У нашей ссылки свои правила версии, PAID и повторного чтения из domain.md.

#### Справка к миграции токенов: autogenerate и имена ограничений

- [ ] [Alembic — Auto Generating Migrations](https://alembic.sqlalchemy.org/en/latest/autogenerate.html). Читать вступление до **What does Autogenerate Detect (and what does it not detect?)**, включая предупреждение о ручной проверке; затем отдельно **Comparing Types**, остановиться перед **Applying Post Processing and Python Code Formatters to Generated Revisions**.
  - Цель: autogenerate сравнивает схему подключённой БД с metadata моделей, а не изменения Python-файлов или содержимое прошлой миграции. `existing_type` описывает отражённый тип БД, `type_` — целевой тип.
- [ ] [Alembic — The Importance of Naming Constraints](https://alembic.sqlalchemy.org/en/latest/naming.html). Читать вступление до **Integration of Naming Conventions into Operations, Autogenerate**; дальнейшее пока пропустить.
  - Цель: для удаления ограничения требуется его имя; при явном именовании использовать одно имя в создании и удалении. Внедрять глобальный naming convention для этой задачи не требуется.

### 3.3.2. Публичное чтение счёта по ссылке

- [ ] [FastAPI — Response Model](https://fastapi.tiangolo.com/tutorial/response-model/#response-model-parameter). Читать от **response_model Parameter** до конца **Add an output model**; затем **Return Type and Data Filtering** с подразделами, остановиться перед **See it in the docs**.
  - Цель: отдельный публичный ответ без внутренних заметок и лишних полей ORM.
- [ ] [FastAPI — Handling Errors](https://fastapi.tiangolo.com/tutorial/handling-errors/#use-httpexception). Читать **Use HTTPException**, включая пример **Raise an HTTPException in your code**, остановиться перед **Add custom headers**.
  - Цель: явные ответы для недоступной ссылки и отсутствие случайных 500; конкретные коды согласуем в постановке.

### 3.3.3. Задача Celery для демооплаты

- [ ] [Celery — Tasks](https://docs.celeryq.dev/en/stable/userguide/tasks.html). Читать вступление от заголовка **Tasks** до оглавления; затем **Basics** вместе с **Bound tasks**, остановиться перед **Task inheritance**.
  - Цель: задача, повторная доставка, подтверждение сообщения и отличие аргументов задачи от живых ORM-объектов. Настройки подтверждения выбирать осознанно, не копировать автоматически.
- [ ] [SQLAlchemy — Using multiple asyncio event loops](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-multiple-asyncio-event-loops). Читать только этот раздел, остановиться перед **Using asyncio scoped session**.
  - Цель: понять ограничения AsyncEngine/pool при запуске async-кода из синхронной Celery-задачи. Это материал для выбора жизненного цикла, не требование обязательно применять NullPool.

### 3.3.4. Подтверждение оплаты и состояние обработки

- [ ] [MDN — 202 Accepted](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/202). Читать описание и **Examples** с ответом и адресом проверки статуса; **Specifications** и ниже пропустить.
  - Цель: принятие к обработке не означает завершённую оплату.
- [ ] [Celery — Calling Tasks](https://docs.celeryq.dev/en/stable/userguide/calling.html). Читать **Basics** до **Linking (callbacks/errbacks)**; отдельно **Message Sending Retry** и **Connection Error Handling**, остановиться перед **Serializers**.
  - Цель: публикация задания, её ошибки и отличие повторов публикации от повторов выполнения воркером.

### 3.3.5. Клиентская страница

- [ ] [FastAPI — Templates](https://fastapi.tiangolo.com/advanced/templates/#using-jinja2templates). Читать от **Using Jinja2Templates** через **Writing templates**, включая **Template Context Values**; остановиться перед **Template url_for Arguments**.
  - Цель: минимальный серверный HTML с явно переданными данными. Отдельный frontend-фреймворк не нужен.
- [ ] [MDN — Using the Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch). Читать **Making a request**: **Setting the method**, **Setting a body**, **Setting headers**; затем **Handling the response**: **Checking response status** и **Reading the response body**. Остальные подразделы пока пропустить.
  - Цель: запрос подтверждения и чтение результата, различие сетевой ошибки и HTTP-отказа. Нужен при выборе страницы с JavaScript; при обычной HTML-форме материал можно отложить.

### 3.3.6. Сбои, повторы и кэш после оплаты

- [ ] [Celery — Retrying](https://docs.celeryq.dev/en/stable/userguide/tasks.html#retrying). Читать от **Retrying** через **Automatic retry for known exceptions** с параметрами `max_retries`, `retry_backoff`, `retry_backoff_max`, `retry_jitter`; остановиться перед **Argument validation with Pydantic**.
  - Цель: ограниченные повторы для временных ошибок, а не для доменного отказа. Не считать повтор откатом уже завершённой транзакции.
- [ ] [Redis — DEL](https://redis.io/docs/latest/commands/del/). Повторить описание и **Examples**, остальные разделы пропустить. Рядом перечитать локальный [контракт транзакций](./handoff-stage-3.3.md#критичные-технические-договорённости): пункты про commit и кэш.
  - Цель: безопасное повторное удаление ключа; Redis и PostgreSQL не одна транзакция.

### 3.3.7. Доставка ссылки клиенту и повтор отправки

PDF исключён 16 октября 2026. Нужна доставка текстового письма со ссылкой; PDF-библиотеку и цепочки ради PDF изучать не требуется. Материал о цепочках сохранён ниже как необязательная историческая справка.

- [ ] Необязательно, вне текущей задачи: [Celery — Canvas / Chains](https://docs.celeryq.dev/en/stable/userguide/canvas.html#chains). Читать только **Chains**, включая обработку ошибок цепочки, остановиться перед **Groups**.
  - Цель: передача результата между существующими PDF/email-задачами и поведение при ошибке.
- [ ] [Python 3.12 — smtplib exceptions](https://docs.python.org/3.12/library/smtplib.html#smtplib.SMTPException). Читать описания исключений от **SMTPException** до **SMTPNotSupportedError** включительно; остановиться перед **SMTP Objects**.
  - Цель: различать ошибки соединения, аутентификации и отказ адресата; решение о повторе зависит от причины. Даже ошибка отправки не всегда доказывает отсутствие доставки.

### 3.3.8. Итоговые проверки

- [ ] [Celery — Tasks and unit tests](https://docs.celeryq.dev/en/stable/userguide/testing.html#tasks-and-unit-tests). Читать весь раздел **Tasks and unit tests**, остановиться перед **pytest**.
  - Цель: различать тест функции, подмену зависимостей и имитацию eager mode.
- [ ] [Celery — pytest](https://docs.celeryq.dev/en/stable/userguide/testing.html#pytest). Читать **Enabling**, **Marks** и **Fixtures**, в Fixtures — только `celery_app` и `celery_worker`; остановиться перед **Session scope**.
  - Цель: первый тест с настоящим тестовым воркером. Его пишет пользователь после согласования изолированного окружения; ассистент дополняет повторяющиеся сценарии. `celery.contrib.pytest` и Docker-плагин `pytest-celery` — разные инструменты, оба устанавливать не требуется. Сначала выбрать подходящий вариант проверки.

Мои заметки по 3.3:

## Инвалидация после оплаты — перенесено из 3.2 в задачу 3.3.6

Исторические материалы ниже сохранены вместе с отметками. Отдельную pay_invoice_with_cache не реализуем ради старой постановки: подключение кэша будет в фактическом вызывающем слое оплаты.

- [ ] Повторено: [SQLAlchemy — Managing Transactions](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html) — пример `with session.begin():` и следующий поясняющий абзац; остановиться перед «The session may also be used in a commit-as-you-go approach».
  - На что обратить внимание: нормальный возврат из нашей pay_invoice_in_db происходит после завершения её контекста транзакции. Redis не участвует в транзакции PostgreSQL; ошибка удаления кэша после commit не откатывает оплату.
  - Мои заметки:

- [ ] Повторено: [Redis — DEL](https://redis.io/docs/latest/commands/del/) — описание и Examples, остальные разделы пропустить.
  - На что обратить внимание: удаление отсутствующего ключа допустимо. Повтор подтверждённой оплаты может повторно инвалидировать кэш без изменения paid_at.
  - Мои заметки:

## Redis — удаление ключа и абсолютный срок истечения

- [ ] Прочитано: [Redis — DEL](https://redis.io/docs/latest/commands/del/) — описание команды и раздел Examples; остальные разделы пропустить.
  - На что обратить внимание: удаляет указанные ключи, отсутствующий ключ не считается ошибкой. В проекте `await conn.delete(key)` удаляет кэш одного пользователя после изменения данных.
  - Мои заметки:

- [ ] Прочитано: [Redis — SET](https://redis.io/docs/latest/commands/set/) — синтаксис, опции `EX seconds` и `EXAT timestamp`; остальные опции пропустить.
  - На что обратить внимание: EX — относительное число секунд, EXAT — абсолютный Unix timestamp в секундах. Выбирается одна из этих опций. Истечение отслеживает Redis, отдельный Python-процесс в полночь не нужен.
  - Мои заметки:

- [ ] Справка: [redis-py — set](https://redis.readthedocs.io/en/stable/commands.html#redis.commands.core.BasicKeyCommands.set) — только сигнатура и описание параметра `exat`, до следующего метода.
  - На что обратить внимание: в асинхронном клиенте используется `await conn.set(..., exat=...)`; срок для текущей задачи — более ранний момент из следующей полуночи UTC и 60 секунд после расчёта.
  - Мои заметки:

## Этап 3.2 — дата UTC и актуальность кэша

- [ ] Прочитано: [Redis — SET](https://redis.io/docs/latest/commands/set/) — синтаксис и описание опции `EX seconds`; остальные опции пока пропустить.
  - На что обратить внимание: TTL ограничивает срок хранения записи, но не проверяет, актуальна ли дата использованных расчётов. Даже ответ моложе 60 секунд может относиться ко вчерашнему дню UTC.
  - Мои заметки:

- [ ] Повторено: [Правила проекта](domain.md) — раздел «Сроки и просрочка» до «Демооплата, отзыв и конкурентность», следующий раздел не читать.
  - На что обратить внимание: просрочка вычисляется при чтении и не требует изменения статуса счёта; список и агрегаты должны использовать одну дату UTC.
  - Мои заметки:

## Этап 3.2 — финансовые поля списка сделок

- [ ] Повторено: [Правила проекта](domain.md) — раздел «Дашборд» до «Контрольные сценарии», следующий раздел не читать.
  - На что обратить внимание: список с пагинацией содержит стоимость сделки, оплаченную сумму и остаток к оплате. ISSUED не уменьшает остаток к оплате.
  - Мои заметки:

- [ ] Прочитано: [SQLAlchemy — ORDER BY](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html#the-order-by-clause) — от заголовка «The ORDER BY clause» до «Aggregate functions with GROUP BY / HAVING», следующий раздел не читать.
  - На что обратить внимание: для воспроизводимой пагинации нужен явно заданный порядок; уникальный ключ позволяет разрешить совпадения основного поля сортировки.
  - Мои заметки:

## Этап 3.2 — финансовая сводка и кэш

- [ ] Прочитано: [Правила проекта](domain.md) — от заголовка «Дашборд» до «Контрольные сценарии», следующий раздел не читать.
  - На что обратить внимание: показатели за всё время текущего пользователя; просрочка входит в ISSUED, а не прибавляется к нему; DRAFT и CANCELLED исключены.
  - Мои заметки:

- [ ] Прочитано: [SQLAlchemy — Special Modifiers WITHIN GROUP, FILTER](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html#special-modifiers-within-group-filter) — только часть про `FunctionElement.filter()`, от предложения с этим именем до конца примера FILTER; WITHIN GROUP пропустить.
  - На что обратить внимание: разные условия у нескольких агрегатов в одном SELECT; COUNT считает строки, SUM складывает суммы. Это возможный способ расчёта, не обязательная форма реализации.
  - Мои заметки:

## Этап 3.2 — два остатка в ответе API

- [ ] Повторено: [Правила проекта](domain.md) — от заголовка «Два остатка» до «Сроки и просрочка», следующий раздел не читать.
  - На что обратить внимание: доступно для выставления = стоимость − ISSUED − PAID; осталось оплатить = стоимость − PAID. Черновики и отменённые счета не влияют на остатки.
  - Мои заметки:

- [ ] Прочитано: [FastAPI — Return Type and Data Filtering](https://fastapi.tiangolo.com/tutorial/response-model/#return-type-and-data-filtering) — от этого заголовка до «Response Model encoding parameters», следующий раздел не читать.
  - На что обратить внимание: расширение модели ответа через наследование; объявленная модель определяет поля JSON. Для подробного GET сделки можно иметь отдельную модель, сохранив прежние ответы остальных маршрутов. Примеры разных версий Python читать только в одном подходящем варианте.
  - Мои заметки:

## Повторение на 14 октября 2026 — сессии, транзакции и загрузка данных

Это материалы для разбора перед продолжением этапа 3.2, не новые задачи этапа. Разбирать по одному блоку: чтение → ответы своими словами → обсуждение непонятного. Самостоятельное понимание этих механизмов пока не считать подтверждённым только по прошедшим тестам.

### 1. FastAPI: почему одна сессия оказалась в двух местах

- [ ] Прочитано: [Using the same dependency multiple times](https://fastapi.tiangolo.com/tutorial/dependencies/sub-dependencies/#using-the-same-dependency-multiple-times) — от этого заголовка до следующего раздела, включая пример `use_cache=False`.
  - Суть: FastAPI по умолчанию повторно использует результат зависимости внутри одного HTTP-запроса. Если авторизация и обработчик зависят от `get_db`, они могут получить один объект AsyncSession. Это не Redis и не кэш результатов SQL.
  - В нашем PATCH: сначала `current_user`, затем `session = Depends(get_db, use_cache=False)`. Для этого использования FastAPI заново вызывает `get_db`, который создаёт отдельную сессию. Сам флаг не сбрасывает транзакцию и не отключает кэш зависимости глобально.
  - Самопроверка: что именно кэшируется? Почему чтение пользователя мешало `session.begin()`? Создаёт ли `use_cache=False` новую сессию сам или это делает `get_db`?
  - Мои заметки:

### 2. SQLAlchemy: сессия и граница транзакции

- [ ] Прочитано: [Auto Begin](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#auto-begin) — от заголовка «Auto Begin» до подзаголовка «Disabling autobegin to prevent implicit transactions», подзаголовок и далее не читать.
- [ ] Повторено: [Managing Transactions](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html) — начало раздела, пример `with session.begin():` и следующий поясняющий абзац; остановиться перед «The session may also be used in a commit-as-you-go approach».
  - Суть: AsyncSession управляет ORM-объектами и работой с БД; транзакция задаёт границу фиксации или отката. Даже SELECT может начать транзакцию автоматически. `async with session.begin()` требует отсутствия уже начатой транзакции и делает commit при нормальном выходе, rollback при исключении.
  - `async with session as session` не создаёт новую сессию: это контекст уже переданного объекта, который закрывает его при выходе. В нашем HTTP-коде жизненным циклом сессии занимается `get_db`, операцией — блок `session.begin()`.
  - Самопроверка: почему SELECT способен привести к «transaction already begun»? Что произойдёт с названием и суммой, если внутри `begin()` выброшен ValueError? Отменяет ли сам по себе HTTP 409 изменения в БД?
  - Мои заметки:

### 3. Почему успешный PATCH терял изменения

- [ ] Прочитано: [Flushing](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#flushing) — начало раздела до примера `session.flush()` включительно; остальное пока пропустить.
- [ ] Прочитано: [Refreshing / Expiring](https://docs.sqlalchemy.org/en/20/orm/session_state_management.html#refreshing-expiring) — найти абзац «Another key behavior of both Session.expire() and Session.refresh()…» о потере незаписанных изменений, прочитать его и следующий пример; остановиться после результата примера.
  - `setattr` меняет объект в памяти; `flush` отправляет изменения в БД, но не фиксирует транзакцию; `refresh` перечитывает объект из БД; commit фиксирует транзакцию. `session.add()` сам по себе не выполняет UPDATE.
  - В исправленном PATCH: изменения → `flush()` → `refresh()` → успешный выход из `begin()`. Refresh загружает в том числе вычисленный БД `updated_at`. Это порядок для этой операции, а не требование делать refresh после каждого UPDATE вообще.
  - Самопроверка: что потеряется при refresh до flush? Можно ли откатить изменения после flush? Когда в текущей функции происходит commit, если return стоит внутри begin?
  - Мои заметки:

### 4. Связь с ORM-объектом и блокировка строки — разные вещи

- [ ] Прочитано: [Joined Eager Loading](https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html#joined-eager-loading) — начало раздела и первый пример с `joinedload`; остановиться перед следующим примечанием «Tip».
- [ ] Повторено: [Row-Level Locks](https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-ROWS) — вступление раздела и пункт `FOR UPDATE`; остановиться перед `FOR NO KEY UPDATE`.
  - `Invoice.deal` — связь, `Deal.amount` — столбец. Joinedload принимает связь и загружает связанный объект вместе с основным; отдельный SELECT сделки не обязан заполнить `invoice.deal`. Lazy='raise' запрещает неявную загрузку связи. Загрузка объекта сама по себе не означает блокировку строки.
  - Проверка финансового лимита читает сумму после блокировки общей сделки. Обычный SELECT разрешён при FOR UPDATE; согласованная блокировка нужна операциям, которые меняют финансовое состояние.
  - Самопроверка: почему `joinedload(Deal.amount)` неверен? Почему блокировка только во время UPDATE слишком поздняя для проверки суммы? Почему две операции блокируют одну сделку, даже если меняют разные счета?
  - Мои заметки:

## Этап 3.2 — изменение стоимости сделки

- [ ] Прочитано: [Правила проекта](domain.md) — от заголовка «Два остатка» до заголовка «Сроки и просрочка», не включая следующий раздел.
  - На что обратить внимание: занятая сумма включает ISSUED и PAID; стоимость сделки не должна становиться меньше этой суммы.
  - Мои заметки:

- [ ] Повторено: [SQLAlchemy — Managing Transactions](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html) — начало раздела до примера `with session.begin():` включительно и следующий поясняющий абзац; остановиться перед «The session may also be used in a commit-as-you-go approach».
  - На что обратить внимание: проверка и все поля одного PATCH должны входить в одну транзакцию; исключение отменяет всю операцию. В нашем асинхронном коде используется `async with session.begin()`.
  - Мои заметки:

## Этап 3.2 — расчёт сумм счетов сделки

- [ ] Прочитано: [PostgreSQL — Aggregate Functions](https://www.postgresql.org/docs/current/functions-aggregate.html) — строка `sum` в таблице и абзац о результате при отсутствии строк.
  - На что обратить внимание: `SUM` складывает значения выбранных строк; без подходящих строк возвращает `NULL`, а не ноль. Для `numeric` результат также `numeric`.
  - Мои заметки:

- [ ] Прочитано: [PostgreSQL — COALESCE](https://www.postgresql.org/docs/current/functions-conditional.html#FUNCTIONS-COALESCE).
  - На что обратить внимание: возвращает первый аргумент, отличный от `NULL`; позволяет задать нулевой результат для пустой суммы. Аргументы должны приводиться к общему типу.
  - Мои заметки:

- [ ] Прочитано: [SQLAlchemy — Working with SQL Functions](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html#working-with-sql-functions) — начало раздела с `func` и агрегатами; справка по [sum](https://docs.sqlalchemy.org/en/20/core/functions.html#sqlalchemy.sql.functions.sum) и [coalesce](https://docs.sqlalchemy.org/en/20/core/functions.html#sqlalchemy.sql.functions.coalesce).
  - На что обратить внимание: `func` строит SQL-выражения, вычисляемые базой; выражения можно вкладывать друг в друга и передавать в `select`. Для общей суммы отфильтрованного набора `GROUP BY` не обязателен.
  - Мои заметки:

- [ ] Прочитано: [SQLAlchemy — AsyncSession.scalar](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#sqlalchemy.ext.asyncio.AsyncSession.scalar).
  - На что обратить внимание: асинхронное выполнение запроса с получением одного скалярного значения; денежный результат должен оставаться `Decimal`, включая ноль.
  - Мои заметки:

## Проверка отката при искусственном сбое

- [ ] Прочитано: [pytest — monkeypatch функций](https://docs.pytest.org/en/stable/how-to/monkeypatch.html#monkeypatching-functions).
  - На что обратить внимание: временная замена функции через `monkeypatch.setattr`; заменять имя в модуле, где его использует проверяемый код. Исходную функцию сохранить до подмены.
  - Мои заметки:

- [ ] Прочитано: [SQLAlchemy — Flushing](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#flushing).
  - На что обратить внимание: flush отправляет изменения в БД внутри текущей транзакции, но не фиксирует их. В AsyncSession вызывается `await session.flush()`; rollback может отменить эти изменения.
  - Мои заметки:

## Интеграционная проверка сохранения

- [ ] Прочитано: [SQLAlchemy — AsyncSession.get](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#sqlalchemy.ext.asyncio.AsyncSession.get).
  - На что обратить внимание: получение ORM-объекта по первичному ключу, возврат `None` при отсутствии записи. В тесте проверяй именно объект из новой сессии и явно утверждай, что он существует.
  - Мои заметки:

- [ ] Прочитано: [SQLAlchemy — async_sessionmaker](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#sqlalchemy.ext.asyncio.async_sessionmaker).
  - На что обратить внимание: фабрика создаёт отдельные сессии; для подготовки данных, вызова сервиса и независимого чтения используй разные сессии из тестовой фикстуры `session_pool`.
  - Мои заметки:

- [ ] Прочитано: [Локальное тестовое окружение](testing-stage-24.md) — только раздел «Изолированное окружение».
  - На что обратить внимание: выделенная тестовая БД, `CRM_TEST_SERVICES=1`; интеграционные тесты нельзя запускать с `--noconftest`. Очистку обеспечивает фикстура `clean_tables`, одной `session_pool` недостаточно.
  - Мои заметки:

## Граница транзакции бизнес-операции

- [ ] Прочитано: [SQLAlchemy — Managing Transactions](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html).
  - На что обратить внимание: начало страницы, контекст `session.begin()`, commit при успешном выходе и rollback при исключении. SELECT может запускать транзакцию автоматически (autobegin).
  - Мои заметки:

- [ ] Прочитано: [SQLAlchemy — AsyncSession.begin](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#sqlalchemy.ext.asyncio.AsyncSession.begin).
  - На что обратить внимание: `async with session.begin()`; для первой сервисной операции передаём отдельную сессию без уже начатой транзакции.
  - Мои заметки:

## Вызов асинхронных функций

- [ ] Прочитано: [Python — Coroutines](https://docs.python.org/3.12/library/asyncio-task.html#coroutines).
  - На что обратить внимание: вызов `async def` возвращает объект корутины; для получения результата в другой async-функции используется `await`.
  - Мои заметки:

## Синтаксис assert

- [ ] Прочитано: [Python — оператор assert](https://docs.python.org/3.12/reference/simple_stmts.html#the-assert-statement).
  - На что обратить внимание: `assert условие, сообщение` проверяет только условие до запятой. Для двух независимых проверок используй две строки `assert`.
  - Мои заметки:

## Имена функций и повторное определение

- [ ] Прочитано: [Python — определения функций](https://docs.python.org/3.12/reference/compound_stmts.html#function-definitions).
  - На что обратить внимание: выполнение `def` связывает имя с объектом функции. Повторный `def` с тем же именем в модуле заменяет предыдущую привязку; pytest не увидит прежнюю функцию под этим именем. Достаточно абзаца «A function definition is an executable statement».
  - Мои заметки:

Здесь только материалы и заметки. Задачи выдаются по одной в диалоге: задача → выполнение → проверка → следующий шаг.

Отметки «прочитано» пользователь ставит самостоятельно: `[ ]` → `[x]`. Наличие ссылки не означает, что материал уже прочитан. Новые материалы добавляются по мере работы; существующие отметки и заметки сохраняются.

## Этап 3.1 — состояния счёта

### Правила выставления и отзыва

- [ ] Прочитано: [Правила проекта](domain.md) — только раздел «Состояния и действия».
  - На что обратить внимание: из какого состояния можно выставить счёт; чем отзыв отличается от окончательной отмены.
  - Мои заметки:

### Работа с enum в Python — справка при необходимости

- [x] Прочитано: [Python Enum — доступ к элементам и сравнение](https://docs.python.org/3.12/howto/enum.html#programmatic-access-to-enumeration-members-and-their-attributes).
  - На что обратить внимание: обращение к элементу через имя класса и сравнение элементов enum. Всю страницу читать не требуется.
  - Мои заметки:

### Отдельные файлы тестов

- [x] Прочитано: [pytest — соглашения об обнаружении тестов](https://docs.pytest.org/en/stable/explanation/goodpractices.html#conventions-for-python-test-discovery).
  - На что обратить внимание: имена файлов `test_*.py` и функций `test_*`. Достаточно этого подраздела.
  - Мои заметки:

### Отказ при запрещённом переходе

- [x] Прочитано: [Python — возбуждение исключений](https://docs.python.org/3.12/tutorial/errors.html#raising-exceptions).
  - На что обратить внимание: `raise ValueError(...)`; проверка должна предшествовать изменению объекта.
  - Мои заметки:

- [x] Прочитано: [pytest — проверка ожидаемых исключений](https://docs.pytest.org/en/stable/how-to/assert.html#assertions-about-expected-exceptions).
  - На что обратить внимание: `with pytest.raises(ValueError)` и проверка неизменности объекта после выхода из блока.
  - Мои заметки:

### Версия выставления — значения по умолчанию

- [x] Прочитано: [SQLAlchemy — Scalar Defaults](https://docs.sqlalchemy.org/en/20/core/defaults.html#scalar-defaults).
  - На что обратить внимание: `default=0` применяется при INSERT, если значение не передано; для обычной ORM-модели это не обещает ноль сразу после `Invoice()`.
  - Мои заметки:

- [x] Прочитано: [SQLAlchemy — Server-invoked DDL-Explicit Default Expressions](https://docs.sqlalchemy.org/en/20/core/defaults.html#server-invoked-ddl-explicit-default-expressions).
  - На что обратить внимание: `server_default` задаёт значение по умолчанию на стороне БД; изменение модели не изменяет существующую таблицу без миграции.
  - Мои заметки:

### Миграция поля версии

- [x] Прочитано: [Alembic — создание миграции](https://alembic.sqlalchemy.org/en/latest/tutorial.html#create-a-migration-script).
  - На что обратить внимание: команда `alembic revision`, функции `upgrade` и `downgrade`. На этом шаге только подготовка файла, без применения к БД.
  - Мои заметки:

- [ ] Прочитано: [Alembic — add_column](https://alembic.sqlalchemy.org/en/latest/ops.html#alembic.operations.Operations.add_column).
  - На что обратить внимание: тип колонки, `nullable` и `server_default`; Python-параметр `default` не заменяет значение по умолчанию на стороне БД.
  - Мои заметки:

### Чтение строки с блокировкой

- [x] Прочитано: [PostgreSQL — Row-Level Locks](https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-ROWS).
  - На что обратить внимание: пункт FOR UPDATE; конкурирующие изменения и блокирующие чтения ждут освобождения блокировки, обычный SELECT не блокируется. Блокировка обычно удерживается до завершения транзакции, не до выхода из Python-функции.
  - Мои заметки:

- [x] Прочитано: [SQLAlchemy — with_for_update](https://docs.sqlalchemy.org/en/20/core/selectable.html#sqlalchemy.sql.expression.GenerativeSelect.with_for_update).
  - На что обратить внимание: вызов `.with_for_update()` у SELECT; для первого шага без `nowait` и `skip_locked`.
  - Мои заметки:

### HTTP-маршруты переходов состояния

- [ ] Прочитано: [SQLAlchemy — предотвращение неявного ввода-вывода в AsyncSession](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#preventing-implicit-io-when-using-asyncsession).
  - На что обратить внимание: чтение незагруженного ORM-атрибута может потребовать SQL; синхронная сериализация не может выполнить такой запрос. Явный `await session.refresh(invoice)` загружает данные до сериализации.
  - Мои заметки:

- [ ] Прочитано: [FastAPI — асинхронные тесты](https://fastapi.tiangolo.com/advanced/async-tests/#example).
  - На что обратить внимание: запросы через `await client.post(...)` и проверки ответа. В проекте используй готовую фикстуру `client`; создавать новый клиент и копировать маркер AnyIO из примера не нужно.
  - Мои заметки:

- [ ] Прочитано: [FastAPI — HTTPException](https://fastapi.tiangolo.com/tutorial/handling-errors/#use-httpexception).
  - На что обратить внимание: исключение прерывает обработчик; отсутствие счёта отображаем в 404, запрещённый переход — в 409.
  - Мои заметки:

- [ ] Прочитано: [FastAPI — повторное использование зависимостей](https://fastapi.tiangolo.com/tutorial/dependencies/sub-dependencies/#using-the-same-dependency-multiple-times).
  - На что обратить внимание: кэширование зависимости в рамках запроса и `Depends(get_db, use_cache=False)` для отдельной сессии обработчика. Чтение пользователя при авторизации уже запускает транзакцию в сессии авторизации.
  - Мои заметки:

### Конкурентные операции

- [ ] Прочитано: [PostgreSQL — функции информации о сервере и сеансе](https://www.postgresql.org/docs/current/functions-info.html#FUNCTIONS-INFO-SESSION).
  - На что обратить внимание: `pg_backend_pid()` возвращает PID текущего соединения; `pg_blocking_pids(pid)` — PID соединений, блокирующих указанное. В `test_payment_locks_before_revoke` отдельная третья сессия проверяет, что именно оплата блокирует отзыв, прежде чем разрешить commit оплаты.
  - Мои заметки:

- [ ] Прочитано: [Python — asyncio.wait_for](https://docs.python.org/3.12/library/asyncio-task.html#asyncio.wait_for).
  - На что обратить внимание: ограничивает ожидание сигнала или завершения операции; при таймауте отменяет ожидаемую задачу. В тесте `finally` освобождает Event, отменяет незавершённые задачи и дожидается их завершения до закрытия сессий.
  - Мои заметки:

- [ ] Прочитано: [SQLAlchemy — text](https://docs.sqlalchemy.org/en/20/core/sqlelement.html#sqlalchemy.sql.expression.text).
  - На что обратить внимание: параметр диагностического SQL передаётся отдельно: `text('SELECT pg_blocking_pids(:pid)')` и `{'pid': backend_pid}`. Короткий `sleep` в цикле лишь ограничивает частоту опроса; доказательство блокировки — ответ PostgreSQL, не прошедшее время.
  - Мои заметки:

- [ ] Прочитано: [Python — asyncio.Event](https://docs.python.org/3.12/library/asyncio-sync.html#asyncio.Event).
  - На что обратить внимание: `await event.wait()` ждёт сигнал, `event.set()` разрешает продолжить выполнение. Event управляет порядком действий в тесте, но не заменяет блокировку PostgreSQL.
  - Мои заметки:

- [ ] Прочитано: [Python — asyncio.create_task](https://docs.python.org/3.12/library/asyncio-task.html#asyncio.create_task).
  - На что обратить внимание: запускает корутину как задачу; сохрани ссылку и дождись завершения. `task.done()` показывает завершение задачи, а не причину ожидания.
  - Мои заметки:

- [x] Прочитано: [Python — asyncio.gather](https://docs.python.org/3.12/library/asyncio-task.html#asyncio.gather).
  - На что обратить внимание: конкурентный запуск корутин, порядок результатов соответствует порядку аргументов, `return_exceptions=True` возвращает исключения в списке результатов.
  - Мои заметки:

- [ ] Прочитано: [SQLAlchemy — AsyncSession и конкурентные задачи](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-asyncsession-with-concurrent-tasks).
  - На что обратить внимание: каждой конкурентной операции нужна собственная сессия; нельзя передавать одну AsyncSession двум задачам gather.
  - Мои заметки:

### Внутренняя операция оплаты — время UTC

- [x] Прочитано: [Python — aware и naive datetime](https://docs.python.org/3.12/library/datetime.html#aware-and-naive-objects).
  - На что обратить внимание: дата-время с часовым поясом, `datetime.now(timezone.utc)` и получение даты UTC через `.date()`. Повтор подтверждения той же оплаты не должен менять первоначальный `paid_at`.
  - Мои заметки:

### Актуальные значения уже загруженного ORM-объекта

- [x] Прочитано: [SQLAlchemy — Populate Existing](https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#populate-existing).
  - На что обратить внимание: `.execution_options(populate_existing=True)` обновляет уже загруженный объект данными результата SELECT. Для наших блокирующих чтений применяется до изменения объектов; не использовать для перезаписи собственных несохранённых правок.
  - Мои заметки:

