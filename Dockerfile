# syntax=docker/dockerfile:1.7

ARG NODE_IMAGE=node:24.21.0-bookworm-slim
ARG PYTHON_IMAGE=python:3.12.14-slim-bookworm
ARG CADDY_IMAGE=caddy:2.10.2-alpine

FROM ${CADDY_IMAGE} AS gateway
COPY deploy/Caddyfile /etc/caddy/Caddyfile

FROM ${NODE_IMAGE} AS frontend-builder
ENV COREPACK_HOME=/corepack \
    PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH
WORKDIR /build/frontend
RUN corepack enable && corepack prepare pnpm@11.28.5 --activate
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/index.html frontend/tsconfig.json frontend/tsconfig.app.json frontend/vite.config.ts frontend/vitest.config.ts ./
COPY frontend/src ./src
COPY frontend/scripts ./scripts
RUN pnpm run typecheck \
    && pnpm run build \
    && pnpm run check:artifact

FROM ${PYTHON_IMAGE} AS python-builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /build/app
COPY pyproject.toml constraints.lock ./
COPY app ./app
RUN python -m pip wheel --constraint constraints.lock --wheel-dir /wheels .

FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --home-dir /home/app app
WORKDIR /srv/app
COPY --from=python-builder /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels beauty-intelligence-api==0.1.0 \
    && rm -rf /wheels
COPY alembic.ini ./
COPY alembic ./alembic
COPY config ./config
COPY --from=frontend-builder --chown=app:app /build/frontend/dist ./static
RUN mkdir -p /data /backups \
    && chown -R app:app /data /backups /srv/app
USER app:app
EXPOSE 8000
STOPSIGNAL SIGTERM
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers"]
