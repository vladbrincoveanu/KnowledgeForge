# KnowledgeForge

KnowledgeForge transforms code and documents into a unified architecture graph with C4 context views, dependency classification, and a React/Vite UI on top of a FastAPI + Neo4j/Postgres backend.

## Quick Start (Docker)
```bash
make up
```
Services:
- UI: http://localhost:3000
- API + docs: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474 (neo4j/password)

Stop:
```bash
make down
```

## Local Development
### API
```bash
cd sources/Api
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### UI
```bash
cd sources/UI
npm install
npm run dev
```

## Extraction & C4 Context
System context extraction includes:
- domain, owner, status, tier, data_class, active_experts, compliance
- external dependencies (values.yaml, README, .env, docker-compose)
- actors (users/administrators)

External dependencies are classified as BUSINESS_SYSTEM vs TECHNICAL_INFRA for C4 context/container separation.

## GitHub Scanning
Set `GITHUB_TOKEN` in `.env` for higher rate limits (5000/hr) during org scans.

## Workspace Separation
- `sources/Api/app/services/c4/context/` is our workspace
- `sources/Api/app/services/c4/containers/` is owned by another developer

## Testing
After any changes, run:
```bash
make quick-check
```
For major infrastructure changes, use:
```bash
make full-check
```

## Recent Work & Status (Task Updates)

- Task #2 — Baseline integration tests for CodeArchitectureViewer: DONE. Tests scaffolded and committed at sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.test.tsx.
- Task #3 — Baseline integration tests for ArchitectureMap: DONE. Tests added at sources/UI/src/@components/architecture-map/ArchitectureMap.test.tsx.
- Task #4 — Decompose CodeArchitectureViewer: IN PROGRESS. NodeDetails stub created and unit test added at sources/UI/src/@components/architecture-map/CodeArchitectureViewer/components/NodeDetails.tsx.
- Fixes applied: deterministic compliance_factors formatting in sources/Api/app/services/c4/context/metadata_detector.py; compatibility shim added at sources/Api/app/utils/config.py to provide get_config() for app.utils imports.

Conclusion: API E2E extraction tests (12) previously passed after earlier changes; NodeDetails stub added to begin safe decomposition. Next: Task #5 — Extract ServiceLegend and GraphControls stubs and add unit tests. Note: E2E tests were not re-run after the NodeDetails change.

