# ingestion/Dockerfile
FROM node:20-bookworm-slim AS scip-cli
# Install once here so the final image stays slim
RUN npm install -g @sourcegraph/scip-typescript @sourcegraph/scip-python \
    && node -v \
    && scip-typescript --help >/dev/null \
    && scip-python --help >/dev/null

FROM python:3.13-slim AS base

ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps (git + build toolchain + libgit2 for pygit2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential libgit2-dev pkg-config ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /api

# Bring over the Node runtime and the globally installed CLIs
COPY --from=scip-cli /usr/local/ /usr/local/
COPY ingestion/requirements_lock.txt /tmp/requirements_lock.txt
# If the file contains "-e .", strip it so we install your package separately:
RUN grep -v -E '^-e[[:space:]]+\.$' /tmp/requirements_lock.txt > /tmp/requirements_no_editable.txt \
    && pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --require-hashes -r /tmp/requirements_no_editable.txt

# Now add your package and install it (non-editable for prod)
FROM python:3.13-slim AS runner
WORKDIR /api
COPY --from=base /usr/local/ /usr/local/
COPY ingestion /api
ENV PYTHONPATH=/api/src
ENV PYTHONUNBUFFERED=1

RUN --mount=type=secret,id=local_env \
    cp /run/secrets/local_env /api/.env && pip install --no-cache-dir /api --no-deps

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
