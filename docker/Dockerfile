# ── Builder stage — installs dependencies with full build toolchain ───────────
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Final stage — slim runtime, no compiler/build toolchain shipped ───────────
FROM python:3.11-slim

# Non-root user: the app's default SQLite dev DB writes to the working
# directory, so this user needs ownership of /app, not just permission to
# run the process.
RUN useradd --create-home --shell /bin/bash app

WORKDIR /app

COPY --from=builder /root/.local /home/app/.local
COPY --chown=app:app . .

ENV PATH=/home/app/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

RUN chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
