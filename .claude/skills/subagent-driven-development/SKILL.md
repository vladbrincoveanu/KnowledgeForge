---
name: subagent-driven-development
description: Use when executing implementation plans with independent tasks in the current session
---

# Subagent-Driven Development

**Override note:** This skill extends the Superpowers subagent-driven-development skill with Phase 2 improvements:
- Process hygiene for E2E tests
- Lean context option for pattern-based tasks
- Skills reading requirement for test subagents

---

## Process Hygiene for E2E Tests

When dispatching subagents that start services (servers, databases, message queues):

### Problem

Subagents are stateless - they don't know about processes started by previous subagents. Background processes persist and can interfere with later tests.

### Preferred Solution: Test Infrastructure

**Design test services to be self-cleaning:**

1. **Use docker-compose for test services:**
   - Services defined in docker-compose.yml with `restart: unless-stopped`
   - `docker-compose down` cleans up all services
   - No manual process management needed

2. **Use port 0 for dynamic port allocation:**
   - Let OS assign available port
   - No port conflict errors
   - Get port from container or stdout

3. **Use test fixtures with lifecycle management:**
   - Fixtures start services before tests
   - Fixtures stop services after tests
   - Automatic cleanup even on test failure

### Fallback: Prompt-based Cleanup

If infrastructure approach isn't available, include cleanup in prompt:

```
BEFORE starting any services:
1. Kill existing processes: pkill -f "<service-pattern>" 2>/dev/null || true
2. Wait for cleanup: sleep 1
3. Verify port free: lsof -i :<port> && echo "ERROR: Port still in use" || echo "Port free"

AFTER tests complete:
1. Kill the process you started
2. Verify cleanup: pgrep -f "<service-pattern>" || echo "Cleanup successful"
```

---

## Context Approaches

**Full Plan (default):**
Use when tasks are complex or have dependencies:
```
Read Task N from [plan-file] carefully.
```

**Lean Context (for independent pattern-based tasks):**
Use when task is standalone and follows an existing pattern:
```
You are implementing: [1-2 sentence task description]

File to modify: [exact path]
Pattern to follow: [reference to existing function/test]
What to implement: [specific requirement]
Verification: [exact command to run]

[Do NOT include full plan file]
```

**Use lean context when:**
- Task follows existing pattern (add similar test, implement similar feature)
- Task is self-contained (doesn't need context from other tasks)
- Pattern reference is sufficient (e.g., "follow TestE2E_FeatureOptionValidation")

**Use full plan when:**
- Task has dependencies on other tasks
- Requires understanding of overall architecture
- Complex logic that needs context

---

## Skills Reading for Test Subagents

BEFORE writing any tests, the implementer subagent should read relevant skills:

```
BEFORE writing any tests:

1. Read verification-before-completion skill:
   Focus on: Mock-Interface Drift Anti-Pattern

2. Apply gate functions when:
   - Writing mocks (must derive from interface, not implementation)
   - Adding methods to production classes
   - Mocking dependencies

This is NOT optional. Tests that violate anti-patterns will be rejected in review.
```

---

## Explicit File Reading for Code Reviewers

When dispatching code review subagents, ensure they read files before reviewing:

**Instruct subagent to:**
1. Read specific files that changed in the diff
2. Read files referenced by changes but not modified
3. DO NOT proceed with review until actual code is read

This prevents "file not found" review failures.

---

---

## Original subagent-driven-development Skill (preserved)

See superpowers reference: `skills/subagent-driven-development/SKILL.md`

Core workflow:
1. Read plan, extract all tasks with full text, create TodoWrite
2. Dispatch implementer subagent per task
3. Two-stage review: spec compliance then code quality
4. Mark task complete, repeat until done
5. Final code review, then use finishing-a-development-branch

### Allow Implementer to Fix Self-Identified Issues

If self-reflection identifies fixable issues:
1. Fix the issues
2. Re-run verification
3. Report: "Initial implementation + self-reflection fix"

Include in report:
- Self-reflection findings
- Whether fixes were applied
- Final verification results
