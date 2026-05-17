"""Print a human-readable summary of containers from a c4_architecture.json.

Usage:
    docker compose exec api python scripts/summarize_c4_containers.py [path/to/c4_architecture.json]

Defaults to /app/c4_architecture.json.
"""

import json
import sys
from pathlib import Path


def _trim(value, n=60):
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= n else s[: n - 1] + "…"


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/app/c4_architecture.json")
    if not path.is_file():
        sys.exit(f"not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    containers = data.get("containers", [])
    relationships = data.get("container_relationships") or data.get("relationships") or []

    print(f"=== {path} ===")
    print(f"containers: {len(containers)}")
    print(f"relationships: {len(relationships)}")

    print()
    header = f"{'NAME':<35} {'TYPE':<22} {'TECH':<22} {'VERDICT':<10} {'CONF':<5} REASON"
    print(header)
    print("-" * len(header))

    def _sort_key(c):
        verdict = c.get("llm_verdict") or "zzz"
        return (verdict, c.get("name") or "")

    for c in sorted(containers, key=_sort_key):
        name = _trim(c.get("name"), 35)
        ctype = _trim(c.get("container_type"), 22)
        tech = _trim(c.get("technology"), 22)
        verdict = _trim(c.get("llm_verdict"), 10)
        conf = c.get("llm_confidence")
        conf_s = f"{conf:.2f}" if isinstance(conf, (int, float)) else "-"
        reason = _trim(c.get("llm_notes") or c.get("description") or "", 80)
        flag = c.get("sanity_flag")
        if flag and flag.get("verdict") == "false_positive":
            verdict = (verdict or "") + "*"
            reason = f"[sanity-fp] {flag.get('reason', '')} | {reason}"
        print(f"{name:<35} {ctype:<22} {tech:<22} {verdict:<10} {conf_s:<5} {reason}")


if __name__ == "__main__":
    main()
