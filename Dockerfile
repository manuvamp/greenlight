# Greenlight web demo: the UI, recorded runs (replays) and the eval scoreboard.
# Replays cost nothing to watch. Live runs need a sandbox backend, so they are off unless
# GREENLIGHT_LIVE=1 is set (with Token Factory Sandboxes, or Docker on a machine that has it).

FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 GREENLIGHT_HOME=/tmp/greenlight
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY greenlight/ greenlight/
RUN pip install . fastapi "uvicorn[standard]"
COPY server/ server/
COPY replays/ replays/
COPY evals/dataset.toml evals/dataset.toml
COPY evals/results/eval-nemotron/scoreboard.json evals/results/eval-nemotron/scoreboard.json
COPY examples/ examples/
COPY --from=web /web/dist web/dist
# Hugging Face Spaces routes to port 7860; elsewhere set PORT.
ENV PORT=7860
EXPOSE 7860
CMD ["sh", "-c", "uvicorn server.app:app --host 0.0.0.0 --port ${PORT}"]
