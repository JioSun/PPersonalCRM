# Материалы по проекту

## Интеграционная проверка сохранения

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

### Актуальные значения уже загруженного ORM-объекта

- [ ] Прочитано: [SQLAlchemy — Populate Existing](https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#populate-existing).
  - На что обратить внимание: `.execution_options(populate_existing=True)` обновляет уже загруженный объект данными результата SELECT. Для наших блокирующих чтений применяется до изменения объектов; не использовать для перезаписи собственных несохранённых правок.
  - Мои заметки:
