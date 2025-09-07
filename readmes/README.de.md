<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# AutoDocs, von Sita

Automatisieren Sie die Dokumentation für jedes Repository: Wir traversieren Ihre Codebasis, parsen den AST, bauen einen Abhängigkeitsgraphen und durchlaufen ihn, um präzise und nützliche Dokumentation zu erzeugen. Ein integrierter MCP‑Server ermöglicht tiefgehende Suche per HTTP.

Schlüsselendpunkte

- Web‑UI: http://localhost:3000
- API (FastAPI): http://localhost:8000
- MCP‑Server: http://localhost:3000/api/mcp

## Was dieses Repository macht

- Analysiert Ihr Repository mit tree‑sitter, um einen AST zu bauen.
- Baut einen Abhängigkeitsgraphen (Dateien, Definitionen, Aufrufe, Importe) und erkennt Zyklen.
- Traversiert den Graphen, um repo‑weite, abhängigkeitssensible Doku und Zusammenfassungen zu erzeugen.
- Stellt ein FastAPI‑Backend für Ingestion/Suche und eine Next.js‑Web‑UI bereit.
- Bietet einen MCP‑Server unter `/api/mcp` für tiefe Abfragen.

---

## Dokumentation aktualisieren (wichtig)

Aktuell müssen Sie zur Aktualisierung der Doku nach Codeänderungen das Repo entfernen und erneut ingestieren (temporärer Ablauf):

- In der UI: Repo im Workspace löschen, dann erneut hinzufügen (Ingestion startet automatisch).
- Per API: lokale Analysedaten löschen und neue Ingestion einreihen:

```bash
# lokale Analysedaten löschen (DB + Clone)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# neue Ingestion einreihen
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

Wir arbeiten an einem „Reingestieren“-Button mit einem Klick sowie automatischer periodischer Ingestion. Erscheint sehr bald.

## Schnellstart

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

Datenbankmigration (einmal lokal):

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## MCP‑Server

- URL: `http://localhost:3000/api/mcp`
- Fügen Sie den Header `x-repo-id` hinzu.

## Projektstruktur

- `ingestion/` — FastAPI, AST‑Parsing, Graph, Embeddings, Suche.
- `webview/` — Next.js‑App und gemeinsame TS‑Pakete.
- `docker-compose.yml` — lokale Postgres‑, API‑ und Web‑Dienste.

## Lizenz

MIT. Bei Abweichungen gilt ../README.md (Englisch).

## Bekannte Probleme

- Der Code muss im Repository‑Root liegen, nicht in einem verschachtelten Ordner.
- Aktuell werden nur TS, JS und Python unterstützt; Erweiterung auf Java und Kotlin, danach Go und Rust, ist geplant.
- Mehrsprachen‑Repos werden derzeit nicht unterstützt, wir arbeiten daran.
