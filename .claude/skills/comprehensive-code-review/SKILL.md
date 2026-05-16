---
name: comprehensive-code-review
description: Use when implementing features, fixing bugs, or doing code review — covers hallucinations, workflows, coverage, simplifications, and full code quality.
---

# Comprehensive Code Review

## Overview

Systematic multi-phase code quality review. Catches hallucination errors, missing tests, coverage gaps, dead code, and logic flaws before they reach production.

## Phases

```
PHASE 1: Pre-Commit Review (before git add)
PHASE 2: Test Verification (run tests)
PHASE 3: Simplify (cleanup pass)
PHASE 4: Final Review (commit-ready check)
```

---

## Phase 1: Pre-Commit Review

**Run BEFORE staging changes.**

### 1a. Hallucination Check
Common hallucination patterns:
- Function calls that don't exist in imported modules
- Method names that don't match actual API
- Config/environment variables that don't exist
- File paths that don't exist in the codebase
- Import paths that don't resolve

```bash
# Check for commonly hallucinated patterns
grep -rn "import" changed_files.py | head -20
grep -rn "from " changed_files.py | head -20
```

### 1b. Workflow Review
Verify new code follows existing patterns:
- Async/await used correctly (not blocking calls inside async functions)
- Error handling present (no bare `except: pass`)
- Logging at appropriate level (DEBUG for development, WARNING for production issues)
- No hardcoded credentials or API keys

### 1c. Dead Code Detection
- Unused imports
- Unused variables
- Duplicate function implementations
- Commented-out code that should be deleted

---

## Phase 2: Test Verification

**Run AFTER changes are staged.**

### 2a. Integration Test Coverage
Must have integration tests for:
- New public functions
- Cross-module interactions
- I/O operations (file, network, database)
- Error/edge case paths

### 2b. Run Tests
```bash
# Run relevant tests
python -m pytest tests/ -v --tb=short

# Run with coverage for new code
python -m pytest tests/ --cov=. --cov-report=term-missing
```

### 2c. Fix Test Failures
- Unit tests mocking wrong interfaces → update mocks
- Missing mocks → add them
- Integration tests failing → fix the integration, not the test
- Pre-existing failures → note and don't block (document them)

---

## Phase 3: Simplify

**Run regardless of whether tests pass.**

### 3a. Code Reuse Check
- Duplicate functions → consolidate
- Inline logic that duplicates existing utilities → use the utility
- Near-duplicate code blocks → unify with shared abstraction

### 3b. Dead Code Removal
- Functions never called → remove
- Imports unused after changes → remove
- Commented-out code → delete

### 3c. Import Cleanup
- Group: stdlib → third-party → local
- Alphabetical within groups
- No unused imports

### 3d. Simplification Fixes
Apply fixes directly:
- Redundant two-pass loops → single pass
- Unnecessary existence checks → operate and handle error
- Blocking calls in async context → wrap in asyncio.to_thread()
- Inline imports inside functions → move to module level

---

## Phase 4: Final Review

**Before commit.**

### 4a. Logic Correctness
- Verify the change actually solves the stated problem
- Check edge cases (empty input, null, max values)
- Verify error paths work correctly

### 4b. Blast Radius Check
For changes to shared code:
- What files import this module?
- What tests cover this code path?
- Are there any breaking changes?

### 4c. Commit-Ready Checklist
- [ ] Tests pass (or pre-existing failures documented)
- [ ] No debug print statements
- [ ] No TODO comments left in
- [ ] Commit message describes WHY, not just WHAT
- [ ] No uncommitted changes beyond the fix

---

## Quick Reference

| Issue | Fix |
|-------|-----|
| Hallucinated function call | Check API docs, verify import exists |
| Missing integration test | Write test before finishing |
| Bare `except: pass` | Log at DEBUG or return error |
| Blocking call in async | Wrap: `await asyncio.to_thread(blocking_func)` |
| Duplicate code | Extract to shared function |
| Unused import | Remove it |
| Pre-existing test failure | Document, don't block |

## Common Hallucination Patterns

1. **Module/function doesn't exist**: ImportError or AttributeError at runtime
2. **Wrong API shape**: `requests.get()` called like `requests.post()`, wrong return type used
3. **Non-existent env var**: `os.environ["API_KEY"]` but API_KEY not in .env.example
4. **Wrong file path**: Import from `core.utils` but file is `core/helpers.py`
5. **Mock mismatch**: Test patches `module.func` but real code calls `module.Class.func`
6. **Config drift**: Code uses `config.API_URL` but config has `API_URL_2`

## Testing Integration Test Coverage

Must cover:
- **Happy path**: Normal operation works
- **Error path**: Failures are caught and handled
- **Edge cases**: Empty, null, max values
- **Integration**: Cross-module calls work

Nice to have:
- Performance assertions
- Concurrency safety

## Red Flags — STOP

- Tests not written before/during feature implementation
- Pre-existing test failures ignored without documentation
- Dead code left "just in case"
- Magic numbers without constants
- Stringly-typed enums
