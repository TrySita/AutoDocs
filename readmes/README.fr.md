<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# AutoDocs, par Sita

Automatisez la documentation de n’importe quel dépôt : nous parcourons votre codebase, analysons l’AST, construisons un graphe de dépendances et le parcourons pour produire une documentation précise et utile. Un serveur MCP intégré permet une recherche approfondie via HTTP.

Points clés

- Interface Web : http://localhost:3000
- API (FastAPI) : http://localhost:8000
- Serveur MCP : http://localhost:3000/api/mcp

## Ce que fait ce dépôt

- Analyse avec tree‑sitter pour construire un AST.
- Construit un graphe de dépendances (fichiers, définitions, appels, imports) et détecte les cycles.
- Parcourt le graphe pour générer une documentation et des résumés sensibles aux dépendances.
- Expose un backend FastAPI pour l’ingestion/la recherche et une interface Next.js pour l’exploration.
- Fournit un serveur MCP sur `/api/mcp` pour les requêtes approfondies.

---

## Mise à jour de la documentation (important)

Actuellement, pour rafraîchir la documentation après des changements de code, supprimez le dépôt et ré-ingérez-le (flux temporaire) :

- UI : supprimez le dépôt de votre Espace de travail puis ajoutez‑le à nouveau (l’ingestion démarre automatiquement).
- API : supprimez et ré‑ingérez via le service d’ingestion :

```bash
# supprimer les données locales (BD + clone)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# mettre en file une nouvelle ingestion
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

Nous ajoutons un bouton « Ré-ingestion » en un clic, puis une ingestion périodique automatique. Très bientôt.

## Démarrage rapide

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

Migration de la base (une fois en local) :

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## Serveur MCP

- URL : `http://localhost:3000/api/mcp`
- Ajoutez l’en‑tête `x-repo-id`.

## Structure du projet

- `ingestion/` — FastAPI, parsing AST, graphe, embeddings, recherche.
- `webview/` — App Next.js et paquets TS partagés.
- `docker-compose.yml` — Postgres, API et Web locaux.

## Licence

MIT. En cas de divergence, se référer à ../README.md (anglais).

## Problèmes connus

- Le code doit se trouver à la racine du dépôt, pas dans un dossier imbriqué.
- Nous ne prenons en charge que TS, JS et Python pour le moment; prise en charge prévue de Java et Kotlin puis de Go et Rust.
- Pas encore de support multi‑langage (plusieurs langages dans un même dépôt), mais c’est en cours.
