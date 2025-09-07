# webview/Dockerfile
FROM node:20-bookworm-slim AS deps
WORKDIR /app
ENV PNPM_HOME=/usr/local/share/pnpm PATH=$PNPM_HOME:$PATH
RUN corepack enable && corepack prepare pnpm@10.15.0 --activate
COPY webview/pnpm-workspace.yaml ./
COPY webview/pnpm-lock.yaml ./pnpm-lock.yaml
COPY webview/package.json ./
COPY webview/apps/webapp/package.json ./apps/webapp/
COPY webview/packages/shared/package.json ./packages/shared/
RUN pnpm config set store-dir /pnpm/store && pnpm install --frozen-lockfile

FROM node:20-bookworm-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    git python3 make g++ ca-certificates && rm -rf /var/lib/apt/lists/*
ENV PNPM_HOME=/usr/local/share/pnpm PATH=$PNPM_HOME:$PATH
ENV NODE_ENV=production PORT=3000
RUN corepack enable && corepack prepare pnpm@10.15.0 --activate \
    && pnpm config set store-dir /pnpm/store
COPY --from=deps /pnpm/store /pnpm/store
# now add the whole workspace and install offline from the store

FROM node:20-bookworm-slim AS runner
WORKDIR /app
ENV PNPM_HOME=/usr/local/share/pnpm PATH=$PNPM_HOME:$PATH
ENV NODE_ENV=production PORT=3000
RUN corepack enable && corepack prepare pnpm@10.15.0 --activate \
    && pnpm config set store-dir /pnpm/store
COPY --from=builder /pnpm/store /pnpm/store
# now add the built files
COPY webview ./
RUN --mount=type=secret,id=local_env \
    cp /run/secrets/local_env /app/apps/webapp/.env && pnpm install --frozen-lockfile && pnpm build
RUN pnpm prune --prod
EXPOSE 3000
CMD ["pnpm","start"]
