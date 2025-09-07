<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# AutoDocs, Sita द्वारा

किसी भी रिपो के लिए दस्तावेज़ीकरण को स्वचालित करें: हम आपके कोडबेस को ट्रैवर्स करते हैं, AST पार्स करते हैं, निर्भरता ग्राफ़ बनाते हैं और सटीक व उपयोगी दस्तावेज़ तैयार करने के लिए उसे ट्रैवर्स करते हैं। इन-बिल्ट MCP सर्वर एजेंटों को HTTP के माध्यम से गहराई से खोजने देता है।

मुख्य एन्डपॉइंट्स

- वेब UI: http://localhost:3000
- API (FastAPI): http://localhost:8000
- MCP सर्वर: http://localhost:3000/api/mcp

## यह रिपो क्या करता है

- tree‑sitter से AST बनाता है।
- फाइल/परिभाषा/कॉल/इम्पोर्ट का निर्भरता ग्राफ़ बनाता है और साइकिल्स पहचानता है।
- उसी ग्राफ़ पर चलकर रिपो‑स्तरीय, निर्भरता‑सचेत दस्तावेज़ और सार बनाता है।
- इन्गेस्ट/सर्च के लिए FastAPI बैकएंड और एक्सप्लोरेशन के लिए Next.js वेब UI देता है।
- `/api/mcp` पर MCP सर्वर उपलब्ध।

---

## दस्तावेज़ अपडेट करना (महत्वपूर्ण)

अभी, कोड बदलने के बाद डॉक अपडेट करने के लिए उस रिपो को हटाएँ और दोबारा इन्गेस्ट करें (अस्थायी वर्कफ़्लो):

- UI में: Workspace से रिपो डिलीट करें और फिर से जोड़ें (इन्गेस्ट अपने‑आप शुरू होगा)।
- API से: पहले लोकल डेटा (DB + क्लोन) हटाएँ, फिर नई इन्गेस्ट जॉब लगाएँ:

```bash
# लोकल विश्लेषण डेटा हटाएँ (DB + clone)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# नई इन्गेस्ट जॉब जोड़ें
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

हम UI में “Reingest” का एक‑क्लिक बटन और उसके बाद ऑटोमैटिक पीरियोडिक इन्गेस्ट जोड़ रहे हैं—बहुत जल्द।

## त्वरित शुरुआत

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

डेटाबेस माइग्रेशन (लोकल में एक बार):

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## MCP सर्वर

- URL: `http://localhost:3000/api/mcp`
- `x-repo-id` हेडर जोड़ें।

## परियोजना संरचना

- `ingestion/` — FastAPI, AST पार्सिंग, ग्राफ़, एम्बेडिंग्स, सर्च।
- `webview/` — Next.js ऐप व साझा TS पैकेज।
- `docker-compose.yml` — लोकल Postgres, API, Web।

## लाइसेंस

MIT लाइसेंस। किसी भी मतभेद की स्थिति में ../README.md (अंग्रेज़ी) देखें।

## ज्ञात समस्याएँ

- आपके रिपोजिटरी का कोड रूट स्तर पर होना चाहिए, किसी नेस्टेड फ़ोल्डर में नहीं।
- अभी केवल TS, JS और Python समर्थित हैं; आगे Java और Kotlin, फिर Go और Rust के लिए समर्थन जोड़ रहे हैं।
- फिलहाल मल्टी‑लैंग्वेज (एक ही रिपो में कई भाषाएँ) सपोर्ट नहीं है, इस पर भी काम जारी है।
