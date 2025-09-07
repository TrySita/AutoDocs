<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# Sita యొక్క AutoDocs

ఏ రిపోజిటరీకైనా డాక్యుమెంటేషన్‌ను ఆటోమేట్ చేయండి: మీ కోడ్‌బేస్‌ను ట్రావర్స్ చేసి, AST ను పార్స్ చేసి, డిపెండెన్సీ గ్రాఫ్‌ను నిర్మించి దాన్ని అనుసరించి ఖచ్చితమైన మరియు ఉపయోగకరమైన డాక్యుమెంటేషన్‌ను సృష్టిస్తాము. అంతర్నిర్మిత MCP సర్వర్ ద్వారా HTTP మీద లోతైన శోధన సాధ్యమవుతుంది.

ప్రధాన ఎండ్‌పాయింట్లు

- వెబ్ UI: http://localhost:3000
- API (FastAPI): http://localhost:8000
- MCP సర్వర్: http://localhost:3000/api/mcp

## ఈ రిపో ఏమి చేస్తుంది

- tree‑sitter సహాయంతో AST తయారు చేస్తుంది.
- డిపెండెన్సీ గ్రాఫ్ (ఫైళ్లు, నిర్వచనలు, కాల్స్, ఇంపోర్ట్స్) నిర్మించి సైకిళ్లను గుర్తిస్తుంది.
- గ్రాఫ్‌ను అనుసరించి డిపెండెన్సీ‑అవగాహనతో డాక్యుమెంట్లు మరియు సారాంశాలు సృష్టిస్తుంది.
- ingestion/శోధన కోసం FastAPI బ్యాక్‌ఎండ్ మరియు అన్వేషణ కోసం Next.js వెబ్ UI అందిస్తుంది.
- లోతైన క్వెరీల కోసం `/api/mcp` వద్ద MCP సర్వర్ అందిస్తుంది.

---

## డాక్యుమెంటేషన్‌ను నవీకరించడం (ముఖ్యం)

ప్రస్తుతం, కోడ్ మార్పుల తర్వాత డాక్యుమెంటేషన్‌ను రిఫ్రెష్ చేయాలంటే రిపోను తొలగించి మళ్లీ ingest చేయండి (తాత్కాలిక వర్క్‌ఫ్లో):

- UI లో: Workspace నుండి రిపోను డిలీట్ చేసి, మళ్లీ జోడించండి (ingestion ఆటోమేటిక్‌గా ప్రారంభమవుతుంది).
- API ద్వారా: లోకల్ డేటా (DB + క్లోన్) తొలగించి, కొత్త ingestion జాబ్‌ను క్యూలో పెట్టండి.

```bash
# లోకల్ విశ్లేషణ డేటా తొలగించండి (DB + clone)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# కొత్త ingestion జాబ్‌ను క్యూలో పెట్టండి
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

UIలో ఒక క్లిక్‌తో “Reingest” బటన్ మరియు తరువాత ఆటోమేటిక్ పీరియాడిక్ ingestion ను త్వరలో జోడిస్తున్నాము.

## త్వరిత ప్రారంభం

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

డేటాబేస్ మైగ్రేషన్ (లోకల్‌లో ఒక్కసారి):

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## MCP సర్వర్

- URL: `http://localhost:3000/api/mcp`
- `x-repo-id` హెడర్‌ను జోడించండి.

## ప్రాజెక్ట్ నిర్మాణం

- `ingestion/` — FastAPI, AST పార్సింగ్, గ్రాఫ్, ఎంబెడింగ్స్, శోధన.
- `webview/` — Next.js యాప్ మరియు షేర్ చేయబడిన TS ప్యాకేజీలు.
- `docker-compose.yml` — లోకల్ Postgres, API, Web.

## లైసెన్స్

MIT. ఏవైనా తేడాలుంటే ../README.md (ఆంగ్లం) చూడండి.

## తెలిసిన సమస్యలు

- మీ రిపోలో కోడ్ రూట్ స్థాయిలో ఉండాలి; లోపలి (నెస్టెడ్) ఫోల్డర్‌లో కాకూడదు.
- ప్రస్తుతం TS, JS, Python మాత్రమే సపోర్ట్; తరువాత Java, Kotlin, ఆపై Go, Rust కి విస్తరిస్తున్నాం.
- మల్టీ‑లాంగ్వేజ్ (ఒకే రిపోలో బహుళ భాషలు) ఇప్పుడే సపోర్ట్ కాదు; దీనిపై కూడా పని జరుగుతోంది.
