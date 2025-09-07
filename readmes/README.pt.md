<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# AutoDocs, por Sita

Automatize a documentação de qualquer repositório: percorremos seu código, analisamos a AST, construímos um grafo de dependências e o percorremos para gerar documentação precisa e de alto valor. Um servidor MCP integrado permite busca profunda via HTTP.

Endpoints principais

- Web UI: http://localhost:3000
- API (FastAPI): http://localhost:8000
- Servidor MCP: http://localhost:3000/api/mcp

## O que este repositório faz

- Analisa o repositório com tree‑sitter para construir a AST.
- Constrói um grafo de dependências (arquivos, definições, chamadas, imports) e detecta ciclos.
- Percorre o grafo para criar documentação e resumos cientes das dependências.
- Exibe um backend FastAPI para ingestão/pesquisa e uma UI Next.js para exploração.
- Fornece um servidor MCP em `/api/mcp` para consultas profundas.

---

## Atualizando a documentação (importante)

No momento, para atualizar a documentação após mudanças no código, remova o repo e reingira (fluxo temporário):

- Na UI: exclua o repositório do seu Workspace e adicione novamente (a ingestão inicia automaticamente).
- Pela API: exclua e reingira via serviço de ingestão:

```bash
# excluir dados locais (BD + clone)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# enfileirar uma nova ingestão
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

Estamos adicionando um botão de “Reingestão” com um clique e, em seguida, ingestão periódica automática. Muito em breve.

## Início rápido

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

Migração do banco (uma vez local):

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## Servidor MCP

- URL: `http://localhost:3000/api/mcp`
- Inclua o cabeçalho `x-repo-id`.

## Estrutura do projeto

- `ingestion/` — FastAPI, parsing AST, grafo, embeddings, busca.
- `webview/` — App Next.js e pacotes TS compartilhados.
- `docker-compose.yml` — Postgres, API e Web locais.

## Licença

MIT. Em caso de dúvida, consulte ../README.md (inglês).

## Problemas conhecidos

- O código do repositório deve estar na raiz, não em uma pasta aninhada.
- No momento, suportamos apenas TS, JS e Python; ampliaremos para Java e Kotlin e depois para Go e Rust.
- Ainda não há suporte multi‑linguagem (vários idiomas no mesmo repo), mas estamos trabalhando nisso.
