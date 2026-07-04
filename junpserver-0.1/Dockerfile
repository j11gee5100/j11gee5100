# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN set -eux; \
    sed -i 's|http://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g; s|http://security.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      build-essential \
      curl \
      default-libmysqlclient-dev \
      libpcre3-dev \
      pkg-config; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com -r /app/requirements.txt

COPY app /app/app
COPY scripts/inference_env_mcp_stdio.py /app/scripts/inference_env_mcp_stdio.py
COPY scripts/inference_env_mcp_launcher.py /app/scripts/inference_env_mcp_launcher.py
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY docker/api/uwsgi.ini /app/docker/api/uwsgi.ini
COPY docker/api/entrypoint.sh /entrypoint.sh

RUN useradd --system --create-home --home-dir /home/app app \
    && mkdir -p /data/env-packages /data/delivery-bundles /tmp/opspaw-delivery-bundles \
    && chown -R app:app /app /data /tmp/opspaw-delivery-bundles \
    && chmod +x /entrypoint.sh /app/scripts/inference_env_mcp_stdio.py /app/scripts/inference_env_mcp_launcher.py

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uwsgi", "--ini", "/app/docker/api/uwsgi.ini"]
