<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# Sita による AutoDocs

あらゆるリポジトリのドキュメント化を自動化します。コードベースを走査し、AST を解析し、依存関係グラフを構築して辿ることで、正確で価値の高いドキュメントを生成します。内蔵の MCP サーバーにより、HTTP 経由のディープサーチが可能です。

主なエンドポイント

- Web UI: http://localhost:3000
- API (FastAPI): http://localhost:8000
- MCP サーバー: http://localhost:3000/api/mcp

## 本リポジトリの機能

- tree‑sitter により AST を構築します。
- 依存関係グラフ（ファイル、定義、呼び出し、インポート）を構築し、循環を検出します。
- グラフを辿って、依存関係を考慮したリポジトリ全体のドキュメントと要約を生成します。
- 取り込み/検索用の FastAPI バックエンドと、閲覧用の Next.js Web UI を提供します。
- `/api/mcp` に MCP サーバーを提供します。

---

## ドキュメントの更新（重要）

現在、コード変更後にドキュメントを更新するには、リポジトリを削除して再取り込みしてください（暫定フロー）：

- UI: Workspace でリポジトリを削除し、再度追加します（取り込みは自動開始）。
- API: ローカルデータ（DB + クローン）を削除し、新しい取り込みジョブを登録します。

```bash
# ローカル分析データの削除（DB + clone）
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# 新規取り込みジョブの登録
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

UI にワンクリックの「Reingest」ボタンを追加し、その後は自動の定期取り込みを提供予定です。まもなく公開されます。

## クイックスタート

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

DB マイグレーション（ローカルで一度）:

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## MCP サーバー

- URL: `http://localhost:3000/api/mcp`
- ヘッダー `x-repo-id` を追加してください。

## プロジェクト構成

- `ingestion/` — FastAPI、AST 解析、グラフ、埋め込み、検索。
- `webview/` — Next.js アプリと共有 TS パッケージ。
- `docker-compose.yml` — ローカルの Postgres、API、Web。

## ライセンス

MIT。差異がある場合は ../README.md（英語）を参照してください。

## 既知の問題

- リポジトリのコードはルート直下に配置する必要があり、入れ子フォルダ内は不可です。
- 現時点の対応言語は TS・JS・Python のみです。今後、Java と Kotlin、その後に Go と Rust を予定しています。
- 同一リポで複数言語を扱うマルチ言語構成は未サポートですが、対応を進めています。
