---
name: multi-architect
description: Launch a parallel agent team with 1 Leader + 1 Business Analyst + N Software Architects. Use when user wants multi-perspective architectural analysis, wants to run multiple architects in parallel, or asks for team-based code review.
---

# Multi-Architect Team

Launch a parallel agent team to analyze a task from multiple architectural perspectives.

## Team Structure

```
┌─────────────────────────────────────┐
│              LEADER                 │
│   (Your main interaction point)     │
└─────────────────────────────────────┘
          │                    │
          ▼                    ▼
┌──────────────────┐   ┌──────────────────────┐
│  BUSINESS        │   │   ARCHITECT TEAM     │
│  ANALYST         │   │   (Parallel Workers) │
│                  │   │   - Architect A     │
│  - Requirements  │   │   - Architect B     │
│  - Scope         │   │   - Architect C     │
│  - Prioritization│   │   ...              │
└──────────────────┘   └──────────────────────┘
```

## Workflow

1. **Leader** (you) - Orchestrates, coordinates, synthesizes
2. **Business Analyst** - Defines scope, priorities, success criteria first
3. **Architects** (run in parallel) - Deep technical analysis of different areas

## How to Expand the Prompt

When user says `/ma [TASK]`, expand to:

```
Create a parallel agent team for [TASK]:

**LEADER** (you): Orchestrate the entire task. Coordinate between business analyst and architects. Synthesize findings into a unified plan. You're the single point of contact - all architects report to you.

**BUSINESS ANALYST**: Analyze requirements for [TASK]. Define scope, success criteria, and prioritize by business value. Ask: What problem are we solving? What's the ROI? What constraints exist?

**ARCHITECT TEAM** (run these in PARALLEL after BA defines scope):
- Architect A: [specific area - e.g., "database layer", "API surface", "frontend components"]
- Architect B: [different area]
- Architect C: [different area]

Each architect should deeply analyze their area, identify issues, and propose solutions.
```

## Key Principles

| Role | Responsibility | When to Call |
|------|---------------|--------------|
| Leader | Orchestration, synthesis | Always - your main interaction |
| Business Analyst | Requirements, scope, priorities | At start of new analysis |
| Architects | Deep technical analysis | In parallel after BA defines scope |

## Example Usage

**User input:**
```
/ma Analyze the React frontend for component patterns and state management
```

**Expand to full prompt and execute:**
```
Create a parallel agent team for analyzing the React frontend for component patterns and state management:

LEADER: ...
BUSINESS ANALYST: ...
ARCHITECT TEAM (parallel):
- Architect A: Review component structure and reusability
- Architect B: Review state management (useReducer, context, hooks)
- Architect C: Review performance and rendering patterns
```

## Related Skills
- **agent-designer** - For designing the multi-agent team structure and communication patterns
- **orchestration** - For coordination patterns and phase handoffs
- **self-improving-agent** - For curating architectural decisions into project memory
- **pr-review-expert** - For detailed PR analysis with blast radius

## Tips

- Always call Business Analyst FIRST to define scope
- Run all architects in PARALLEL (use Agent tool with subagent_type)
- Synthesize findings into actionable recommendations
- Keep architects focused on different areas to avoid duplication
