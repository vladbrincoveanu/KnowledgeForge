---
name: brainstorming
description: "You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation. Override of superpowers:brainstorming with feedback step."
---

# Brainstorming Ideas Into Designs

**Override note:** This skill extends the Superpowers brainstorming skill with a feedback-writing step after design approval. The base skill content is preserved below.

---

## Feedback Step (added by override)

After the user approves the design (after Step 8: "User reviews spec?" with approved), before transitioning to writing-plans:

### Write brainstorming feedback

Write a feedback file to `~/.claude/memory/feedback/brainstorming-$(date +%Y-%m-%d).md`:

```bash
FEEDBACK_FILE=~/.claude/memory/feedback/brainstorming-$(date +%Y-%m-%d).md
cat > "$FEEDBACK_FILE" << 'FEEDBACK_EOF'
---
name: brainstorming-feedback-$(date +%Y-%m-%d)
type: feedback
---

## Brainstorming Feedback

**Session:** $(pwd | xargs basename)
**Date:** $(date +%Y-%m-%d)
**Outcome:** approved

### What worked
- <brief note on what went well in this brainstorming session>

### What didn't work
- <brief note on what was unclear or took too long>

### Next time try
- <suggestion for how to improve the next brainstorming session>

### Energy level (1-5)
<1-5 rating>
FEEDBACK_EOF
```

### Write missed edge cases

If bugs or edge cases were discovered during implementation, capture them:

```bash
EDGE_CASE_FILE=~/.claude/memory/edge-cases/$(date +%Y-%m-%d)-$(pwd | xargs basename | tr ' ' '-').md
cat > "$EDGE_CASE_FILE" << 'EOF'
---
name: edge-case-$(date +%Y-%m-%d)
type: edge-case
tags: [<relevant tags>]
---

## Edge Case: <brief descriptive name>

**When:** <trigger condition>

**Expected behavior:** <what should happen>

**Actual behavior (if bug):** <what actually happened>

**Session:** <session or project>
**Date:** $(date +%Y-%m-%d)
EOF
```

Then announce: "Feedback written. Transitioning to writing-plans."

---

## Original Brainstorming Skill (preserved)

Help turn ideas into fully formed designs and specs through natural collaborative dialogue.

Start by understanding the current project context, then ask questions one at a time to refine the idea. Once you understand what you're building, present the design and get user approval.

<HARD-GATE>
Do NOT invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have presented a design and the user has approved it. This applies to EVERY project regardless of perceived simplicity.
</HARD-GATE>

## Anti-Pattern: "This Is Too Simple To Need A Design"

Every project goes through this process. A todo list, a single-function utility, a config change — all of them. "Simple" projects are where unexamined assumptions cause the most wasted work. The design can be short (a few sentences for truly simple projects), but you MUST present it and get approval.

## Checklist

You MUST create a task for each of these items and complete them in order:

0. **Pre-flight grill-me** — invoke grill-me skill to challenge assumptions BEFORE starting
0.5. **Read relevant edge cases** — scan `~/.claude/memory/edge-cases/` for patterns relevant to this topic and surface them
1. **Explore project context** — check files, docs, recent commits

## Edge Cases Reading (Step 0.5)

Before exploring project context, scan for relevant edge cases:

```bash
ls ~/.claude/memory/edge-cases/*.md 2>/dev/null | head -20
```

Read any edge case files relevant to the topic (e.g., if building a web app, read `auth-edge-cases.md`).

Surface relevant edge cases to the user:
> "From past bugs, some edge cases to consider: [list edge cases]. Which of these apply to this feature?"

