<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# AutoDocs, di Sita

Automatizza la documentazione per qualsiasi repository: attraversiamo la codebase, analizziamo l’AST, costruiamo un grafo delle dipendenze e lo percorriamo per generare documentazione accurata e utile. Un server MCP integrato consente ricerche approfondite via HTTP.

Punti chiave

- Interfaccia Web: http://localhost:3000
- API (FastAPI): http://localhost:8000
- Server MCP: http://localhost:3000/api/mcp

## Cosa fa questo repository

- Analizza il repository con tree‑sitter per costruire l’AST.
- Costruisce un grafo di dipendenze (file, definizioni, chiamate, import) e rileva cicli.
- Percorre il grafo per creare documentazione e riepiloghi consapevoli delle dipendenze.
- Espone un backend FastAPI per ingestion/ricerca e una UI Next.js per l’esplorazione.
- Fornisce un server MCP su `/api/mcp` per query approfondite.

---

## Aggiornare la documentazione (importante)

Per ora, per aggiornare la documentazione dopo modifiche al codice, rimuovi il repo e re‑ingestiscilo (flusso temporaneo):

- In UI: elimina il repo dallo Workspace e aggiungilo di nuovo (l’ingestion parte automaticamente).
- Via API: elimina i dati locali e accoda una nuova ingestion:

```bash
# elimina dati locali (DB + clone)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# accoda una nuova ingestion
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

Stiamo aggiungendo un pulsante “Reingest” con un clic e, a seguire, ingestion periodica automatica. In arrivo molto presto.

## Avvio rapido

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

Migrazione del database (una volta in locale):

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## Server MCP

- URL: `http://localhost:3000/api/mcp`
- Includi l’header `x-repo-id`.

## Struttura del progetto

- `ingestion/` — FastAPI, parsing AST, grafo, embedding, ricerca.
- `webview/` — App Next.js e pacchetti TS condivisi.
- `docker-compose.yml` — Postgres, API e Web locali.

## Licenza

MIT. In caso di discrepanze, fare riferimento a ../README.md (inglese).

## Problemi noti

- Il codice deve stare nella radice del repository, non in una cartella annidata.
- Al momento supportiamo solo TS, JS e Python; espanderemo a Java e Kotlin, poi a Go e Rust.
- Nessun supporto multi‑linguaggio per ora (più linguaggi nello stesso repo), ma ci stiamo lavorando.
