FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN pip install uv && uv sync --frozen

ENV PYTHONUNBUFFERED=1

COPY . .

CMD ["uv", "run", "fastapi", "run", "backend/app/main.py", "--host", "0.0.0.0", "--port", "8000"]

