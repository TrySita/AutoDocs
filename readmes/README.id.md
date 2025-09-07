<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# AutoDocs, oleh Sita

Otomatisasi dokumentasi untuk repo apa pun: kami menelusuri basis kode Anda, mengurai AST, membangun graf dependensi, lalu menelusurinya untuk menghasilkan dokumentasi yang akurat dan bernilai tinggi. Server MCP bawaan memungkinkan agen melakukan pencarian mendalam via HTTP.

Endpoint utama

- Antarmuka web: http://localhost:3000
- API (FastAPI): http://localhost:8000
- Server MCP: http://localhost:3000/api/mcp

## Apa yang dilakukan repo ini

- Mengurai repo menggunakan tree‑sitter untuk membangun AST.
- Membangun graf dependensi (berkas, definisi, pemanggilan, impor) dan mendeteksi siklus.
- Menelusuri graf untuk membuat dokumentasi dan ringkasan yang sadar dependensi.
- Menyediakan backend FastAPI untuk ingestion/pencarian dan UI Next.js untuk eksplorasi.
- Menyediakan server MCP di `/api/mcp` untuk kueri mendalam.

---

## Memperbarui dokumen (penting)

Saat ini, untuk menyegarkan dokumen setelah perubahan kode, hapus repo dan lakukan ingestion ulang (alur sementara):

- Di UI: hapus repo dari Workspace, lalu tambahkan lagi (ingestion mulai otomatis).
- Via API: hapus data lokal (DB + klon) lalu antrekan pekerjaan ingestion baru:

```bash
# hapus data analisis lokal (DB + clone)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# antrekan ingestion baru
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

Kami sedang menambahkan tombol “Reingest” satu klik, diikuti ingestion berkala otomatis. Segera hadir.

## Mulai cepat

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

Migrasi basis data (sekali di lokal):

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## Server MCP

- URL: `http://localhost:3000/api/mcp`
- Sertakan header `x-repo-id`.

## Struktur proyek

- `ingestion/` — FastAPI, parsing AST, graf, embeddings, pencarian.
- `webview/` — Aplikasi Next.js dan paket TS bersama.
- `docker-compose.yml` — Postgres, API, dan Web lokal.

## Lisensi

MIT. Jika terjadi perbedaan, rujuk ke ../README.md (Inggris).

## Masalah yang diketahui

- Kode repo harus berada di level root, bukan di folder bertingkat.
- Saat ini hanya mendukung TS, JS, dan Python; akan diperluas ke Java dan Kotlin lalu ke Go dan Rust.
- Belum mendukung multi‑bahasa (beberapa bahasa dalam satu repo), namun sedang dikerjakan.
