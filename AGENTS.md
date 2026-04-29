# Repository Guidelines

## Project Structure
KnowledgeForge is a C4 architecture extraction engine: analyze codebases → produce C4 graphs stored in Neo4j/PostgreSQL.

**Stack:** FastAPI (Python 3.11) / React+TypeScript (Vite) / Neo4j / PostgreSQL / Docker

- `sources/Api/` — FastAPI backend, C4 extraction services (`app/services/c4/`)
- `sources/UI/` — React frontend (Vite + Cytoscape + ReactFlow), Playwright E2E tests in `e2e/specs/`
- `sources/demo/` — 23 OmniPay fixture repos used as extraction test inputs (read-only)
- `sources/e2e/` — deprecated (actual E2E tests live in `sources/Api/tests/e2e/`)

**Important:** There are two `package.json` files. The root `package.json` is a stale shadcn template — ignore it. All frontend tooling lives in `sources/UI/package.json`.

## Workspace Boundary (the "iron curtain")
- `sources/Api/app/services/c4/context/` — **our workspace**, can modify
- `sources/Api/app/services/c4/containers/` — **do not modify** (parallel squad's territory)

## Build, Test, and Development Commands

### Root Make targets (run from repo root)
- `make up` / `make down` — start/stop all services via Docker
- `make quick-check` — fast restart + E2E tests (run after logical changes)
- `make full-check` — full rebuild + E2E (run after infra/Docker-level changes)
- `make tests` — API unit tests + pipeline + UI tests (does NOT include Docker E2E)
- `make fix` — auto-format API (Black) + UI (Prettier + ESLint fix)

### Local development (no Docker)
```bash
cd sources/Api && python3 main.py          # API server on :8000
cd sources/UI && npm run dev               # Frontend on :3000
```

### Frontend quality gates (run from `sources/UI/`)
```bash
npm run fix-all      # format + lint:fix + type-check
npm run check-all    # type-check + lint + format:check
npm run test         # vitest (run after any UI change)
npm run test:e2e     # Playwright E2E tests (requires: make up)
npm run test:e2e:ui  # Playwright UI mode for debugging
```

### Backend tests
```bash
cd sources/Api && python3 -m pytest tests/ -v           # unit tests
cd sources/Api && python3 tests/test_pipeline.py        # pipeline integration
docker compose exec api python tests/test_pipeline.py   # via Docker
```

### E2E extraction tests (require Docker services running)
```bash
make test-e2e                    # OmniPay extraction benchmarks (Python)
make test-e2e-omnipay-verbose    # with detailed output
npm run test:e2e                 # Playwright browser E2E tests (from sources/UI/)
```

## API Endpoint Workflow
1. Plan endpoint changes, confirm with user
2. Implement in `sources/Api/app/`
3. Add/update request in `sources/Api/code_extraction.http`
4. Test via: `docker run --rm -i -t -v $PWD:/workdir jetbrains/intellij-http-client sources/Api/code_extraction.http`

## Coding Conventions

### Python
- Black (88 cols), Ruff, MyPy (strict type hints)
- Pydantic V2 models for API/domain schemas (`validate_by_name`, NOT `allow_population_by_field_name`)
- Typed exceptions from `app/domain/exceptions.py` — never bare `except Exception:` (except for 3rd-party LLM calls)
- `snake_case`, `pathlib` over `os.path`, f-strings over `.format()`

### TypeScript/React
- Prettier + ESLint: `singleQuote: true`, `tabWidth: 2`, `printWidth: 80`
- Functional components with hooks, `React.memo()` for expensive components
- `*.test.tsx` files co-located with source
- Tests: Vitest + Testing Library

### Commits
Conventional Commit format: `feat(scope):`, `fix(scope):`, `docs:`, `refactor:`, `test:`, `chore:`
Scopes: `web`, `api`, `docker`

## Key Architecture Notes
- Extraction pipeline: GitHub URL → ServiceDiscovery → ServiceEnhancers (8 phases) → Neo4j + PostgreSQL
- Each service has 5 primary fields: domain, owner, status, tier, data_class
- ServiceStatus canonical values: `ACTIVE`, `MAINTENANCE`, `DEPRECATED`, `ARCHIVED` (not old strings like "Active-Dev")
- Owner detection requires `full_history=True` in github_downloader.py
- Zip extraction must use `safe_extract_zip()` to block path traversal

## Security
- Copy `.env.example` to `.env`; never commit secrets or tokens
- Sanitize user input to prevent XSS
- Never expose internal error details to API consumers
