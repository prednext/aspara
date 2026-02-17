# ==============================================================================
# Aspara Demo - Hugging Face Spaces
# Multi-stage build: frontend (Node.js) + backend (Python/FastAPI)
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Frontend build (JS + CSS + icons)
# ------------------------------------------------------------------------------
FROM node:22-slim AS frontend-builder

WORKDIR /app

# Enable pnpm via corepack
RUN corepack enable && corepack prepare pnpm@10.6.3 --activate

# Install JS dependencies (cache layer)
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy source and build frontend assets
COPY vite.config.js icons.config.json ./
COPY scripts/ ./scripts/
COPY src/aspara/dashboard/ ./src/aspara/dashboard/
RUN pnpm run build:icons && pnpm run build:js && pnpm run build:css

# ------------------------------------------------------------------------------
# Stage 2: Python runtime + sample data generation
# ------------------------------------------------------------------------------
FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy Python project files
COPY pyproject.toml uv.lock ./
COPY space_README.md ./README.md
COPY src/ ./src/

# Install Python dependencies (dashboard extra only, no dev deps)
RUN uv sync --frozen --extra dashboard --no-dev

# Overwrite with built frontend assets
COPY --from=frontend-builder /app/src/aspara/dashboard/static/dist/ ./src/aspara/dashboard/static/dist/

# Generate sample data during build
COPY examples/generate_random_runs.py ./examples/
ENV ASPARA_DATA_DIR=/data/aspara
ENV ASPARA_ALLOW_IFRAME=1
RUN mkdir -p /data/aspara && uv run python examples/generate_random_runs.py

# Create non-root user (HF Spaces best practice)
RUN useradd -m -u 1000 user && \
    chown -R user:user /data /app
USER user

# HF Spaces uses port 7860
EXPOSE 7860

# Start dashboard only (no tracker = no external write API)
CMD ["uv", "run", "aspara", "serve", "--host", "0.0.0.0", "--port", "7860", "--data-dir", "/data/aspara"]
