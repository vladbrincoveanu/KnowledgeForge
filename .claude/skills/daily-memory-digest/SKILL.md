---
name: daily-memory-digest
description: Scan accumulated skill feedback and update ~/.claude/CLAUDE.md with patterns. Run weekly or on-demand. Writes to CLAUDE.md only after user approval.
---

# Daily Memory Digest

Scan accumulated skill feedback files since the last digest, identify patterns in what worked/what didn't across sessions, and propose targeted updates to `~/.claude/CLAUDE.md`.

**Announce at start:** "I'm running the memory digest to consolidate recent skill feedback into CLAUDE.md."

## The Process

### Step 1: Read last digest date

Read `~/.claude/memory/metadata/last-digest-date` to get the ISO date string of the last digest run.

### Step 2: Scan feedback files

List all files in `~/.claude/memory/feedback/` that were modified since the last digest date.

Run:
```bash
find ~/.claude/memory/feedback/ -name "*.md" -type f -newer ~/.claude/memory/metadata/last-digest-date 2>/dev/null
```

If no files found:
```
No new feedback since last digest (1970-01-01). Nothing to do.
```
Exit gracefully.

### Step 3: Read all new feedback files

For each file found, read its contents and extract:
- Skill name
- Outcome
- "What worked" bullets
- "What didn't work" bullets
- "Next time try" bullets
- Energy level

### Step 4: Identify patterns

Group feedback by skill. For each skill, tally:
- Most common "what worked" patterns
- Most common "what didn't work" patterns
- Recurring "next time try" suggestions
- Average energy level

### Step 5: Generate CLAUDE.md delta

If patterns found, generate a diff that:
- Adds a new section "## Recent Skill Feedback Patterns" with summarized patterns
- Updates any existing feedback section with new observations
- Keeps existing CLAUDE.md content intact

Present the delta to the user as a diff:

```
## Proposed CLAUDE.md Update

Since last digest, N feedback files from: <skill list>

### Patterns identified:
- <skill>: <pattern summary>

Diff:
<full diff of proposed changes>

Approve these changes? (yes/no)
```

### Step 6: Apply or exit

**If user approves:**
Edit `~/.claude/CLAUDE.md` to apply the diff.

Then update the last-digest-date:
```bash
date +%Y-%m-%d > ~/.claude/memory/metadata/last-digest-date
```

Report: "CLAUDE.md updated. Last digest date reset to today."

**If user rejects:** Report "Digest skipped. Feedback files preserved for next cycle." and exit.

### Step 7: Commit

Since the digest modified `~/.claude/CLAUDE.md` (a file outside the current repo), do NOT commit. Just report the update is complete.

## Error Handling

| Failure | Handling |
|---------|----------|
| No feedback files since last digest | Exit gracefully with message |
| last-digest-date file missing | Treat as 1970-01-01, continue |
| Feedback file corrupted (empty/parse error) | Skip file, log warning, continue |
| User rejects delta | Exit, feedback preserved |
| Write to CLAUDE.md fails | Report error, do not update last-digest-date |
