"""Diagnose what each container detector finds for a given repo path.

Runs every detector standalone (no LLM, no Docker), prints what each one
emits, and the merged final candidate set BEFORE any LLM enrichment. Use
this to triangulate where the container layer is losing fidelity:
detection coverage vs LLM enrichment.

Usage:
    python scripts/diagnose_container_detection.py <path-to-repo>
"""

import sys
from pathlib import Path

# Make app/ importable when run from sources/Api/
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from app.services.c4.containers.compose_detector import ComposeDetector
from app.services.c4.containers.helm_detector import HelmDetector
from app.services.c4.containers.kubernetes_detector import KubernetesDetector
from app.services.c4.containers.structure_detector import StructureDetector
from app.services.c4.containers.terraform_detector import TerraformDetector
from app.services.c4.containers.container_manager import ContainerManager


def _row(name, ctype, tech, path, source):
    return f"  {source:<11} {name:<35} {ctype:<25} {tech:<22} {path}"


def _run_detector(label, detector, source):
    can = detector.can_detect()
    print(f"\n--- {label}  (can_detect={can}) ---")
    if not can:
        return []
    try:
        results = detector.detect() or []
    except Exception as exc:
        print(f"  ERROR: {exc}")
        return []
    print(f"  found: {len(results)}")
    for c in results:
        print(_row(
            (c.get("name") or "")[:35],
            (c.get("container_type") or "")[:25],
            (c.get("technology") or "")[:22],
            c.get("path") or "",
            source,
        ))
    return results


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: diagnose_container_detection.py <repo-path>")
    repo = Path(sys.argv[1]).resolve()
    if not repo.is_dir():
        sys.exit(f"not a directory: {repo}")

    print(f"=== diagnostic for {repo} ===")

    # Run each detector independently
    structure = _run_detector(
        "StructureDetector", StructureDetector(repo), "structure",
    )
    compose = _run_detector(
        "ComposeDetector", ComposeDetector(repo), "compose",
    )
    helm = _run_detector(
        "HelmDetector", HelmDetector(repo), "helm",
    )
    k8s = _run_detector(
        "KubernetesDetector", KubernetesDetector(repo), "k8s",
    )
    terraform = _run_detector(
        "TerraformDetector", TerraformDetector(repo), "terraform",
    )

    # Run the manager to get the merged candidate set (still no LLM)
    print("\n--- ContainerManager.detect_all_containers() (merged, pre-LLM) ---")
    cm = ContainerManager(repo, llm_manager=None)
    merged = cm.detect_all_containers()
    print(f"  merged total: {len(merged)}")
    header = f"  {'NAME':<35} {'TYPE':<25} {'TECH':<22} PATH"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for name, c in sorted(merged.items()):
        print(f"  {name[:35]:<35} {(c.get('container_type') or '')[:25]:<25} "
              f"{(c.get('technology') or '')[:22]:<22} {c.get('path') or ''}")

    print(f"\n=== summary ===")
    print(f"  structure:  {len(structure):>3}")
    print(f"  compose:    {len(compose):>3}")
    print(f"  helm:       {len(helm):>3}")
    print(f"  k8s:        {len(k8s):>3}")
    print(f"  terraform:  {len(terraform):>3}")
    print(f"  ----------------")
    print(f"  raw sum:    {len(structure)+len(compose)+len(helm)+len(k8s)+len(terraform):>3}")
    print(f"  merged:     {len(merged):>3}  (after dedup/merge)")


if __name__ == "__main__":
    main()
