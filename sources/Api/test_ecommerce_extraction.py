#!/usr/bin/env python3
"""
Test script for C4 extraction on e-commerce-microservices-sample repo.
Runs extraction directly (no API required) and saves/verifies JSON output.
"""
import json
import sys
import tempfile
from pathlib import Path

# Add sources/Api to path (parent of app/)
api_root = Path(__file__).resolve().parent
sys.path.insert(0, str(api_root))

GITHUB_URL = "https://github.com/venkataravuri/e-commerce-microservices-sample.git"


def run_extraction():
    """Run C4 extraction directly and return (c4_architecture, task_id)."""
    from app.services.code_extraction.c4_extractor import C4ArchitectureExtractor
    from app.services.service_extraction.github_downloader import GitHubDownloader

    print(f"📥 Cloning: {GITHUB_URL}")
    temp_dir = Path(tempfile.mkdtemp(prefix="c4_test_"))
    try:
        repo_path = GitHubDownloader.download_repository(
            GITHUB_URL,
            output_dir=temp_dir,
            use_git=True,
        )
        print(f"✅ Cloned to: {repo_path}")

        print("\n🔍 Running C4 extraction...")
        extractor = C4ArchitectureExtractor(repo_path=repo_path, llm_manager=None)
        c4_architecture = extractor.extract(max_components_per_domain=10)

        # Generate task_id for output
        import uuid
        task_id = str(uuid.uuid4())[:8]

        return c4_architecture, task_id
    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


def save_json(data, task_id):
    """Save C4 architecture to JSON file."""
    api_root = Path(__file__).resolve().parent
    output_dir = api_root / "sources" / "data" / "c4_extractions"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{task_id}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    print(f"\n💾 Saved to: {output_file}")
    return output_file


def verify_extraction(data):
    """Verify all expected fields are present in extraction output."""
    print("\n" + "=" * 60)
    print("📋 EXTRACTION VERIFICATION REPORT")
    print("=" * 60)

    system = data.get("system_context", {})
    required_context_fields = [
        "name",
        "purpose",
        "owner_team",
        "business_domain",
        "criticality",
        "data_class",
        "status",
        "active_experts",
        "compliance",
        "external_dependencies",
        "languages",
        "frameworks",
        "repository_url",
        "git",
    ]

    print("\n📊 System Context (Level 1):")
    for field in required_context_fields:
        val = system.get(field)
        present = "✅" if val is not None else "⚠️"
        if isinstance(val, list):
            display = f"[{len(val)} items]"
        elif isinstance(val, dict):
            display = "{...}"
        else:
            display = str(val)[:60] + "..." if val and len(str(val)) > 60 else val
        print(f"  {present} {field}: {display}")

    # New Context Enhancement fields
    print("\n📊 Context Enhancement (7 Service Model):")
    for key in ["status", "status_evidence", "active_experts", "compliance", "owner_contributors", "owner_contributor_stats", "contributor_count"]:
        val = system.get(key)
        present = "✅" if val is not None else "⚠️"
        if isinstance(val, dict):
            display = "{...}"
        elif isinstance(val, list):
            display = f"[{len(val)} items]"
        else:
            display = str(val)[:50] + "..." if val is not None and len(str(val)) > 50 else val
        print(f"  {present} {key}: {display}")

    # Git metrics
    git = system.get("git", {})
    print("\n📊 Git Metrics:")
    for key in ["top_contributors", "commits_30d", "commits_90d", "last_commit_date"]:
        val = git.get(key)
        present = "✅" if val is not None else "⚠️"
        print(f"  {present} {key}: {val}")

    # Containers & Components
    containers = data.get("containers", [])
    components = data.get("components", [])
    print(f"\n📦 Containers: {len(containers)}")
    for c in containers[:5]:
        print(f"  - {c.get('name', '?')} ({c.get('technology', '?')})")
    if len(containers) > 5:
        print(f"  ... and {len(containers) - 5} more")

    print(f"\n🔌 Components: {len(components)}")
    for c in components[:5]:
        print(f"  - {c.get('name', '?')} ({c.get('endpoint_method', '?')} {c.get('endpoint_path', '?')})")
    if len(components) > 5:
        print(f"  ... and {len(components) - 5} more")

    # External deps
    deps = system.get("external_dependencies", [])
    print(f"\n🔗 External Dependencies: {len(deps)}")
    for d in deps:
        print(f"  - {d.get('name')} ({d.get('type')}) - {d.get('detected_from', '')}")

    # Relationships
    rels = data.get("relationships", {})
    context_rels = rels.get("context", [])
    print(f"\n🔗 Context Relationships: {len(context_rels)}")
    for r in context_rels[:5]:
        print(f"  - {r.get('source')} -> {r.get('destination')} ({r.get('relationship_type')})")

    print("\n" + "=" * 60)


def main():
    print("=" * 60)
    print("C4 EXTRACTION TEST - e-commerce-microservices-sample")
    print("=" * 60)

    try:
        c4_architecture, task_id = run_extraction()
    except Exception as e:
        print(f"\n❌ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    output_file = save_json(c4_architecture, task_id)
    verify_extraction(c4_architecture)

    # Also save to test result location
    result_path = Path(__file__).parent / "test_extraction_result.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(c4_architecture, f, indent=2, default=str, ensure_ascii=False)
    print(f"\n💾 Full output also saved to: {result_path}")
    print("\n✅ Test completed successfully!")


if __name__ == "__main__":
    main()
