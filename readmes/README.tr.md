<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# Sita tarafından AutoDocs

Herhangi bir deponun dokümantasyonunu otomatikleştirin: kod tabanınızı dolaşır, AST’yi ayrıştırır, bir bağımlılık grafı oluşturur ve bunu izleyerek doğru ve kullanışlı dokümantasyon üretiriz. Yerleşik MCP sunucusu, HTTP üzerinden derin arama yapmayı sağlar.

Ana uç noktalar

- Web arayüzü: http://localhost:3000
- API (FastAPI): http://localhost:8000
- MCP sunucusu: http://localhost:3000/api/mcp

## Bu depo ne yapar

- tree‑sitter ile AST oluşturur.
- Bağımlılık grafı (dosyalar, tanımlar, çağrılar, içe aktarmalar) kurar ve döngüleri tespit eder.
- Grafı izleyerek bağımlılık farkındalığı olan doküman ve özetler üretir.
- Ingestion/arama için FastAPI arka ucu ve keşif için Next.js web arayüzü sunar.
- `/api/mcp` altında MCP sunucusu sağlar.

---

## Belgeleri güncelleme (önemli)

Şimdilik kod değişikliklerinden sonra dokümanları yenilemek için depoyu kaldırıp yeniden ingest etmeniz gerekir (geçici akış):

- UI: Workspace’te depoyu silin ve yeniden ekleyin (ingestion otomatik başlar).
- API: yerel verileri (DB + kopya) silin ve yeni ingestion işi kuyruğa alın.

```bash
# yerel analiz verilerini sil (DB + clone)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# yeni ingestion işi oluştur
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

Tek tıkla “Reingest” düğmesi ve ardından otomatik periyodik ingestion yakında eklenecek.

## Hızlı başlangıç

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

Veritabanı geçişi (yerelde bir kez):

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## MCP sunucusu

- URL: `http://localhost:3000/api/mcp`
- `x-repo-id` başlığını ekleyin.

## Proje yapısı

- `ingestion/` — FastAPI, AST ayrıştırma, graf, embedding, arama.
- `webview/` — Next.js uygulaması ve paylaşılan TS paketleri.
- `docker-compose.yml` — yerel Postgres, API ve Web.

## Lisans

MIT. Fark olması halinde ../README.md (İngilizce) geçerlidir.

## Bilinen sorunlar

- Kod depo kök dizininde olmalı; iç içe klasörlerde olmamalı.
- Şimdilik yalnızca TS, JS ve Python destekleniyor; yakında Java ve Kotlin, ardından Go ve Rust eklenecek.
- Çok dilli (aynı depoda birden çok dil) yapı henüz desteklenmiyor, bunun üzerinde çalışıyoruz.
