# KnowledgeForge - Secrets Management Setup

## Quick Start

### 1. Copy the environment template
```bash
cp .env.example .env
```

### 2. Edit `.env` with your actual credentials
```bash
nano .env  # or use your preferred editor
```

### 3. Configure your LLM provider

#### Option A: Use OpenAI API (Recommended for production)
```bash
# In .env file:
OPENAI_API_KEY=sk-your-actual-api-key-here
OPENAI_MODEL=gpt-4o-mini  # or gpt-4, gpt-3.5-turbo
```

#### Option B: Use Local LM Studio (Free, runs locally)
```bash
# In .env file:
OPENAI_API_KEY=  # Leave empty to use LM Studio

# Ensure LM Studio is running at:
# http://localhost:1234
```

### 4. Start the services
```bash
docker-compose up -d
```

---

## Environment Variables Reference

### Database Credentials
| Variable | Description | Example |
|----------|-------------|---------|
| `POSTGRES_PASSWORD` | PostgreSQL database password | `my_secure_pass_123` |
| `NEO4J_PASSWORD` | Neo4j graph database password | `my_neo4j_pass` |
| `NEO4J_AUTH` | Neo4j auth string | `neo4j/my_neo4j_pass` |

### LLM Configuration

#### OpenAI API (Option 1)
| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key | (empty - uses LM Studio) |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4o-mini` |
| `OPENAI_BASE_URL` | OpenAI API endpoint | `https://api.openai.com/v1` |

**Supported Models:**
- `gpt-4o-mini` - Fastest, cheapest (recommended)
- `gpt-4o` - More capable
- `gpt-4-turbo` - High quality
- `gpt-3.5-turbo` - Budget option

#### LM Studio (Option 2 - Default)
| Variable | Description | Default |
|----------|-------------|---------|
| `LMSTUDIO_BASE_URL` | LM Studio API endpoint | `http://localhost:1234/v1` |
| `LMSTUDIO_MODEL_NAME` | Model name in LM Studio | `llama2` |

---

## Security Best Practices

### ✅ DO
- Keep `.env` out of version control (already in `.gitignore`)
- Use strong, unique passwords for each service
- Rotate credentials regularly
- Use environment-specific `.env` files (`.env.dev`, `.env.prod`)
- Use secrets managers in production (AWS Secrets Manager, Vault)

### ❌ DON'T
- Never commit `.env` to git
- Never share `.env` files via email or chat
- Never use default passwords in production
- Never hardcode secrets in source code

---

## Troubleshooting

### Error: "Database connection failed"
- Check `POSTGRES_PASSWORD` matches in `.env`
- Verify PostgreSQL container is running: `docker-compose ps postgres`

### Error: "Neo4j authentication failed"
- Ensure `NEO4J_AUTH` format is `neo4j/password`
- Password in `NEO4J_AUTH` must match `NEO4J_PASSWORD`

### Error: "LLM enrichment timed out"
- **Using OpenAI**: Check your `OPENAI_API_KEY` is valid
- **Using LM Studio**: Ensure LM Studio is running at `http://localhost:1234`
- Check logs: `docker-compose logs api | grep -i llm`

### Switching between OpenAI and LM Studio
1. Edit `.env`
2. Set or clear `OPENAI_API_KEY`
3. Restart: `docker-compose restart api`

---

## Production Deployment

For production environments, use a secrets management service:

### AWS Secrets Manager
```bash
# Fetch secrets at runtime
aws secretsmanager get-secret-value --secret-id knowledgeforge/prod --query SecretString
```

### HashiCorp Vault
```bash
vault kv get secret/knowledgeforge/prod
```

### Kubernetes Secrets
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: knowledgeforge-secrets
type: Opaque
data:
  postgres-password: <base64-encoded>
  openai-api-key: <base64-encoded>
```

---

## Files Overview

| File | Purpose | Safe to commit? |
|------|---------|----------------|
| `.env.example` | Template with placeholders | ✅ Yes |
| `.env` | Actual secrets | ❌ **NEVER** |
| `docker-compose.yml` | Uses variables from `.env` | ✅ Yes |
| `README_SECRETS.md` | This documentation | ✅ Yes |
| `.gitignore` | Blocks `.env` from git | ✅ Yes |

---

## Default Credentials (Development Only)

**⚠️ Change these in production!**

- PostgreSQL: `knowledgeforge` / `knowledgeforge123`
- Neo4j: `neo4j` / `password`
- OpenAI: Not set (uses LM Studio by default)








