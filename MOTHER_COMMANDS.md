# Mother Commands - Complete Development Workflows

## 🎯 Overview

Three comprehensive "mother" commands that orchestrate complete workflows to catch errors fast and ensure quality.

---

## 🚀 Quick Start

```bash
# Daily development workflow
make quick-check         # ⚡ Fast (1-2 min)

# Before committing
make full-check          # 🔥 Complete (5-10 min)

# Before pushing/merging
make ci                  # 🤖 Production-ready (3-5 min)
```

---

## ⚡ make quick-check

**Purpose:** Fast iteration during development  
**Time:** 1-2 minutes  
**When to use:** After making code changes, before committing

### What it does:

```
1. ♻️  Restart services (no rebuild)
2. ✅ Check service health
3. 🧪 Run E2E tests (11 tests)
4. 🔍 Quick syntax check (imports)
```

### Output:
```
╔════════════════════════════════════════════════════════════════╗
║  ⚡ QUICK CHECK - Fast Restart + Tests                        ║
╚════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Step 1/4: Restarting services...
✅ Services restarted

📋 Step 2/4: Checking service status...
✅ API is running

📋 Step 3/4: Running E2E tests...
✅ 11/11 tests passed

📋 Step 4/4: Quick syntax check...
✅ Imports OK

╔════════════════════════════════════════════════════════════════╗
║  ✅ QUICK CHECK COMPLETE - Ready to develop!                  ║
╚════════════════════════════════════════════════════════════════╝
```

### Use cases:
- ✅ After editing Python files
- ✅ After changing configuration
- ✅ Before committing code
- ✅ Multiple times per hour

---

## 🔥 make full-check

**Purpose:** Complete rebuild and validation  
**Time:** 5-10 minutes  
**When to use:** Major changes, dependency updates, before important commits

### What it does:

```
1. 🛑 Stop all services
2. 🧹 Clean Docker system
3. 🏗️  Build Docker images (no cache)
4. 🚀 Start services
5. ⏳ Wait for readiness (10s)
6. 🏥 Health checks
7. 🧪 Run E2E tests (11 tests)
8. 🔍 Validation checks (Python syntax)
```

### Output:
```
╔════════════════════════════════════════════════════════════════╗
║  🔥 FULL CHECK - Complete Rebuild + Tests + Validation        ║
╚════════════════════════════════════════════════════════════════╝

⏱️  Estimated time: 5-10 minutes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Step 1/7: Stopping all services...
✅ Services stopped

📋 Step 2/7: Cleaning Docker system...
✅ Docker system cleaned

📋 Step 3/7: Building Docker images (no cache)...
✅ Docker images built

📋 Step 4/7: Starting services...
✅ Services started

📋 Step 5/7: Checking service health...
✅ All services healthy

📋 Step 6/7: Running E2E tests...
✅ 11/11 tests passed

📋 Step 7/7: Running validation checks...
✅ Python syntax OK

╔════════════════════════════════════════════════════════════════╗
║  ✅ FULL CHECK COMPLETE - All systems operational!            ║
╚════════════════════════════════════════════════════════════════╝
```

### Use cases:
- ✅ After dependency updates (requirements.txt)
- ✅ After Docker configuration changes
- ✅ Before major feature commits
- ✅ When things feel "weird"
- ✅ Once per day (morning routine)

---

## 🤖 make ci

**Purpose:** CI/CD pipeline simulation  
**Time:** 3-5 minutes  
**When to use:** Before pushing, creating PR, or merging

### What it does:

```
1. 📊 Git status check
2. 🛑 Stop all services
3. 🏗️  Build Docker images (with cache)
4. 🚀 Start services
5. ⏳ Wait for readiness (10s)
6. 🏥 Health checks (API + UI)
7. 🧪 Run E2E tests (detailed output)
8. 🔍 Code quality checks (imports)
9. 💾 Docker resource check
```

### Output:
```
╔════════════════════════════════════════════════════════════════╗
║  🤖 CI/CD PIPELINE - Production-Ready Checks                  ║
╚════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Step 1/8: Git status check...
✅ Git status OK

📋 Step 2/8: Stopping services...
✅ Services stopped

📋 Step 3/8: Building Docker images...
✅ Docker build successful

📋 Step 4/8: Starting services...
✅ Services started

📋 Step 5/8: Health checks...
✅ API is healthy
✅ UI is responding

📋 Step 6/8: Running E2E tests...
✅ 11/11 tests passed

📋 Step 7/8: Code quality checks...
✅ All imports OK

📋 Step 8/8: Docker resource check...
[Resource usage table]

╔════════════════════════════════════════════════════════════════╗
║  ✅ CI/CD PIPELINE COMPLETE - Ready for production!           ║
╚════════════════════════════════════════════════════════════════╝

🎉 All checks passed! Safe to merge/deploy.

📊 Test Summary:
  ✅ Docker build successful
  ✅ Services healthy
  ✅ E2E tests passed (11/11)
  ✅ Import checks passed
  ✅ Git status clean
```

### Use cases:
- ✅ Before `git push`
- ✅ Before creating Pull Request
- ✅ Before merging to main
- ✅ Pre-deployment validation
- ✅ Weekly full validation

---

## 🎯 Comparison Matrix

