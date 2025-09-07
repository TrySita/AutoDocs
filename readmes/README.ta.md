<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# Sita அவர்களிடமிருந்து AutoDocs

எந்த நிரல்தொகுப்பிற்கும் (repo) ஆவணத்தை தானியக்கமாக உருவாக்குங்கள்: உங்கள் குறியீட்டைத் (codebase) திரிந்து, AST ஐப் பகுப்பாய்வு செய்து, சார்பு வரைபடத்தை உருவாக்கி அதைப் பின்தொடர்ந்து துல்லியமான மற்றும் பயனுள்ள ஆவணங்களை உருவாக்குகிறோம். உட்புற MCP சேவையகம் HTTP வழியாக ஆழ்ந்த தேடலை இயக்கு கிறது.

முக்கிய இறுதிமுகங்கள் (Endpoints)

- வலை UI: http://localhost:3000
- API (FastAPI): http://localhost:8000
- MCP சேவையகம்: http://localhost:3000/api/mcp

## இந்த நிரல்தொகுப்பு என்ன செய்கிறது

- tree‑sitter மூலம் AST உருவாக்கும்.
- சார்பு வரைபடம் (கோப்புகள், வரையறைகள், அழைப்புகள், இறக்குமதி) உருவாக்கி சுழற்சிகளை கண்டறியும்.
- வரைபடத்தைப் பின்தொடர்ந்து சார்பு‑அறிவுள்ள ஆவணங்களையும் சுருக்கங்களையும் உருவாக்கும்.
- ingestion/தேடலுக்காக FastAPI பின்னணியும், ஆராய்வதற்காக Next.js வலை UI‑யும் வழங்குகிறது.
- ஆழ்ந்த கேள்விகளுக்காக `/api/mcp` இல் MCP சேவையகம் உள்ளது.

---

## ஆவணங்களைப் புதுப்பித்தல் (முக்கியம்)

தற்போது, குறியீடு மாற்றங்களுக்குப் பிறகு ஆவணங்களைப் புதுப்பிக்க, நிரல்தொகுப்பை நீக்கி மீண்டும் ingest செய்ய வேண்டும் (தற்காலிக நடைமுறை):

- UI: Workspace‑இல் இருந்து நிரல்தொகுப்பை நீக்கி, மறுபடியும் சேர் (ingestion தானாகத் தொடங்கும்).
- API: உள்ளூர் தரவை (DB + clone) நீக்கி, புதிய ingestion பணியை வரிசைப்படுத்துங்கள்.

```bash
# உள்ளூர் பகுப்பாய்வு தரவை நீக்கு (DB + clone)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# புதிய ingestion பணியை வரிசைப்படுத்து
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

UI‑யில் ஒரே‑கிளிக் “Reingest” பொத்தானையும், பின்னர் தானியங்கும் காலாண்டு ingestion‑யையும் விரைவில் வழங்குகிறோம்.

## விரைவான தொடக்கம்

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

தரவுத்தள இடமாற்றம் (உள்நிலையில் ஒருமுறை):

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## MCP சேவையகம்

- URL: `http://localhost:3000/api/mcp`
- `x-repo-id` தலைப்பைச் சேர்க்கவும்.

## திட்ட அமைப்பு

- `ingestion/` — FastAPI, AST பகுப்பாய்வு, வரைபடம், embeddings, தேடல்.
- `webview/` — Next.js பயன்பாடு மற்றும் பகிரப்பட்ட TS தொகுதிகள்.
- `docker-compose.yml` — உள்ளூர் Postgres, API, Web.

## உரிமம்

MIT. எந்த வேறுபாடுகளும் இருந்தால் ../README.md (ஆங்கிலம்) பார்க்கவும்.

## அறியப்பட்ட சிக்கல்கள்

- உங்கள் நிரல்தொகுப்பின் குறியீடு ரூட் நிலையில் இருக்க வேண்டும்; உட்பொத்தகத்தில் இருக்கக் கூடாது.
- தற்போது TS, JS, Python மட்டும் ஆதரவு; அடுத்து Java, Kotlin, பின்னர் Go, Rust ஆதரவைச் சேர்க்கிறோம்.
- ஒரே நிரல்தொகுப்பில் பல மொழிகள் — இப்போது ஆதரவில்லை; இதற்கும் வேலை நடக்கிறது.