**This builds institutional memory — bugs from the past become considerations for the future.**
2. **Offer visual companion** (if topic will involve visual questions) — this is its own message, not combined with a clarifying question. See the Visual Companion section below.
3. **Ask clarifying questions** — one at a time, understand purpose/constraints/success criteria
4. **Propose 2-3 approaches** — with trade-offs and your recommendation
5. **Present design** — in sections scaled to their complexity, get user approval after each section
6. **Design grill-me** — invoke grill-me skill AFTER user approves design but BEFORE writing design doc
7. **Write design doc** — save to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` and commit
8. **Spec self-review** — quick inline check for placeholders, contradictions, ambiguity, scope (see below)
9. **User reviews written spec** — ask user to review the spec file before proceeding
10. **Transition to implementation** — invoke writing-plans skill to create implementation plan

## Process Flow

```dot
digraph brainstorming {
    "Pre-flight grill-me" [shape=box];
    "Read relevant edge cases" [shape=box];
    "Explore project context" [shape=box];
    "Visual questions ahead?" [shape=diamond];
    "Offer Visual Companion\n(own message, no other content)" [shape=box];
    "Ask clarifying questions" [shape=box];
    "Propose 2-3 approaches" [shape=box];
    "Present design sections" [shape=box];
    "User approves design?" [shape=diamond];
    "Design grill-me" [shape=box];
    "Write design doc" [shape=box];
    "Spec self-review\n(fix inline)" [shape=box];
    "User reviews spec?" [shape=diamond];
    "Write feedback" [shape=box];
    "Invoke writing-plans skill" [shape=doublecircle];

    "Pre-flight grill-me" -> "Read relevant edge cases";
    "Read relevant edge cases" -> "Explore project context";
    "Explore project context" -> "Visual questions ahead?";
    "Visual questions ahead?" -> "Offer Visual Companion\n(own message, no other content)" [label="yes"];
    "Visual questions ahead?" -> "Ask clarifying questions" [label="no"];
    "Offer Visual Companion\n(own message, no other content)" -> "Ask clarifying questions";
    "Ask clarifying questions" -> "Propose 2-3 approaches";
    "Propose 2-3 approaches" -> "Present design sections";
    "Present design sections" -> "User approves design?";
    "User approves design?" -> "Present design sections" [label="no, revise"];
    "User approves design?" -> "Design grill-me" [label="yes"];
    "Design grill-me" -> "Write design doc";
    "Write design doc" -> "Spec self-review\n(fix inline)";
    "Spec self-review\n(fix inline)" -> "User reviews spec?";
    "User reviews spec?" -> "Write design doc" [label="changes requested"];
    "User reviews spec?" -> "Write feedback" [label="approved"];
    "Write feedback" -> "Invoke writing-plans skill";
}
```

**The terminal state is writing feedback, then invoking writing-plans.** Do NOT invoke any other implementation skill. The ONLY skill you invoke after brainstorming is writing-plans.

## The Process

**Understanding the idea:**

- Check out the current project state first (files, docs, recent commits)
- Before asking detailed questions, assess scope: if the request describes multiple independent subsystems (e.g., "build a platform with chat, file storage, billing, and analytics"), flag this immediately. Don't spend questions refining details of a project that needs to be decomposed first.
- If the project is too large for a single spec, help the user decompose into sub-projects: what are the independent pieces, how do they relate, what order should they be built? Then brainstorm the first sub-project through the normal design flow. Each sub-project gets its own spec → plan → implementation cycle.
- For appropriately-scoped projects, ask questions one at a time to refine the idea
- Prefer multiple choice questions when possible, but open-ended is fine too
- Only one question per message - if a topic needs more exploration, break it into multiple questions
- Focus on understanding: purpose, constraints, success criteria

**Exploring approaches:**

- Propose 2-3 different approaches with trade-offs
- Present options conversationally with your recommendation and reasoning
- Lead with your recommended option and explain why

**Presenting the design:**

- Once you believe you understand what you're building, present the design
- Scale each section to its complexity: a few sentences if straightforward, up to 200-300 words if nuanced
- Ask after each section whether it looks right so far
- Cover: architecture, components, data flow, error handling, testing
- Be ready to go back and clarify if something doesn't make sense

**Design for isolation and clarity:**

- Break the system into smaller units that each have one clear purpose, communicate through well-defined interfaces, and can be understood and tested independently
- For each unit, you should be able to answer: what does it do, how do you use it, and what does it depend on?
- Can someone understand what a unit does without reading its internals? Can you change the internals without breaking consumers? If not, the boundaries need work.
- Smaller, well-bounded units are also easier for you to work with - you reason better about code you can hold in context at once, and your edits are more reliable when files are focused. When a file grows large, that's often a signal that it's doing too much.

**Working in existing codebases:**

- Explore the current structure before proposing changes. Follow existing patterns.
- Where existing code has problems that affect the work (e.g., a file that's grown too large, unclear boundaries, tangled responsibilities), include targeted improvements as part of the design - the way a good developer improves code they're working in.
- Don't propose unrelated refactoring. Stay focused on what serves the current goal.

## After the Design

**Documentation:**

- Write the validated design (spec) to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
  - (User preferences for spec location override this default)
- Use elements-of-style:writing-clearly-and-concisely skill if available
- Commit the design document to git

**Spec Self-Review:**
After writing the spec document, look at it with fresh eyes:

1. **Placeholder scan:** Any "TBD", "TODO", incomplete sections, or vague requirements? Fix them.
2. **Internal consistency:** Do any sections contradict each other? Does the architecture match the feature descriptions?
3. **Scope check:** Is this focused enough for a single implementation plan, or does it need decomposition?
4. **Ambiguity check:** Could any requirement be interpreted two different ways? If so, pick one and make it explicit.

Fix any issues inline. No need to re-review — just fix and move on.

### Module Design Block Requirement

Every significant module in a spec MUST have a Module Design Block:

```markdown
### Module: <Name>
- **Responsibility:** <One sentence — what it does>
- **Interface:** <Inputs, outputs — what it communicates with>
- **Dependencies:** <What it depends on, if anything>
- **Size target:** <200 lines max, single responsibility — if it needs more, decompose>
```

**Enforcement:** A spec is NOT approved until all modules have this block filled out. Vague or oversized modules are sent back for clarification before proceeding.

**User Review Gate:**
After the spec review loop passes, ask the user to review the written spec before proceeding:

> "Spec written and committed to `<path>`. Please review it and let me know if you want to make any changes before we start writing out the implementation plan."

Wait for the user's response. If they request changes, make them and re-run the spec review loop. Only proceed once the user approves.

**Implementation:**

- Write feedback (see Feedback Step above)
- Invoke the writing-plans skill to create a detailed implementation plan
- Do NOT invoke any other skill. writing-plans is the next step.

## Key Principles

- **One question at a time** - Don't overwhelm with multiple questions
- **Multiple choice preferred** - Easier to answer than open-ended when possible
- **YAGNI ruthlessly** - Remove unnecessary features from all designs
- **Explore alternatives** - Always propose 2-3 approaches before settling
- **Incremental validation** - Present design, get approval before moving on
- **Be flexible** - Go back and clarify when something doesn't make sense

## Visual Companion

A browser-based companion for showing mockups, diagrams, and visual options during brainstorming. Available as a tool — not a mode. Accepting the companion means it's available for questions that benefit from visual treatment; it does NOT mean every question goes through the browser.

**Offering the companion:** When you anticipate that upcoming questions will involve visual content (mockups, layouts, diagrams), offer it once for consent:
> "Some of what we're working on might be easier to explain if I can show it to you in a web browser. I can put together mockups, diagrams, comparisons, and other visuals as we go. This feature is still new and can be token-intensive. Want to try it? (Requires opening a local URL)"

**This offer MUST be its own message.** Do not combine it with clarifying questions, context summaries, or any other content. The message should contain ONLY the offer above and nothing else. Wait for the user's response before continuing. If they decline, proceed with text-only brainstorming.

**Per-question decision:** Even after the user accepts, decide FOR EACH QUESTION whether to use the browser or the terminal. The test: **would the user understand this better by seeing it than reading it?**

- **Use the browser** for content that IS visual — mockups, wireframes, layout comparisons, architecture diagrams, side-by-side visual designs
- **Use the terminal** for content that is text — requirements questions, conceptual choices, tradeoff lists, A/B/C/D text options, scope decisions

A question about a UI topic is not automatically a visual question. "What does personality mean in this context?" is a conceptual question — use the terminal. "Which wizard layout works better?" is a visual question — use the browser.

If they agree to the companion, read the detailed guide before proceeding:
`skills/brainstorming/visual-companion.md`
