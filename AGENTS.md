# Repository Guidelines

## Project Structure & Module Organization
KnowledgeForge is a monorepo with three active modules under `sources/`:
- `sources/Api/`: FastAPI backend and C4 extraction services (`app/services/c4/`), tests in `sources/Api/tests/`.
- `sources/UI/`: React + TypeScript + Vite frontend (`src/`), tests as `*.test.tsx`.
- `sources/e2e/`: cross-service pipeline tests and fixtures.
Use `docs/architecture/` for technical design docs and `docs/plans/` for planning/status files.

## Build, Test, and Development Commands
Use root Make targets for full-stack workflows:
- `make up` / `make down`: start or stop UI, API, and infra via Docker.
- `make quick-check`: mandatory regression gate after logical changes.
- `make full-check`: full rebuild + E2E + validation for infra/Docker-level changes.
- `make tests`: API + UI + e2e suites.

Module-level development:
- Backend: `cd sources/Api && python app.py`
- Frontend: `cd sources/UI && npm run dev`
- UI quality gate: `cd sources/UI && npm run check-all`

## Workflows

### Creating/Modifying API Endpoints

When creating new API endpoints:

1. First plan the new endpoint changes, including new/updated methods, paths and request payloads
2. Confirm proposed changes with user
3. Implement the endpoint
4. Add/update endpoint in the .http file, including documenting endpoint and payloads
5. Test the .http file using: `docker run --rm -i -t -v $PWD:/workdir jetbrains/intellij-http-client <http_file_name>`

### Discovering Package Docs

When working with an unfamiliar package or third-party API, first use `chub` to discover relevant docs and packages before writing code:

```sh
chub search "stripe payments"        # find relevant docs
chub get stripe/api --lang js        # fetch the doc
# Agent reads the doc, writes correct code. Done.
```

## Coding Style & Naming Conventions
- Python: Black (88 cols), Ruff, MyPy, strict type hints, and Pydantic models for API/domain schemas.
- TypeScript/React: ESLint + Prettier (`singleQuote: true`, `tabWidth: 2`, `printWidth: 80`).
- Naming: `snake_case` (Python), `PascalCase` (React components), `test_*.py` and `*.test.tsx`.

## Code Style

- General:
  - Prefer writing clear code and use inline comments sparingly
- C#:
  - 4-space indent
  - `PascalCase` for classes/methods
  - `_camelCase` for private fields
  - `camelCase` for local variables, parameters
  - Prefer primary constructors where possible
  - Use auto-properties, and `field` if necessary
  - Write XML comments on all classes, methods, properties and fields
  - Tests:
    - `<ClassName>Tests` for test class
    - `<MethodName>_<Conditions>_<AssertedOutcome>` for test methods (never `Async` suffix)
    - Arrange, Act, Assert pattern (comment each section in method)
- TypeScript/JavaScript/CSS:
  - 2-space indent
  - Document all methods, types and interfaces with JSDoc comments
  - Keep `*.test.ts` files in same directory as corresponding `*.ts` file
- Commits:
  - Use Conventional Commit format
  - **Commit Types:** `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
  - **Scopes:** `web`, `api`, `docker`

## Documentation Principles

- Domain-Specific Jargon
- Architectural Decisions and Structure
- Keep It Concise
- Treat It Like a Living Document

## Testing Guidelines
- Backend unit/integration: `cd sources/Api && pytest tests/ -v`
- Frontend: `cd sources/UI && npm run test`
- End-to-end pipeline: `cd sources/e2e && ./run_tests.sh --verbose`
- Add tests for every behavior change and ensure extraction benchmark tests remain green.

## Commit & Pull Request Guidelines
- Prefer Conventional Commit style used in history: `feat(scope): ...`, `fix: ...`, `docs: ...`, `refactor: ...`.
- Keep commits focused and imperative (one logical change per commit).
- PRs should include:
  - concise summary and motivation,
  - linked issue/task,
  - test evidence (commands + results),
  - screenshots/GIFs for UI changes.

## Security, Scope & Team Notes
- Copy `.env.example` to `.env`; never commit secrets or tokens.
- Use `GITHUB_TOKEN` locally for GitHub scanning rate limits.
- Scope boundary: we own `sources/Api/app/services/c4/context/`; do not modify `sources/Api/app/services/c4/containers/` unless explicitly coordinated.
- Keep extraction metadata complete (domain, owner, status/lifecycle, tier, data_class, experts, compliance) and preserve human-readable UI labels.
