# Meraki WPN Portal Add-on
# Multi-stage build for Home Assistant add-on

# BUILD_FROM is set by HA add-on builder, defaults to python base for standalone
ARG BUILD_FROM="ghcr.io/home-assistant/amd64-base-python:3.13-alpine3.22"

FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Install dependencies
COPY frontend/package*.json ./
RUN npm ci --production=false

# Copy source and build
COPY frontend/ ./
RUN npm run build

# Backend stage - use Python base image
ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install build dependencies (Python is already in base-python image)
RUN apk add --no-cache \
    curl \
    libffi-dev \
    build-base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Set up environment for uv
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV UV_PYTHON_PREFERENCE=only-system
ENV PATH="/opt/venv/bin:$PATH"

# Copy project files for dependency installation
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./

# Install Python dependencies with uv (production only, no dev deps)
RUN uv sync --no-dev --frozen --python python3

# Copy backend code
COPY backend/app ./app

# Copy frontend build
COPY --from=frontend-builder /app/frontend/dist ./static

# Copy run scripts
COPY run.sh /run.sh
COPY run-standalone.sh /run-standalone.sh
RUN chmod a+x /run.sh /run-standalone.sh

# Set default environment variables (can be overridden by docker-compose or HA)
ENV RUN_MODE=standalone
ENV SECRET_KEY=change-this-in-production

# Expose ports
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run
CMD ["/run.sh"]
