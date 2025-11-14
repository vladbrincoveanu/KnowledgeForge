# How to Run KnowledgeForge with Code Extraction

## Quick Start (Docker - Recommended)

### 1. Start All Services

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge

# Start infrastructure (Neo4j, PostgreSQL) and API
make up

# OR manually:
cd sources/Api
docker-compose up -d
```

This starts:
- **PostgreSQL** on port `5432`
- **Neo4j** on port `7687` (Bolt) and `7474` (HTTP)
- **API** on port `8000`

### 2. Verify Services Are Running

```bash
# Check status
make status

# OR
docker-compose ps

# Check API health
curl http://localhost:8000/health
```

### 3. Access Services

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Neo4j Browser**: http://localhost:7474
  - Username: `neo4j`
  - Password: `password`

---

## Option 2: Local Development (Without Docker)

### 1. Install Dependencies

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
cd Api
pip install -r requirements.txt
```

### 2. Start Infrastructure Services

You still need Neo4j and PostgreSQL running. Options:

**Option A: Use Docker for infrastructure only**
```bash
cd sources/Api
docker-compose up -d postgres neo4j
```

**Option B: Install locally**
- Install PostgreSQL and Neo4j locally
- Update `config.yaml` with local connection strings

### 3. Update Configuration

Edit `sources/Api/config.yaml`:

```yaml
neo4j:
  uri: "bolt://localhost:7687"  # Change from docker service name
  username: "neo4j"
  password: "password"

database:
  host: "localhost"  # Change from docker service name
  port: 5432
```

### 4. Run the API

```bash
cd sources/Api
source ../venv/bin/activate
python app.py
```

The API will start on `http://localhost:8000`

---

## Testing Code Extraction

### 1. Upload a Repository (ZIP)

```bash
# Create a test repository ZIP
cd /tmp
mkdir test-repo
cd test-repo
echo "def hello(): pass" > hello.py
echo '{"name": "test", "version": "1.0.0"}' > package.json
zip -r test-repo.zip .

# Upload via API
curl -X POST http://localhost:8000/api/v1/code/upload-repo \
  -F "file=@test-repo.zip"
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Repository uploaded and scan queued",
  "created_at": "2024-01-15T10:30:00"
}
```

### 2. Check Scan Status

```bash
TASK_ID="550e8400-e29b-41d4-a716-446655440000"

curl http://localhost:8000/api/v1/code/scan/$TASK_ID | jq
```

### 3. Get Results

```bash
curl http://localhost:8000/api/v1/code/scan/$TASK_ID/results | jq
```

### 4. Scan Local Repository

```bash
curl -X POST http://localhost:8000/api/v1/code/scan \
  -H "Content-Type: application/json" \
  -d '{
    "repo_path": "/path/to/your/repo",
    "incremental": false,
    "force_full": true
  }'
```

---

## Using the Interactive API Docs

1. Open http://localhost:8000/docs
2. Navigate to `/api/v1/code/` section
3. Try the endpoints:
   - `POST /api/v1/code/upload-repo` - Upload repository ZIP
   - `POST /api/v1/code/scan` - Scan local repository
   - `GET /api/v1/code/scan/{task_id}` - Get scan status
   - `GET /api/v1/code/scan/{task_id}/results` - Get results

---

## Python API Usage

```python
from pathlib import Path
from app.services.code_extraction.repository_scanner import RepositoryScanner

# Initialize scanner
scanner = RepositoryScanner(
    repo_path=Path("/path/to/repo"),
    ignore_patterns=["*.test.js", "dist/"],
    max_file_size_mb=10.0
)

# Full scan
result = scanner.scan(force_full=True)

print(f"Entities: {len(result.entities)}")
print(f"Relationships: {len(result.relationships)}")
print(f"Dependencies: {len(result.dependencies)}")

# Incremental scan
diff = scanner.incremental_scan()
print(f"Added: {len(diff.added_entities)}")
print(f"Modified: {len(diff.modified_entities)}")
```

---

## Viewing Results in Neo4j

1. Open Neo4j Browser: http://localhost:7474
2. Login: `neo4j` / `password`
3. Run queries:

```cypher
// Count code entities
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
WHERE e1.source_type = 'code'
RETURN type(r), count(*) as count
ORDER BY count DESC
```

---

## Troubleshooting

### API won't start

```bash
# Check logs
docker-compose logs api

# OR if running locally
tail -f sources/Api/logs/api.log
```

### Neo4j connection failed

```bash
# Check Neo4j is running
docker ps | grep neo4j

# Test connection
curl http://localhost:7474

# Check credentials in config.yaml
cat sources/Api/config.yaml | grep neo4j
```

### Missing dependencies

```bash
# Reinstall
cd sources
source venv/bin/activate
cd Api
pip install -r requirements.txt
```

### Port conflicts

```bash
# Check what's using port 8000
lsof -i :8000

# Change port in docker-compose.yml or config.yaml
```

---

## Development Workflow

### 1. Make Code Changes

Edit files in `sources/Api/app/`

### 2. Restart API (Docker)

```bash
# Restart with code changes (volume-mounted)
make restart-api-dev

# OR rebuild image
make restart-api
```

### 3. Restart API (Local)

```bash
# Stop current process (Ctrl+C)
# Then restart
cd sources/Api
source ../venv/bin/activate
python app.py
```

### 4. View Logs

```bash
# Docker
docker-compose logs -f api

# Local
tail -f sources/Api/logs/api.log
```

---

## Common Commands

```bash
# Start everything
make up

# Stop everything
make down

# View logs
make logs

# Check status
make status

# Restart API only
make restart-api-dev

# Run tests
make tests

# Clean up
make clean
```

---

## Next Steps

1. ✅ **Test with a small repository** - Upload a simple Python/JS project
2. ✅ **Check Neo4j** - Verify entities are stored correctly
3. ✅ **Try incremental scan** - Make changes and re-scan
4. ✅ **Explore API docs** - Use Swagger UI at `/docs`
5. ✅ **Query the graph** - Use Cypher queries in Neo4j Browser

---

## Support

- 📖 **Full Documentation**: [CODEFORGE_README.md](CODEFORGE_README.md)
- 🚀 **Quick Start**: [QUICKSTART_CODEFORGE.md](QUICKSTART_CODEFORGE.md)
- 📋 **Implementation**: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)

