# syntax=docker/dockerfile:1
# webview/Dockerfile
FROM node:20-bookworm-slim AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable
COPY . /app

FROM base as builder
WORKDIR /app
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm add -g turbo@^2.5.6
RUN turbo prune @sita/onboard-webapp --docker
COPY . .

FROM base as installer
WORKDIR /app
COPY --from=builder /app/out/json/ .
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile

COPY --from=builder /app/out/full/ .
RUN --mount=type=cache,id=pnpm,target=/pnpm/store --mount=type=secret,id=local_env \
    cp /run/secrets/local_env /app/apps/webapp/.env && pnpm build

# RUN node -e "require.resolve('@libsql/linux-arm64-gnu')"

# @todo: change to nextjs standalone after fixing libsql issue I HATE NEXTJS gimme my dist folder back

FROM base AS runner
WORKDIR /app
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs
USER nextjs
# Copy app artifacts
COPY --from=installer --chown=nextjs:nodejs /app/node_modules ./node_modules
COPY --from=installer --chown=nextjs:nodejs /app/apps/webapp/ ./apps/webapp
CMD ["sh", "-c", "cd apps/webapp && node ./node_modules/next/dist/bin/next start -p 3000"]