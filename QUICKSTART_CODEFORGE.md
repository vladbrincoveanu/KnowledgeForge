# CodeForge Quick Start Guide

Get started with code-native extraction in 5 minutes!

## Prerequisites

```bash
# Install dependencies
cd sources/Api
pip install -r requirements.txt

# Ensure Neo4j is running
docker-compose up -d neo4j

# Start the API
python app.py
```

## Option 1: Upload a Repository ZIP

### Step 1: Create a ZIP of your repository
```bash
cd /path/to/your/repo
zip -r my-repo.zip . -x "*.git*" -x "*node_modules*" -x "*venv*"
```

### Step 2: Upload via API
```bash
curl -X POST http://localhost:8000/api/v1/code/upload-repo \
  -F "file=@my-repo.zip"
```

**Response**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Repository uploaded and scan queued",
  "created_at": "2024-01-15T10:30:00"
}
```

### Step 3: Check Status
```bash
TASK_ID="550e8400-e29b-41d4-a716-446655440000"

curl http://localhost:8000/api/v1/code/scan/$TASK_ID
```

**Response**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 1.0,
  "message": "Scan completed",
  "entities_count": 234,
  "relationships_count": 456,
  "dependencies_count": 89
}
```

### Step 4: Get Results
```bash
curl http://localhost:8000/api/v1/code/scan/$TASK_ID/results | jq '.'
```

## Option 2: Scan a Local Repository

```bash
curl -X POST http://localhost:8000/api/v1/code/scan \
  -H "Content-Type: application/json" \
  -d '{
    "repo_path": "/absolute/path/to/repo",
    "incremental": false,
    "force_full": true,
    "ignore_patterns": ["*.test.js", "*.spec.ts"]
  }'
```

## Option 3: Use Python API Directly

```python
from pathlib import Path
from app.services.code_extraction.repository_scanner import RepositoryScanner

# Initialize scanner
scanner = RepositoryScanner(
    repo_path=Path("/path/to/repo"),
    ignore_patterns=["*.min.js", "dist/"],
    max_file_size_mb=10.0
)

# Perform full scan
result = scanner.scan(force_full=True)

# Print statistics
print(f"📊 Scan Results:")
print(f"  Total files: {len(result.files)}")
print(f"  Entities: {len(result.entities)}")
print(f"  Relationships: {len(result.relationships)}")
print(f"  Dependencies: {len(result.dependencies)}")
print(f"  Duration: {result.extraction_duration_seconds:.2f}s")

# List languages detected
print(f"\n📚 Languages detected:")
for lang in result.repository.languages_detected:
    print(f"  - {lang.value}")

# Show entity breakdown
from collections import Counter
entity_types = Counter(e.entity_type.value for e in result.entities)
print(f"\n🔍 Entity Types:")
for entity_type, count in entity_types.most_common(10):
    print(f"  {entity_type}: {count}")

# Show top dependencies
print(f"\n📦 Top Dependencies:")
for dep in result.dependencies[:10]:
    print(f"  {dep.name} ({dep.version or dep.version_spec})")
```

## Incremental Scanning

After making changes to your repository:

```python
# First scan
scanner = RepositoryScanner("/path/to/repo")
result1 = scanner.scan()

# Make changes to the code...

# Incremental scan (only changed files)
diff = scanner.incremental_scan()

print(f"📝 Changes detected:")
print(f"  Added: {len(diff.added_entities)} entities")
print(f"  Modified: {len(diff.modified_entities)} entities")
print(f"  Deleted: {len(diff.deleted_entity_ids)} entities")
print(f"  Unchanged: {diff.unchanged_entity_count} entities")
```

## View Results in Neo4j

After scanning, view the graph in Neo4j Browser:

```cypher
// Count entities by type
MATCH (e:Entity)
WHERE e.source_type = 'code'
RETURN e.entity_type, count(*) as count
ORDER BY count DESC

// View Python classes
MATCH (c:Entity)
WHERE c.entity_type = 'class' AND c.language = 'python'
RETURN c.name, c.file_path
LIMIT 10

// View relationships
MATCH (e1:Entity)-[r]->(e2:Entity)
WHERE e1.source_type = 'code' AND e2.source_type = 'code'
RETURN type(r), count(*) as count
ORDER BY count DESC

// View dependencies
MATCH (e:Entity)
WHERE e.entity_type = 'dependency'
RETURN e.name, e.version
LIMIT 20

// Find classes with most methods
MATCH (c:Entity {entity_type: 'class'})<-[:CONTAINS]-(m:Entity {entity_type: 'method'})
RETURN c.name, count(m) as method_count
ORDER BY method_count DESC
LIMIT 10
```

