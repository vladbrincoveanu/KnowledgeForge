#!/usr/bin/env bash
# superpowers-brainstorm-auto.sh
# Runs ui-ux-pro-max design system search when UI context is detected.
# Called by the brainstorming skill preamble.

set -e

UI_KEYWORDS="ui|ux|component|layout|button|color|typography|palette|font|spacing|accessibility|tooltip|panel|sidebar|graph|visual|design|style|professional|enterprise|dashboard|mockup|wireframe|prototype|interface|frontend"

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# Check if stdin or args contain UI keywords
input_text=$(cat "${1:-/dev/stdin}" 2>/dev/null || echo "")

if echo "$input_text" | grep -iqE "$UI_KEYWORDS"; then
  echo "[superpowers] UI context detected — running ui-ux-pro-max..."

  cd "$PROJECT_ROOT"

  # Run design system search and persist
  python3 "$SKILL_DIR/ui-ux-pro-max/scripts/search.py" \
    "enterprise dashboard architecture visualization" \
    --design-system \
    --persist \
    -p "KnowledgeForge" \
    -f markdown \
    2>/dev/null || true

  echo "[superpowers] Design system updated at design-system/MASTER.md"
fi
