<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# AutoDocs, Sita-এর পক্ষ থেকে

যে কোনো রিপোজিটরির ডকুমেন্টেশন স্বয়ংক্রিয় করুন: আমরা কোডবেস ট্রাভার্স করি, AST পার্স করি, ডিপেনডেন্সি গ্রাফ বানাই এবং সেটি ট্রাভার্স করে সঠিক ও কার্যকর ডক তৈরি করি। বিল্ট‑ইন MCP সার্ভার এজেন্টদের HTTP-এর মাধ্যমে গভীর অনুসন্ধান করতে দেয়।

মূল এন্ডপয়েন্ট

- ওয়েব UI: http://localhost:3000
- API (FastAPI): http://localhost:8000
- MCP সার্ভার: http://localhost:3000/api/mcp

## এই রিপো কী করে

- tree‑sitter দিয়ে AST তৈরি করে।
- ডিপেনডেন্সি গ্রাফ (ফাইল, ডেফিনিশন, কল, ইমপোর্ট) তৈরি করে এবং সাইকেল শনাক্ত করে।
- গ্রাফ ট্রাভার্স করে ডিপেনডেন্সি‑সচেতন ডক ও সারাংশ তৈরি করে।
- ইনজেস্ট/সার্চের জন্য FastAPI ব্যাকএন্ড ও এক্সপ্লোরেশনের জন্য Next.js ওয়েব UI দেয়।
- `/api/mcp` এ MCP সার্ভার দেয় গভীর কুয়েরির জন্য।

---

## ডক আপডেট (গুরুত্বপূর্ণ)

এখন, কোড পরিবর্তনের পর ডক রিফ্রেশ করতে রিপো মুছে ফেলে পুনরায় ইনজেস্ট করুন (অস্থায়ী ওয়ার্কফ্লো):

- UI-তে: Workspace থেকে রিপো ডিলিট করে আবার যোগ করুন (ইনজেস্ট স্বয়ংক্রিয়ভাবে শুরু হবে)।
- API-তে: লোকাল ডাটা (DB + ক্লোন) ডিলিট করে নতুন ইনজেস্ট জব কিউ করুন:

```bash
# লোকাল ডাটা ডিলিট (DB + clone)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# নতুন ইনজেস্ট জব কিউ করুন
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

আমরা এক‑ক্লিক “Reingest” বাটন এবং পরে স্বয়ংক্রিয় পিরিয়ডিক ইনজেস্ট যোগ করছি—খুব শিগগিরই।

## দ্রুত শুরু

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

ডাটাবেস মাইগ্রেশন (লোকালে একবার):

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## MCP সার্ভার

- ঠিকানা: `http://localhost:3000/api/mcp`
- `x-repo-id` হেডার দিন।

## প্রজেক্ট স্ট্রাকচার

- `ingestion/` — FastAPI, AST পার্সিং, গ্রাফ, এমবেডিংস, সার্চ।
- `webview/` — Next.js অ্যাপ ও শেয়ার্ড TS প্যাকেজ।
- `docker-compose.yml` — লোকাল Postgres, API, Web।

## লাইসেন্স

MIT। কোনো অমিল হলে ../README.md (ইংরেজি) দেখুন।

## পরিচিত সমস্যা

- আপনার রিপোজিটরির কোড অবশ্যই রুট লেভেলে থাকতে হবে, নেস্টেড ফোল্ডারে নয়।
- আপাতত কেবল TS, JS এবং Python সমর্থিত; পরে Java ও Kotlin, তারপর Go ও Rust যুক্ত হবে।
- এখনো মাল্টি‑ল্যাঙ্গুয়েজ (একই রিপোতে একাধিক ভাষা) সমর্থিত নয়, তবু এ নিয়ে কাজ চলছে।
