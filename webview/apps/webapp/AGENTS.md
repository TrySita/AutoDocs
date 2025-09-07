# Repository Guidelines

## Project Structure & Module Organization

- `src/app`: Next.js App Router routes and edge/API handlers.
- `src/components`: Reusable UI (PascalCase). `sections/` for marketing/landing.
- `src/hooks`: React hooks (`useX.ts(x)`).
- `src/lib`: Core logic (tRPC, DB, services, utils).
- `src/types`: Shared TypeScript types.
- `public/`: Static assets. Key configs: `drizzle.*.config.ts`, `wrangler.jsonc`.

## Build, Test, and Development Commands

Use pnpm (enforced by `only-allow pnpm`).

- `pnpm dev`: Run locally with Turbopack.
- `pnpm build` / `pnpm start`: Production build and serve.
- `pnpm lint` / `pnpm lint:fix`: ESLint check/fix.
- `pnpm format` / `pnpm format:check`: Prettier write/check.
- `pnpm generate-api-types`: OpenAPI → `src/types/api.ts`.

## Coding Style & Naming Conventions

- TypeScript-first; 2-space indent; functional components; prefer named exports.
- Components: PascalCase; hooks: `useX.ts(x)`; utilities/types: camelCase.
- Centralize re-exports via `index.ts` where helpful.
- Follow ESLint (`eslint.config.mjs`) and Prettier (`.prettierrc.json`). Run `pnpm lint` and `pnpm format` before committing.

## Architecture & Patterns

- Server state: TanStack Query; client state: Jotai. Keep concerns separate but connected via atoms and query invalidation.
- APIs: Prefer tRPC under `src/lib/trpc/*`. Use `/app/api/*` for webhooks/uploads or when tRPC isn’t suitable.
- DRY: Search before adding code; place shared helpers in `src/lib/utils` and shared UI in `src/components/common`.
- Components mainly render; extract data/mutations into hooks (e.g., `useChat`).

## Testing Guidelines

- No formal test harness in repo yet. For new tests, colocate as `*.test.ts(x)` beside source or under `__tests__/` and keep fast, isolated units. Aim for critical-path coverage (auth, TRPC handlers, important hooks/components). Add a `pnpm test` script when introducing a runner.

## Commit & Pull Request Guidelines

- Commits: short, imperative subject; reference issues/PRs when relevant (e.g., "fix: handle SQS edge (#123)").
- PRs: clear description, linked issue, screenshots for UI changes, steps to validate, and env vars touched. Ensure `pnpm lint` and `pnpm format:check` pass.

## Styling

- Tailwind v4 utilities; shadcn/ui + Radix for primitives; prefer CVA for variants; use `next-themes` for dark/light.

## Security & Configuration Tips

- Database configs via Drizzle; validate migrations locally before `push`.
- Use `pnpm` only; do not commit lockfiles other than `pnpm-lock.yaml`.