## Common Use Cases

### 1. Scan a Python Project
```bash
curl -X POST http://localhost:8000/api/v1/code/scan \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/path/to/python-project"}'
```

### 2. Scan a Node.js Project
```bash
curl -X POST http://localhost:8000/api/v1/code/scan \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/path/to/nodejs-project"}'
```

### 3. Scan Infrastructure-as-Code
```bash
curl -X POST http://localhost:8000/api/v1/code/scan \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/path/to/terraform-project"}'
```

### 4. Extract CI/CD Pipelines
```bash
# Your repo with .github/workflows/*.yml
curl -X POST http://localhost:8000/api/v1/code/scan \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/path/to/repo-with-actions"}'
```

## What Gets Extracted

### Python Projects
- ✅ Modules, Classes, Methods, Functions
- ✅ Inheritance relationships
- ✅ Function calls
- ✅ Import statements
- ✅ Dependencies from pyproject.toml, requirements.txt

### JavaScript/TypeScript Projects
- ✅ Modules, Classes, Functions
- ✅ Import/Export relationships
- ✅ Dependencies from package.json
- ✅ Lockfile versions (package-lock.json, yarn.lock)

### Docker Projects
- ✅ Container definitions
- ✅ Services from docker-compose
- ✅ Volumes, Networks
- ✅ Service dependencies

### CI/CD
- ✅ Pipelines, Jobs, Steps
- ✅ Triggers and workflows
- ✅ Job dependencies

### Infrastructure-as-Code
- ✅ Terraform resources
- ✅ Resource dependencies
- ✅ Variables and outputs
- ✅ Pulumi projects

## Troubleshooting

### Issue: "No module named 'tomli'"
```bash
pip install tomli
```

### Issue: Scan is slow
```python
# Use smaller max file size
scanner = RepositoryScanner(
    repo_path=path,
    max_file_size_mb=5.0  # Default is 10MB
)

# Add more ignore patterns
scanner = RepositoryScanner(
    repo_path=path,
    ignore_patterns=[
        "*.min.js",
        "dist/*",
        "build/*",
        "*.map"
    ]
)
```

### Issue: Memory errors
```bash
# Increase Docker memory
docker update --memory 4g neo4j
```

### Issue: Neo4j connection failed
```bash
# Check Neo4j is running
docker ps | grep neo4j

# Check credentials in config.yaml
cat sources/Api/config.yaml
```

## Next Steps

1. **Explore the API**: Try different endpoints at http://localhost:8000/docs
2. **View in UI**: Open the KnowledgeForge UI to review extracted entities
3. **Query Neo4j**: Use Cypher queries to explore relationships
4. **Export Data**: Get CSV exports for further analysis
5. **Integrate**: Use the API in your CI/CD pipeline

## Advanced Usage

### Custom Ignore Patterns
```python
scanner = RepositoryScanner(
    repo_path="/path/to/repo",
    ignore_patterns=[
        "tests/",
        "*.test.*",
        "*.spec.*",
        "coverage/",
        ".cache/",
        "*.log"
    ]
)
```

### Filter by Language
```python
result = scanner.scan()

# Get only Python entities
python_entities = [
    e for e in result.entities 
    if e.language == CodeLanguage.PYTHON
]

# Get only JavaScript/TypeScript entities
js_entities = [
    e for e in result.entities 
    if e.language in [CodeLanguage.JAVASCRIPT, CodeLanguage.TYPESCRIPT]
]
```

### Analyze Dependencies
```python
result = scanner.scan()

# Group by language
from collections import defaultdict
deps_by_lang = defaultdict(list)

for dep in result.dependencies:
    deps_by_lang[dep.language.value].append(dep)

for lang, deps in deps_by_lang.items():
    print(f"\n{lang}: {len(deps)} dependencies")
    for dep in deps[:5]:
        print(f"  - {dep.name} ({dep.version or dep.version_spec})")
```

## Tips & Best Practices

1. **Start Small**: Test with a small repository first
2. **Use Incremental**: After initial scan, use incremental for faster updates
3. **Ignore Build Artifacts**: Always ignore dist/, build/, node_modules/, venv/
4. **Monitor Memory**: Large repositories may need more RAM
5. **Export Regularly**: Keep CSV backups of important scans
6. **Review Changes**: Use the diff to understand what changed

## Support

- 📖 Full Documentation: [CODEFORGE_README.md](CODEFORGE_README.md)
- 🔧 Implementation Details: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- 🌐 Main README: [README.md](README.md)

---

**Ready to extract your codebase?** Start scanning now! 🚀
