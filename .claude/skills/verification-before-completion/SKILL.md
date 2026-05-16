---
name: verification-before-completion
description: Use when about to claim work is complete, fixed, or passing, before committing or creating PRs. Override of superpowers:verification-before-completion with feedback step.
---

# Verification Before Completion

**Override note:** This skill extends the Superpowers verification-before-completion skill with a feedback-writing step after verification passes.

---

## Verifying Configuration Changes

When testing changes to configuration, providers, feature flags, or environment:

**Don't just verify the operation succeeded. Verify the output reflects the intended change.**

### Common Failure Pattern

Operation succeeds because *some* valid config exists, but it's not the config you intended to test.

### Examples

| Change | Insufficient | Required |
|--------|-------------|----------|
| Switch LLM provider | Status 200 | Response contains expected model name |
| Enable feature flag | No errors | Feature behavior actually active |
| Change environment | Deploy succeeds | Logs/vars reference new environment |
| Set credentials | Auth succeeds | Authenticated user/context is correct |

### Gate Function

```
BEFORE claiming configuration change works:

1. IDENTIFY: What should be DIFFERENT after this change?
2. LOCATE: Where is that difference observable?
   - Response field (model name, user ID)
   - Log line (environment, provider)
   - Behavior (feature active/inactive)
3. RUN: Command that shows the observable difference
4. VERIFY: Output contains expected difference
5. ONLY THEN: Claim configuration change works

Red flags:
  - "Request succeeded" without checking content
  - Checking status code but not response body
  - Verifying no errors but not positive confirmation
```

**Why this works:** Forces verification of INTENT, not just operation success.

---

## Mock-Interface Drift Anti-Pattern

When writing tests, mocks must derive from interfaces, not from implementation.

### The Violation

```typescript
// Interface defines close()
interface PlatformAdapter {
  close(): Promise<void>;
}

// Code (BUGGY) calls cleanup()
await adapter.cleanup();

// Mock (MATCHES BUG) defines cleanup()
const mock = {
  cleanup: vi.fn().mockResolvedValue(undefined),  // Wrong!
};
// Tests pass but runtime crashes: "adapter.cleanup is not a function"
```

### Why Tests Pass But Code Crashes

Mock encodes the bug. TypeScript can't catch inline mocks with wrong method names.

### Gate Function

```
BEFORE writing any mock:

1. FIND: The interface/type definition for the dependency
2. READ: The interface file
3. LIST: Methods defined in the interface
4. MOCK: ONLY those methods with EXACTLY those names
5. DO NOT: Look at what your code calls

IF test fails because code calls something not in mock:
  GOOD - The test found a bug in your code
  Fix the code to call the correct interface method, NOT the mock
```

### Detection

When you see runtime error "X is not a function" but tests pass:
1. Check if X is mocked
2. Compare mock methods to interface methods
3. Look for method name mismatches

---

## Feedback Step (added by override)

After verification passes and before claiming completion:

### Write verification feedback

```bash
FEEDBACK_FILE=~/.claude/memory/feedback/verification-$(date +%Y-%m-%d).md
cat > "$FEEDBACK_FILE" << 'FEEDBACK_EOF'
---
name: verification-feedback-$(date +%Y-%m-%d)
type: feedback
---

## Verification Feedback

**Session:** $(pwd | xargs basename)
**Date:** $(date +%Y-%m-%d)
**Outcome:** passed

### What worked
- <note on what verification approach worked well>

### What didn't work
- <note on what was flaky or unclear>

### Next time try
- <suggestion for improving verification>

### Energy level (1-5)
<1-5 rating>
FEEDBACK_EOF
```

---

## Original verification-before-completion Skill (preserved)

## Overview

Claiming work is complete without verification is dishonesty, not efficiency.

**Core principle:** Evidence before claims, always.

**Violating the letter of this rule is violating the spirit of this rule.**

## The Iron Law

NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE

If you haven't run the verification command in this message, you cannot claim it passes.

## The Gate Function

BEFORE claiming any status or expressing satisfaction:

