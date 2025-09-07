<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# AutoDocs, por Sita

Automatiza la documentación de cualquier repositorio: recorremos tu código, analizamos el AST, construimos un grafo de dependencias y lo atravesamos para generar documentación precisa y útil. Un servidor MCP integrado permite a los agentes buscar en profundidad por HTTP.

Puntos clave

- Interfaz web: http://localhost:3000
- API (FastAPI): http://localhost:8000
- Servidor MCP: http://localhost:3000/api/mcp

## Qué hace este repositorio

- Analiza tu repo con tree‑sitter para construir un AST.
- Construye un grafo de dependencias (archivos, definiciones, llamadas, importaciones) y detecta ciclos.
- Recorre el grafo para crear documentación y resúmenes con conocimiento de dependencias.
- Expone un backend FastAPI para ingesta/búsqueda y una UI Next.js para exploración.
- Proporciona un servidor MCP en `/api/mcp` para consultas profundas.

---

## Actualizar documentación (importante)

Por ahora, para refrescar la documentación tras cambios en el código, elimina el repo y vuelve a ingerirlo (flujo temporal):

- En la UI: elimina el repo en tu Espacio de trabajo y añádelo de nuevo (la ingesta comenzará automáticamente).
- Con la API: elimina y vuelve a ingerir usando el servicio de ingesta:

```bash
# borrar datos locales (BD + clon)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# encolar una nueva ingesta
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

Estamos añadiendo un botón de “Reingesta” con un clic y, después, ingesta automática periódica. Muy pronto.

## Inicio rápido

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

Migración de base de datos (una vez en local):

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## Servidor MCP

- URL: `http://localhost:3000/api/mcp`
- Incluye `x-repo-id` en las cabeceras.

## Estructura del proyecto

- `ingestion/` — FastAPI, análisis AST, grafo, embeddings y búsqueda.
- `webview/` — App Next.js y paquetes TS compartidos.
- `docker-compose.yml` — Postgres, API y Web locales.

## Licencia

MIT. En caso de duda, consulta ../README.md (inglés).

## Problemas conocidos

- El código del repositorio debe estar en la raíz, no en una carpeta anidada.
- Por ahora solo admitimos TS, JS y Python; ampliaremos a Java y Kotlin y después a Go y Rust.
- Tampoco admitimos repositorios multilenguaje por ahora, pero estamos trabajando en ello.
