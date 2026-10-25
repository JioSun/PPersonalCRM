# Локальный запуск и приёмка 4.1

## Обычный запуск

Из корня проекта скопировать `.env.example` в `.env`, только если `.env` ещё нет.
Заменить примерные секреты; не коммитить `.env`. PostgreSQL в текущем Compose
использует пользователя `postgres` и БД `personalcrm`: значения приложения должны
совпадать с ними. Изменение переменных не изменяет уже инициализированную БД.
Для запуска без отправки писем и AI-вызовов допустимы заполненные заглушки
SMTP/Gemini; настоящие интеграции с ними работать не будут.

```powershell
docker compose up -d --build
docker compose ps -a
docker compose logs migration
Invoke-RestMethod http://127.0.0.1:8000/
```

Миграции ждут healthy PostgreSQL. API ждёт успешного завершения миграций и
готовности PostgreSQL/Redis. Нормальный результат migration — `Exited (0)`:
это одноразовый процесс, а не постоянно работающий сервер.

Публикация только на loopback: API 8000, PostgreSQL 5432, Redis 6379.
Внутри сети Compose API обращается к `postgres:5432` и `redis:6379`.
`MAIN_URL=http://localhost:8000` — адрес для локальных ссылок оплаты.

При следующем обновлении схемы перед запуском нового API явно выполнить:

```powershell
docker compose run --rm migration
```

Если команда завершилась ошибкой, не продолжать выпуск. Это не обещание
автоматического применения новых миграций при любом перезапуске контейнера.

Данные: Compose-volume `postgres_persistence_check`, путь PostgreSQL 17
`/var/lib/postgresql/data`. Историческое имя volume сохранено намеренно:
переименование подключит другое хранилище и не перенесёт существующую БД.
Не использовать `down -v` и не удалять volumes с нужными данными.

## Повторение проверки на изолированных ресурсах

Использовать отдельную временную папку вне контекста сборки и новое уникальное
имя проекта Compose. Скопировать туда `.env.example` как `.env` и `compose.yaml`.
В копии изменить только `build: .` на абсолютный путь проекта и внешние порты
на динамические loopback-порты: `127.0.0.1::8000`, `127.0.0.1::5432`,
`127.0.0.1::6379`. Не копировать рабочий `.env`.

Ниже `$acceptanceFile` — абсолютный путь этой копии, `$acceptanceProject` —
новое имя только для приёмки. Все команды запускать с этими двумя параметрами.
`compose.test.yaml` и его ресурсы в этой проверке не используются.

```powershell
docker compose -p $acceptanceProject -f $acceptanceFile up -d --build
docker compose -p $acceptanceProject -f $acceptanceFile ps -a
docker compose -p $acceptanceProject -f $acceptanceFile logs migration
docker compose -p $acceptanceProject -f $acceptanceFile port backend 8000
```

По выведенному порту проверить GET `/`. В пустой БД миграции должны создать
схему и `alembic_version`. Создать синтетического владельца и клиента,
зафиксировать транзакцию и прочитать клиента отдельным запросом. Сохранить
ID контейнера через `docker compose ... ps -q postgres`, затем:

```powershell
docker compose -p $acceptanceProject -f $acceptanceFile up -d --no-deps --force-recreate --wait postgres
```

Подтвердить новый ID контейнера, прежний volume и прочитать того же клиента
через новое подключение. Не создавать запись повторно после пересоздания.
По окончании `docker compose -p $acceptanceProject -f $acceptanceFile down`
удаляет только контейнеры/сеть приёмки, оставляя volume.

## Проверено 22 октября 2026

- Проект приёмки: `personalcrm-stage41-20261022`, новый volume
  `personalcrm-stage41-20261022_postgres_persistence_check`.
- Копия Compose и пример окружения: временная папка
  `C:/Users/gobly/AppData/Local/Temp/personalcrm-stage41-20261022`.
- Сборка текущего Dockerfile успешна (слои зависимостей использовали кеш;
  воспроизводимость образа без кеша относится к 4.2).
- На новой пустой БД прошла вся цепочка миграций до `b66e7a98d473`, exit code 0.
- PostgreSQL/Redis healthy; API запущен после migration. GET `/` с компьютера
  через `127.0.0.1:52541` вернул `{"greetings":"Hello World"}`.
- Все три опубликованных порта приёмки привязаны к `127.0.0.1`.
- SQL создал владельца `stage41-user` и клиента `stage41-client` с именем
  `Persistence check`; это синтетические записи, не реальный пользователь.
- ID PostgreSQL изменился с `badd20da494b…` на `b27f2cefb5f9…`.
  Volume остался прежним; `SHOW data_directory` — `/var/lib/postgresql/data`.
- Новым вызовом psql после пересоздания прочитаны тот же ID, имя и владелец;
  ревизия схемы также сохранилась. Повторного заполнения БД не было.
- Рабочие контейнеры и volumes не изменялись. Реальные AI/SMTP не вызывались.
  Полная регрессия не повторялась: проверялся только контракт 4.1.
