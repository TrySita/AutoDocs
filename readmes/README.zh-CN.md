<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# AutoDocs（由 Sita 构建）

为任何代码仓库自动生成高质量文档：我们遍历代码库、解析抽象语法树（AST）、构建依赖图，并沿图遍历以生成准确、可追溯的文档。内置 MCP 服务器允许智能体通过 HTTP 深度检索代码。

关键端点

- Web 界面：http://localhost:3000
- API（FastAPI）：http://localhost:8000
- MCP 服务器：http://localhost:3000/api/mcp

## 本仓库做什么

- 使用 tree-sitter 解析仓库并构建 AST。
- 构建代码依赖图（文件、定义、调用、导入）并检测循环。
- 沿依赖图生成仓库范围的依赖感知文档与摘要。
- 提供用于摄取/搜索的 FastAPI 后端与 Next.js Web 界面。
- 在 `/api/mcp` 提供 MCP 服务器，便于智能体进行深度检索。

---

## 更新文档（重要）

当前要在代码变更后刷新某个仓库的文档，请“移除并重新摄取”该仓库（临时流程）：

- 在 UI 中：在“Workspace”中删除该仓库，然后再次添加（会自动开始摄取）。
- 通过 API：先删除本地分析数据（数据库 + 克隆），再重新入队摄取任务：

```bash
# 删除本地分析数据（数据库 + 克隆）
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# 入队新的摄取任务
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

我们正在开发“一键重新摄取”按钮，随后会支持自动周期性摄取，即将发布。

## 快速开始

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

数据库迁移（本地一次性）：

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## 使用 MCP 服务器

- 服务器地址：`http://localhost:3000/api/mcp`
- 在请求头中添加 `x-repo-id` 指定仓库 ID。

## 项目结构

- `ingestion/` — Python FastAPI、AST 解析、依赖图、嵌入与搜索。
- `webview/` — Next.js 应用与共享 TS 包。
- `docker-compose.yml` — 本地 Postgres、API、Web 服务。

## 许可证

MIT 许可。以英文版为准；如有出入，请以 ../README.md 为准。

## 已知问题

- 仓库的代码必须位于仓库根目录，而不是嵌套子文件夹内。
- 目前仅支持 TS、JS 和 Python；计划先扩展到 Java 与 Kotlin，随后支持 Go 与 Rust。
- 目前不支持“多语言（同一仓库包含多种编程语言）”，我们也在开发中。
