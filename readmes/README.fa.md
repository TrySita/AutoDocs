<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# ‏AutoDocs توسط Sita

مستندسازی هر مخزن کدی را خودکار کنید: کُد شما را پیمایش می‌کنیم، AST را تجزیه می‌کنیم، گراف وابستگی می‌سازیم و با پیمایش آن مستندات دقیق و کاربردی تولید می‌کنیم. سرور MCP داخلی امکان جستجوی عمیق از طریق HTTP را فراهم می‌کند.

نقاط دسترسی کلیدی

- رابط وب: http://localhost:3000
- API (FastAPI): http://localhost:8000
- سرور MCP: http://localhost:3000/api/mcp

## این مخزن چه می‌کند

- با tree‑sitter مخزن را برای ساخت AST تحلیل می‌کند.
- گراف وابستگی (فایل‌ها، تعاریف، فراخوانی‌ها، واردات) می‌سازد و حلقه‌ها را شناسایی می‌کند.
- گراف را پیمایش می‌کند تا مستندات و خلاصه‌های آگاه از وابستگی تولید کند.
- یک بک‌اند FastAPI برای ingestion/جستجو و یک رابط وب Next.js برای مرور ارائه می‌کند.
- سرور MCP را در مسیر `/api/mcp` برای پرس‌وجوهای عمیق فراهم می‌کند.

---

## به‌روزرسانی مستندات (مهم)

در حال حاضر برای تازه‌سازی مستندات پس از تغییرات کد، مخزن را حذف کرده و دوباره ingest کنید (روند موقتی):

- در UI: مخزن را از Workspace حذف و دوباره اضافه کنید (ingestion به‌صورت خودکار شروع می‌شود).
- از طریق API: داده‌های محلی (پایگاه‌داده + کلون) را حذف و یک کار ingestion جدید صف کنید.

```bash
# حذف داده‌های تحلیلی محلی (DB + clone)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# صف‌کردن یک کار ingestion جدید
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

در حال افزودن دکمه «Reingest» تک‌کلیکی در UI هستیم و سپس ingestion دوره‌ای خودکار ارائه خواهد شد. به‌زودی منتشر می‌شود.

## شروع سریع

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

مهاجرت پایگاه‌داده (یک‌بار در محیط محلی):

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## سرور MCP

- URL: `http://localhost:3000/api/mcp`
- هدر `x-repo-id` را اضافه کنید.

## ساختار پروژه

- `ingestion/` — FastAPI، تجزیه AST، گراف، embeddingها، جستجو.
- `webview/` — اپ Next.js و پکیج‌های TS مشترک.
- `docker-compose.yml` — سرویس‌های محلی Postgres، API و Web.

## مجوز

MIT. در صورت هرگونه اختلاف، به ../README.md (انگلیسی) مراجعه کنید.

## مشکلات شناخته‌شده

- کد باید در ریشه مخزن باشد، نه داخل پوشه تو در تو.
- فعلاً فقط TS، JS و Python پشتیبانی می‌شوند؛ سپس به Java و Kotlin و بعد به Go و Rust گسترش می‌یابیم.
- پشتیبانی چندزبانه (چند زبان در یک مخزن) در حال حاضر موجود نیست اما روی آن کار می‌کنیم.
