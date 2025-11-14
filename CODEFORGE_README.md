# KnowledgeForge → CodeForge Extension

CodeForge extends KnowledgeForge with code-native extraction so repositories, infrastructure manifests, and project metadata feed the same ontology pipeline as CSV uploads. The goal is deterministic, repeatable scans that can be reviewed and merged into the enterprise graph.

## Capabilities At A Glance
- **Source languages:** Python, JavaScript/TypeScript (extensible to Java, Go, C#, Rust, Ruby, PHP)
- **Infrastructure:** Dockerfiles, docker-compose, Kubernetes/Helm/Kustomize manifests
- **Configs:** package.json, pyproject.toml, pom.xml, build.gradle, go.mod, Cargo.toml, Gemfile, composer.json, lockfiles
- **CI/CD:** GitHub Actions, GitLab CI, Azure Pipelines, Jenkins, CircleCI
- **IaC (opt-in):** Terraform + Pulumi resource graphs
- **Outputs:** Code entities, relationships, dependencies, metadata, CSV export

## Runtime Architecture
| Layer | Location | Responsibility |
| --- | --- | --- |
| Domain models | `sources/api/app/domain/models/code_entities.py` | Typed entities, relationships, dependencies, diff payloads |
| Base extractor | `sources/Api/app/services/code_extraction/base_extractor.py` | Interface with `can_handle` and `extract` contracts |
| Language & manifest extractors | `.../python_extractor.py`, `javascript_extractor.py`, `docker_extractor.py`, `config_extractor.py`, `cicd_extractor.py` | Parse files, emit entities + relationships |
| Repository scanner | `.../repository_scanner.py` | Walk repo, route files to extractors, deduplicate, compute deterministic IDs, manage incremental scans |
| API routes | `sources/Api/app/endpoint/v1/routes/code_extraction.py` | Upload, scan, status, results, deletion endpoints |
| Persistence | `sources/api/app/infrastructure/graph/neo4j_manager.py`, `.../storage/metadata_store.py` | Store graph + task metadata |

### Processing Flow
1. Upload a ZIP (`/api/v1/code/upload-repo`) or point to a local repo (`/api/v1/code/scan`).
2. RepositoryScanner filters files, fans out to extractors, and aggregates entities/relationships/dependencies.
3. Deterministic IDs (SHA-256) enable idempotent writes and incremental diffs.
4. Results land in Neo4j plus the metadata store; optional CSV export keeps legacy tooling working.

## Quick Start
### 1. Upload a repository archive
```bash
curl -X POST http://localhost:8000/api/v1/code/upload-repo \
  -F "file=@your-repo.zip"
```

### 2. Trigger a scan for a local path
```bash
curl -X POST http://localhost:8000/api/v1/code/scan \
  -H "Content-Type: application/json" \
  -d '{
        "repo_path": "/abs/path/to/repo",
        "incremental": false,
        "force_full": true,
        "ignore_patterns": ["node_modules", "*.test.tsx"],
        "max_file_size_mb": 10
      }'
```
Key flags:
- `incremental=true` reuses the last snapshot and only re-extracts changed files.
- `force_full=true` bypasses diffing even if a prior snapshot exists.
- `ignore_patterns` uses fnmatch-style globbing.

### 3. Track progress and fetch results
Status endpoint:
```bash
curl http://localhost:8000/api/v1/code/scan/{task_id}
```
Detailed output:
```bash
curl http://localhost:8000/api/v1/code/scan/{task_id}/results
```
Responses include entity counts, relationship counts, dependency details, and timing stats.

### 4. Clean up
```bash
curl -X DELETE http://localhost:8000/api/v1/code/scan/{task_id}
```

## Data Contracts (abridged)
- `CodeEntity`: classes, functions, services, containers, pipelines, configs
- `CodeRelationship`: `calls`, `imports`, `depends_on`, `deploys`, `connects_to`
- `DependencyInfo`: manifest + lockfile dependency detail
- `SourceFile`: file-level metadata (path, hash, language, size)
- `IncrementalScanResult`: created/updated/deleted entity lists for change review

## Extending CodeForge
1. Create a new extractor inheriting `BaseExtractor`.
2. Implement `can_handle(file_path: Path) -> bool` to gate file types.
3. Implement `extract(file_path: Path, file_contents: str) -> ExtractionResult` returning entities + relationships.
4. Register the extractor inside `RepositoryScanner.__init__`.
5. Add unit coverage under `sources/Api/tests/services/code_extraction` and update `CODEFORGE_README.md` if the capability set changes.

## Operational Tips
- Keep scans deterministic by avoiding random IDs or timestamps inside extractors.
- Use `ignore_patterns` for vendor directories (`node_modules`, `.git`, build outputs) to keep runs fast.
- Incremental scans rely on file hashes; deleting the metadata store forces a full re-scan.
- When testing locally without Docker, set `KF_NEO4J__URI`, `KF_DATABASE__*`, and storage paths via env vars or `config.yaml`.

## Related Files
- `QUICKSTART_CODEFORGE.md` – CLI workflow for uploads and scans
- `RUN_GUIDE.md` – Operational checklist for standing up the full platform
- `sources/api/tests/test_pipeline.py` – Example of how extraction output flows into downstream steps
