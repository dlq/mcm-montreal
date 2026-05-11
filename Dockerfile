FROM python:3.12-slim

LABEL org.opencontainers.image.title="Montreal MCM"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8080

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app.py ./
COPY mcm ./mcm
COPY templates ./templates
COPY static ./static
COPY scripts/start.sh ./scripts/start.sh

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["sh", "/app/scripts/start.sh"]