| Command | Time | Rebuild | Tests | Use Case |
|---------|------|---------|-------|----------|
| `quick-check` | 1-2 min | ❌ No | ✅ E2E | Development iteration |
| `full-check` | 5-10 min | ✅ Yes (no cache) | ✅ E2E + Syntax | Major changes |
| `ci` | 3-5 min | ✅ Yes (with cache) | ✅ E2E + Quality | Pre-push validation |

---

## 💡 Recommended Workflow

### Daily Development
```bash
# Morning: Start fresh
make full-check

# After each change
make quick-check

# Before lunch/end of day
make quick-check
```

### Before Committing
```bash
# Check everything is good
make quick-check

# If all green, commit
git add .
git commit -m "feat: your changes"
```

### Before Pushing
```bash
# Full validation
make ci

# If all green, push
git push origin your-branch
```

---

## 🚨 Error Handling

### If `quick-check` fails:
```bash
# Check API logs
make logs

# Or restart everything
make restart
make quick-check
```

### If `full-check` fails:
```bash
# Check what failed in the output
# Fix the issue
# Run again
make full-check
```

### If `ci` fails:
```bash
# Check git status
git status

# Check service health
make status

# View detailed logs
make logs

# Try full rebuild
make full-check
```

---

## 🎯 Exit Codes

All commands follow standard exit codes:

- **0** - All checks passed ✅
- **1** - At least one check failed ❌

### Examples:
```bash
# Success
make quick-check && echo "Ready to commit!"

# Failure
make quick-check || echo "Fix errors first!"

# Chain commands
make quick-check && git commit && make ci && git push
```

---

## 📊 What Gets Tested

### E2E Test Suite (11 tests):
1. ✅ System context basic fields
2. ✅ IT landscape fields (7 fields)
3. ✅ Owner detection from Git
4. ✅ Container detection
5. ✅ Container required fields
6. ✅ Container endpoints
7. ✅ JSON serialization
8. ✅ Relationships structure
9. ✅ Git metadata
10. ✅ Repository URL
11. ✅ UI data display

### Validation Checks:
- ✅ Docker build success
- ✅ Service health (API + UI)
- ✅ Python syntax (no import errors)
- ✅ Git status (clean/dirty)
- ✅ Resource usage (Docker stats)

---

## 🔄 Aliases

Quick shortcuts:
```bash
make check      # Same as quick-check
make full       # Same as full-check
make all        # Same as full-check
```

---

## 🎨 Visual Features

### Progress Bars
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Step 3/7: Building Docker images...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Status Boxes
```
╔════════════════════════════════════════════════════════════════╗
║  ✅ QUICK CHECK COMPLETE - Ready to develop!                  ║
╚════════════════════════════════════════════════════════════════╝
```

### Emoji Indicators
- 🚀 Starting
- ✅ Success
- ❌ Failure
- ⚠️  Warning
- 📋 Step
- ⏳ Waiting
- 🧪 Testing
- 🔍 Checking

---

## 🎯 Pro Tips

1. **Alias in your shell:**
   ```bash
   alias qc='make quick-check'
   alias fc='make full-check'
   alias pci='make ci'
   ```

2. **Pre-commit hook:**
   ```bash
   # .git/hooks/pre-commit
   #!/bin/bash
   make quick-check || exit 1
   ```

3. **Watch mode (development):**
   ```bash
   # Install watch
   brew install watch  # macOS
   
   # Auto-run on file changes
   watch -n 30 'make quick-check'
   ```

4. **CI/CD integration:**
   ```yaml
   # .github/workflows/test.yml
   - name: Run CI checks
     run: make ci
   ```

---

## 📈 Performance

### Timing Breakdown:

**quick-check (1-2 min):**
- Restart: 5-10s
- Health check: 5s
- Tests: 60s
- Validation: 5s

**full-check (5-10 min):**
- Stop: 10s
- Clean: 30s
- Build: 3-5min
- Start: 30s
- Wait: 10s
- Health: 10s
- Tests: 60s
- Validation: 10s

**ci (3-5 min):**
- Git check: 5s
- Stop: 10s
- Build: 2-3min (cached)
- Start: 30s
- Wait: 10s
- Health: 15s
- Tests: 60s
- Quality: 30s
- Resources: 5s

---

## ✅ Success Criteria

### quick-check passes when:
- ✅ API restarts successfully
- ✅ All 11 E2E tests pass
- ✅ No import errors

### full-check passes when:
- ✅ Docker build completes
- ✅ All services start
- ✅ All 11 E2E tests pass
- ✅ Python syntax valid

### ci passes when:
- ✅ Git status clean
- ✅ Docker build completes
- ✅ API health check passes
- ✅ UI responds
- ✅ All 11 E2E tests pass
- ✅ All imports work
- ✅ Resources within limits

---

## 🎉 Benefits

### Time Savings
- **Before:** 10+ commands manually
- **After:** 1 command automatically
- **Saved:** 5-10 minutes per iteration

### Error Catching
- Catch errors in seconds, not minutes
- Fail fast, fix fast
- No surprises in production

### Confidence
- ✅ All checks passed = Safe to push
- ✅ Reproducible results
- ✅ Same checks as CI/CD

---

## 📚 See Also

- `make help` - All available commands
- `make test-e2e` - Just run E2E tests
- `make status` - Check service status
- `make logs` - View service logs
