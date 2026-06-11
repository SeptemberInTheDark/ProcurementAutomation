# Procurement API

Mini-backend дипломного проекта на Django REST Framework.

## Локальный запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd app
export CELERY_TASK_ALWAYS_EAGER=True
python manage.py migrate
python manage.py test backend
python manage.py runserver
```

API будет доступен на `http://127.0.0.1:8000/api/v1/`.
Swagger UI доступен на `http://127.0.0.1:8000/api/docs/`, схема OpenAPI - на `http://127.0.0.1:8000/api/schema/`.

## Docker

Из корня репозитория:

```bash
docker compose up --build
```

Сервис поднимет PostgreSQL, Redis, Celery worker, применит миграции и запустит API на `http://127.0.0.1:8000/api/v1/`.

Основные endpoint'ы:

- `POST /api/v1/user/register`
- `POST /api/v1/user/register/confirm`
- `POST /api/v1/user/login`
- `GET /api/v1/products`
- `GET|POST|PUT|DELETE /api/v1/basket`
- `GET|POST|DELETE /api/v1/user/contact`
- `GET|POST /api/v1/order`
- `POST /api/v1/partner/update`
- `GET|POST /api/v1/partner/state`

Для фоновой отправки писем используется Celery. В локальных тестах задачи можно выполнять синхронно через переменную `CELERY_TASK_ALWAYS_EAGER=True`.
