<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# Sita의 AutoDocs

어떤 리포지토리든 문서를 자동화합니다. 코드베이스를 순회하고 AST를 파싱하며, 의존성 그래프를 구성해 이를 따라가면서 정확하고 유용한 문서를 생성합니다. 내장 MCP 서버로 HTTP 기반의 심층 검색을 사용할 수 있습니다.

주요 엔드포인트

- 웹 UI: http://localhost:3000
- API (FastAPI): http://localhost:8000
- MCP 서버: http://localhost:3000/api/mcp

## 리포지토리 기능

- tree‑sitter로 AST를 구성합니다.
- 의존성 그래프(파일, 정의, 호출, import)를 만들고 순환을 감지합니다.
- 그래프를 순회하여 의존성 인지 문서와 요약을 생성합니다.
- Ingestion/검색을 위한 FastAPI 백엔드와 탐색을 위한 Next.js 웹 UI를 제공합니다.
- `/api/mcp`에 MCP 서버를 제공합니다.

---

## 문서 업데이트(중요)

현재는 코드 변경 후 문서를 새로고침하려면 리포를 삭제하고 재‑ingest 해야 합니다(임시 워크플로우):

- UI: Workspace에서 리포를 삭제한 뒤 다시 추가합니다(ingestion이 자동 시작됨).
- API: 로컬 데이터(DB + 클론)를 삭제하고 새 ingestion 작업을 등록합니다.

```bash
# 로컬 분석 데이터 삭제(DB + clone)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# 새 ingestion 작업 등록
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

UI에 원클릭 “Reingest” 버튼을 추가하고, 이후 자동 주기적 ingestion을 제공할 예정입니다. 곧 공개됩니다.

## 빠른 시작

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

DB 마이그레이션(로컬 1회):

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## MCP 서버

- URL: `http://localhost:3000/api/mcp`
- `x-repo-id` 헤더를 포함하세요.

## 프로젝트 구조

- `ingestion/` — FastAPI, AST 파싱, 그래프, 임베딩, 검색.
- `webview/` — Next.js 앱 및 공유 TS 패키지.
- `docker-compose.yml` — 로컬 Postgres, API, Web.

## 라이선스

MIT. 상이한 경우 ../README.md(영어)를 참조하세요.

## 알려진 문제

- 리포지토리 코드는 최상위 경로(루트)에 있어야 하며, 하위(중첩) 폴더는 지원되지 않습니다.
- 현재 TS, JS, Python만 지원하며, 이후 Java와 Kotlin, 다음으로 Go와 Rust를 지원할 예정입니다.
- 하나의 리포에서 여러 언어를 사용하는 멀티 언어 구성은 아직 지원하지 않지만, 개발 중입니다.
