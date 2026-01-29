# KnowledgeForge

Transform disparate enterprise data into an actionable knowledge graph. KnowledgeForge couples a FastAPI backend, a React/Vite UI, and a Neo4j/Postgres data layer with automated code-&-document extraction capabilities.

## Highlights
- Polyglot code, document, and metadata extraction feeding a unified ontology
- FastAPI service with WebSocket progress updates plus REST queries
- React/Vite UI for uploads, graph exploration, and system monitoring
- Docker-first deployment with optional local development paths
- End-to-end (Playwright/Pytest) automation plus Makefile-driven workflows

## Important Paths
- `docker-compose.yml` – Spins up Neo4j, Postgres, API, UI, and Portainer
- `Makefile` – Single entry point for running, testing, linting, and cleaning
- `sources/api` – FastAPI service (LLM-assisted extraction, graph persistence)
- `sources/ui` – React TypeScript client (drag-and-drop uploads, graph view)
- `sources/e2e` – End-to-end tests hitting the full stack
- `CODEFORGE_README.md` – Deep dive into the repository/code extraction engine
- `RUN_GUIDE.md`, `QUICKSTART_CODEFORGE.md` – Supplemental how-tos if you need more detail

## Prerequisites
- Docker Desktop 24+ (Compose v2)
- Python 3.11 (for local API development/tests)
- Node.js 18+ and npm 9+ (for local UI work)
- Optionally LM Studio/OpenAI credentials when enabling LLM features

## Quick Start (Docker Compose)
1. Update `sources/api/config.yaml` with the credentials for your environment (defaults match the Compose file).
2. Build and start everything:
   ```bash
   make up
   ```
   (Use `docker compose up --build` if you prefer raw Compose commands.)
3. Verify services:
   - UI: http://localhost:3000
   - API & docs: http://localhost:8000 /docs
   - Neo4j Browser: http://localhost:7474 (neo4j/password)
   - Postgres: localhost:5432 (knowledgeforge/knowledgeforge123)
4. Stop the stack when you are done:
   ```bash
   make down
   ```

## Local Development Without Docker
### Backend API (FastAPI)
```bash
cd sources
python3 -m venv venv && source venv/bin/activate
pip install -r api/requirements.txt
cd api
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```
Or run `python app.py` for the same entry point without auto-reload.
The API expects Postgres + Neo4j. You can either keep the Docker Compose databases running (`docker compose up -d postgres neo4j`) or point the config at your own instances.

### Frontend UI (React/Vite)
```bash
cd sources/ui
npm install
npm run dev
```
Set `VITE_API_URL`/`VITE_APP_API_URL` in `.env` (defaults point to http://localhost:8000 and the dev server runs on http://localhost:5173).

### Running Individual Infrastructure Services
```
docker compose up -d postgres neo4j
```
Use `make infra` if you prefer the Makefile wrapper.

## Testing & Quality Gates
- `make tests` – Runs API unit + pipeline tests, UI Vitest suite, and e2e checks
- `make test-api` / `make e2e` – Targeted subsets
- `cd sources/api && pytest` – FastAPI unit/pipeline tests
- `cd sources/ui && npm run test` – Vitest/RTL suite
- `make validate` – Format, lint, type-check, and test everything (pre-commit style)

## Preparing a PR
1. Sync main: `git checkout main && git pull` then branch.
2. Keep docs and configs updated (especially `README.md`, `CODEFORGE_README.md`, `docker-compose.yml`).
3. Run `make fix` to apply formatters, then `make validate`.
4. Ensure `docker compose up --build` works end-to-end.
5. Commit only the relevant files (code, docs, configs) and open the PR with context plus run instructions.

## Additional Documentation
- `CODEFORGE_README.md` – Extraction engine design + API reference
- `RUN_GUIDE.md` – Ops checklists for deployments
- `IMPLEMENTATION_SUMMARY.md` – Architecture decisions and roadmap

Let the README be the single source of truth—if something changes (ports, env vars, services), update this file alongside your code.
