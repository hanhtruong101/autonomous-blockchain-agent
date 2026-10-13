FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /usr/local/bin/uv
WORKDIR /workspace
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
COPY apps/api apps/api
COPY scripts scripts
COPY contracts contracts
COPY alembic.ini ./
ENV PYTHONPATH=/workspace/apps/api
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
