# syntax=docker/dockerfile:1
# ingestion/Dockerfile
FROM node:20-bookworm-slim AS scip-cli
# Install once here so the final image stays slim
RUN npm install -g @sourcegraph/scip-typescript @sourcegraph/scip-python \
    && node -v \
    && scip-typescript --help >/dev/null \
    && scip-python --help >/dev/null

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS base
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy
# Ensure installed tools can be executed out of the box
ENV UV_TOOL_BIN_DIR=/usr/local/bin

# System deps (git + build toolchain + libgit2 for pygit2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential libgit2-dev pkg-config ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /api
# Bring over the Node runtime and the globally installed CLIs


# Now add your package and install it (non-editable for prod)
FROM base AS runner
WORKDIR /api
ENV PYTHONPATH=/api/src
ENV PYTHONUNBUFFERED=1
COPY --from=scip-cli /usr/local/ /usr/local/

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY . /api
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev
ENV PATH="/api/.venv/bin:$PATH"

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
