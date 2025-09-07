<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# ‏AutoDocs، از جانب Sita

کسی بھی ریپوزٹری کی دستاویزکاری کو خودکار بنائیں: ہم آپ کے کوڈ بیس کو ٹریورس کرتے ہیں، ‏AST‏ پارس کرتے ہیں، انحصاری گراف بناتے ہیں اور درست و مفید دستاویزات پیدا کرنے کے لیے اسے ٹریورس کرتے ہیں۔ بلٹ‑اِن ‏MCP‏ سرور ایجنٹس کو ‏HTTP‏ کے ذریعے گہری تلاش کی سہولت دیتا ہے۔

اہم اینڈ پوائنٹس

- ویب UI: http://localhost:3000
- ‏API (FastAPI): http://localhost:8000
- ‏MCP سرور: http://localhost:3000/api/mcp

## یہ ریپو کیا کرتا ہے

- ‏tree‑sitter‏ کے ذریعے ‏AST‏ بناتا ہے۔
- فائل/ڈیفینیشن/کال/امپورٹ پر مبنی انحصاری گراف بناتا ہے اور سائیکلز شناخت کرتا ہے۔
- اسی گراف پر چل کر ریپو سطح کی، انحصاری آگاہ دستاویزات اور خلاصے تیار کرتا ہے۔
- ان جیسٹ/سرچ کے لیے ‏FastAPI‏ بیک اینڈ اور دریافت کے لیے ‏Next.js‏ ویب UI فراہم کرتا ہے۔
- ‏`/api/mcp`‏ پر ‏MCP‏ سرور فراہم کرتا ہے۔

---

## دستاویزات اپڈیٹ کرنا (اہم)

فی الحال، کوڈ میں تبدیلی کے بعد دستاویزات کو ریفریش کرنے کے لیے ریپو کو حذف کریں اور دوبارہ اِن جیسٹ کریں (عارضی ورک فلو):

- ‏UI‏ میں: Workspace سے ریپو کو حذف کریں، پھر دوبارہ شامل کریں (اِن جیسٹ خود بخود شروع ہو جائے گا)۔
- ‏API‏ کے ذریعے: مقامی ڈیٹا (DB + کلون) حذف کریں اور نئی اِن جیسٹ جاب قطار میں لگائیں:

```bash
# مقامی تجزیاتی ڈیٹا حذف کریں (DB + clone)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# نئی اِن جیسٹ جاب قطار میں لگائیں
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

ہم ‏UI‏ میں ایک کلک والا “Reingest” بٹن اور اس کے بعد خودکار متواتر اِن جیسٹ شامل کر رہے ہیں—بہت جلد۔

## فوری آغاز

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

ڈیٹا بیس مائیگریشن (لوکل میں ایک بار):

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## ‏MCP‏ سرور

- ‏URL‏: `http://localhost:3000/api/mcp`
- `x-repo-id` ہیڈر شامل کریں۔

## پروجیکٹ ڈھانچہ

- `ingestion/` — ‏FastAPI‏، ‏AST‏ پارسنگ، گراف، ایمبیڈنگز، تلاش۔
- `webview/` — ‏Next.js‏ ایپ اور مشترکہ ‏TS‏ پیکجز۔
- `docker-compose.yml` — لوکل ‏Postgres‏، ‏API‏، ویب۔

## لائسنس

‏MIT۔ کسی اختلاف کی صورت میں ../README.md (انگریزی) ملاحظہ کریں۔

## معلوم مسائل

- آپ کے ریپوزٹری کا کوڈ روٹ سطح پر ہونا چاہیے، کسی اندرونی فولڈر میں نہیں۔
- فی الحال صرف TS، JS اور Python تعاون یافتہ ہیں؛ جلد Java اور Kotlin، اس کے بعد Go اور Rust شامل کیے جائیں گے۔
- اس وقت ملٹی‑لینگویج (ایک ہی ریپو میں متعدد زبانیں) کی سہولت نہیں، اس پر بھی کام جاری ہے۔
