<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# AutoDocs, bởi Sita

Tự động hóa tài liệu cho mọi kho mã: chúng tôi duyệt qua codebase của bạn, phân tích AST, xây dựng đồ thị phụ thuộc và lần theo để tạo ra tài liệu chính xác, hữu ích. Máy chủ MCP tích hợp cho phép tìm kiếm chuyên sâu qua HTTP.

Điểm cuối chính

- Giao diện web: http://localhost:3000
- API (FastAPI): http://localhost:8000
- Máy chủ MCP: http://localhost:3000/api/mcp

## Kho này làm gì

- Phân tích kho bằng tree‑sitter để xây dựng AST.
- Xây dựng đồ thị phụ thuộc (tệp, định nghĩa, lời gọi, import) và phát hiện vòng lặp.
- Lần theo đồ thị để tạo tài liệu và tóm tắt có nhận thức phụ thuộc.
- Cung cấp backend FastAPI cho ingestion/tìm kiếm và UI Next.js để khám phá.
- Cung cấp máy chủ MCP tại `/api/mcp` cho truy vấn sâu.

---

## Cập nhật tài liệu (quan trọng)

Hiện tại, để làm mới tài liệu sau khi thay đổi mã, hãy xóa kho và ingest lại (quy trình tạm thời):

- Trên UI: xóa kho khỏi Workspace, rồi thêm lại (ingestion tự động bắt đầu).
- Qua API: xóa dữ liệu cục bộ (DB + clone) và xếp hàng một job ingestion mới.

```bash
# xóa dữ liệu phân tích cục bộ (DB + clone)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# xếp hàng job ingestion mới
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

Chúng tôi đang bổ sung nút “Reingest” một cú nhấp, sau đó là ingest định kỳ tự động. Sắp phát hành.

## Bắt đầu nhanh

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

Di trú cơ sở dữ liệu (một lần cục bộ):

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## Máy chủ MCP

- URL: `http://localhost:3000/api/mcp`
- Thêm header `x-repo-id`.

## Cấu trúc dự án

- `ingestion/` — FastAPI, phân tích AST, đồ thị, embeddings, tìm kiếm.
- `webview/` — Ứng dụng Next.js và các gói TS dùng chung.
- `docker-compose.yml` — Postgres, API và Web cục bộ.

## Giấy phép

MIT. Nếu có khác biệt, hãy tham chiếu ../README.md (tiếng Anh).

## Vấn đề đã biết

- Mã nguồn phải đặt ở thư mục gốc của repo, không đặt trong thư mục lồng nhau.
- Hiện mới hỗ trợ TS, JS và Python; sẽ mở rộng sang Java và Kotlin rồi đến Go và Rust.
- Chưa hỗ trợ đa ngôn ngữ (nhiều ngôn ngữ trong một repo), nhưng đang phát triển.
