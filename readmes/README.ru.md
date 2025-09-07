<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# AutoDocs от Sita

Автоматизируйте документацию для любого репозитория: мы обходим кодовую базу, разбираем AST, строим граф зависимостей и обходим его для генерации точной и полезной документации. Встроенный MCP‑сервер позволяет агентам выполнять глубокий поиск через HTTP.

Ключевые эндпоинты

- Веб‑интерфейс: http://localhost:3000
- API (FastAPI): http://localhost:8000
- MCP‑сервер: http://localhost:3000/api/mcp

## Возможности репозитория

- Парсинг репозитория с помощью tree‑sitter для построения AST.
- Построение графа зависимостей (файлы, определения, вызовы, импорты) и поиск циклов.
- Обход графа для генерации документации и сводок с учётом зависимостей.
- Backend на FastAPI для ingestion/поиска и веб‑интерфейс на Next.js для изучения.
- MCP‑сервер на `/api/mcp` для глубоких запросов.

---

## Обновление документации (важно)

Пока что, чтобы обновить документацию после изменений в коде, удалите репозиторий и выполните повторный ingestion (временный процесс):

- В UI: удалите репозиторий из Workspace и добавьте снова (ingestion стартует автоматически).
- Через API: удалите локальные данные (БД + клон) и поставьте новую задачу ingestion:

```bash
# удалить локальные данные анализа (БД + клон)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# поставить новую задачу ingestion
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

Мы добавляем кнопку «Reingest» в UI, а затем автоматический периодический ingestion. Совсем скоро.

## Быстрый старт

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

Миграция БД (один раз локально):

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## MCP‑сервер

- URL: `http://localhost:3000/api/mcp`
- Добавьте заголовок `x-repo-id`.

## Структура проекта

- `ingestion/` — FastAPI, разбор AST, граф, эмбеддинги, поиск.
- `webview/` — приложение Next.js и общие TS‑пакеты.
- `docker-compose.yml` — локальные Postgres, API и Web.

## Лицензия

MIT. При расхождениях см. ../README.md (английский).

## Известные проблемы

- Код должен находиться в корне репозитория, а не в вложенной папке.
- Сейчас поддерживаются только TS, JS и Python; планируем добавить Java и Kotlin, затем Go и Rust.
- Мульти‑язычные репозитории пока не поддерживаются, но мы работаем над этим.
