# syntax=docker/dockerfile:1

# --- Build: resolve the locked dependency set into a virtualenv ----------------
FROM python:3.12-slim-trixie AS build

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, so source edits don't invalidate this layer.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# --- Runtime: interpreter + virtualenv only, as an unprivileged user ----------
FROM python:3.12-slim-trixie

RUN groupadd --system --gid 10001 aura \
    && useradd --system --uid 10001 --gid aura --no-create-home aura

COPY --from=build --chown=aura:aura /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER aura
EXPOSE 8080

# openstacksdk reads clouds.yaml from /etc/openstack; mount it read-only there.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)"]

CMD ["uvicorn", "aura_api.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--no-server-header"]
