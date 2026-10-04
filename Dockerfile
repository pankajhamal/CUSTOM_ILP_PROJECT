# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: builder — resolve and install dependencies into a venv.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.2 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_NO_INTERACTION=1

WORKDIR /app

RUN pip install "poetry==${POETRY_VERSION}"

# Copy only dependency manifests first to maximize layer caching.
COPY pyproject.toml ./
# poetry.lock is gitignored; copy if present (wildcard keeps build working without it).
COPY poetry.loc[k] ./

# Export a requirements file and install into a local venv.
RUN poetry install --only main --no-root

# ---------------------------------------------------------------------------
# Stage 2: runtime — minimal image with just the venv + app code.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Create an unprivileged user.
RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

# Bring the resolved virtualenv over from the builder.
COPY --from=builder /app/.venv /app/.venv

# Copy application source.
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

USER app

EXPOSE 8000

# Liveness probe hits the health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