1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. ONLY THEN: Make the claim

Skip any step = lying, not verifying

## Refactoring Gate (Anti-Bloat)

After tests pass, run the refactoring gate BEFORE claiming completion.

**Thresholds:**

| Check | Threshold | Action |
|-------|-----------|--------|
| Module size | > 300 lines | Flag for mandatory split |
| Function complexity | > 3 responsibilities | Flag for refactor |
| DRY — same file | Repeated logic | Auto-fix |
| DRY — same module dir | Repeated logic | Auto-fix |
| DRY — cross-module/domain | Repeated logic | Flag for review only |
| Dead code | Imported but unused | Auto-remove |

**DRY Auto-fix scope rules:**
- **Same file** → auto-extract, inline, deduplicate
- **Same module directory** → auto-extract, inline, deduplicate
- **Different module/domain** → flag with location report, never auto-fix

**Behavior when issues found:**
1. Auto-fix if the fix is mechanical (extract method, remove dead import, inline simple duplication)
2. Flag for review if judgment required (cross-domain duplication, large module split)
3. **Completion blocked** until all flagged issues resolved

## Common Failures

| Claim | Requires | Not Sufficient |
|-------|----------|----------------|
| Tests pass | Test command output: 0 failures | Previous run, "should pass" |
| Linter clean | Linter output: 0 errors | Partial check, extrapolation |
| Build succeeds | Build command: exit 0 | Linter passing, logs look good |
| Bug fixed | Test original symptom: passes | Code changed, assumed fixed |
| Regression test works | Red-green cycle verified | Test passes once |
| Agent completed | VCS diff shows changes | Agent reports "success" |
| Requirements met | Line-by-line checklist | Tests passing |

## Red Flags - STOP

- Using "should", "probably", "seems to"
- Expressing satisfaction before verification ("Great!", "Perfect!", "Done!", etc.)
- About to commit/push/PR without verification
- Trusting agent success reports
- Relying on partial verification
- Thinking "just this once"
- Tired and wanting work over
- **ANY wording implying success without having run verification**

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "Should work now" | RUN the verification |
| "I'm confident" | Confidence ≠ evidence |
| "Just this once" | No exceptions |
| "Linter passed" | Linter ≠ compiler |
| "Agent said success" | Verify independently |
| "I'm tired" | Exhaustion ≠ excuse |
| "Partial check is enough" | Partial proves nothing |
| "Different words so rule doesn't apply" | Spirit over letter |

## Key Patterns

**Tests:**
✅ [Run test command] [See: 34/34 pass] "All tests pass"
❌ "Should pass now" / "Looks correct"

**Regression tests (TDD Red-Green):**
✅ Write → Run (pass) → Revert fix → Run (MUST FAIL) → Restore → Run (pass)
❌ "I've written a regression test" (without red-green verification)

**Build:**
✅ [Run build] [See: exit 0] "Build passes"
❌ "Linter passed" (linter doesn't check compilation)

**Requirements:**
✅ Re-read plan → Create checklist → Verify each → Report gaps or completion
❌ "Tests pass, phase complete"

**Agent delegation:**
✅ Agent reports success → Check VCS diff → Verify changes → Report actual state
❌ Trust agent report

## Why This Matters

From 24 failure memories:
- your human partner said "I don't believe you" - trust broken
- Undefined functions shipped - would crash
- Missing requirements shipped - incomplete features
- Time wasted on false completion → redirect → rework
- Violates: "Honesty is a core value. If you lie, you'll be replaced."

## When To Apply

**ALWAYS before:**
- ANY variation of success/completion claims
- ANY expression of satisfaction
- ANY positive statement about work state
- Committing, PR creation, task completion
- Moving to next task
- Delegating to agents

**Rule applies to:**
- Exact phrases
- Paraphrases and synonyms
- Implications of success
- ANY communication suggesting completion/correctness

## The Bottom Line

**No shortcuts for verification.**

Run the command. Read the output. THEN claim the result.

This is non-negotiable.
