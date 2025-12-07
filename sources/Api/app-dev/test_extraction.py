"""Test script for code extraction from monorepo."""

import sys
import json
from pathlib import Path

# Add app-dev to path
sys.path.insert(0, str(Path(__file__).parent))

from services.code_extraction.repository_scanner import RepositoryScanner


def test_monorepo_extraction():
    """Test extracting entities from the monorepo folder."""
    
    # Path to monorepo
    monorepo_path = Path(__file__).parent.parent.parent.parent / "monorepo"
    
    if not monorepo_path.exists():
        print(f"❌ Monorepo path not found: {monorepo_path}")
        return
    
    print(f"📂 Scanning repository: {monorepo_path}")
    print(f"   Absolute path: {monorepo_path.resolve()}")
    print()
    
    # Initialize scanner
    scanner = RepositoryScanner(
        repo_path=monorepo_path,
        max_file_size_mb=10.0
    )
    
    # Perform scan
    print("🔍 Starting scan...")
    result = scanner.scan(force_full=True)
    
    # Display results
    print("\n" + "="*80)
    print("📊 EXTRACTION RESULTS")
    print("="*80)
    
    print(f"\n📁 Repository: {result.repository.repo_name or result.repository.repo_path}")
    print(f"⏱️  Scan duration: {result.extraction_duration_seconds:.2f}s")
    print(f"📄 Files processed: {result.repository.total_files}")
    print(f"🔤 Languages detected: {', '.join([lang.value for lang in result.repository.languages_detected])}")
    
    print(f"\n📦 ENTITIES: {len(result.entities)}")
    
    # Group entities by type
    entities_by_type = {}
    for entity in result.entities:
        entity_type = entity.entity_type.value
        if entity_type not in entities_by_type:
            entities_by_type[entity_type] = []
        entities_by_type[entity_type].append(entity)
    
    for entity_type, entities in sorted(entities_by_type.items()):
        print(f"  - {entity_type}: {len(entities)}")
    
    print(f"\n🔗 RELATIONSHIPS: {len(result.relationships)}")
    
    # Group relationships by type
    rels_by_type = {}
    for rel in result.relationships:
        rel_type = rel.relationship_type.value
        if rel_type not in rels_by_type:
            rels_by_type[rel_type] = 0
        rels_by_type[rel_type] += 1
    
    for rel_type, count in sorted(rels_by_type.items()):
        print(f"  - {rel_type}: {count}")
    
    print(f"\n📚 DEPENDENCIES: {len(result.dependencies)}")
    
    # Group dependencies by language
    deps_by_lang = {}
    for dep in result.dependencies:
        lang = dep.language.value
        if lang not in deps_by_lang:
            deps_by_lang[lang] = []
        deps_by_lang[lang].append(dep)
    
    for lang, deps in sorted(deps_by_lang.items()):
        print(f"  - {lang}: {len(deps)} packages")
    
    # Show file type breakdown
    print(f"\n📂 FILE TYPE BREAKDOWN:")
    for source_type, count in sorted(result.repository.file_counts.items()):
        print(f"  - {source_type}: {count}")
    
    # Show some sample entities
    print(f"\n🔍 SAMPLE ENTITIES (first 10):")
    for i, entity in enumerate(result.entities[:10], 1):
        print(f"\n  {i}. {entity.name}")
        print(f"     Type: {entity.entity_type.value}")
        print(f"     Language: {entity.language.value}")
        print(f"     File: {entity.file_path}")
        if entity.line_start:
            print(f"     Line: {entity.line_start}")
    
    # Show errors and warnings
    if result.errors:
        print(f"\n⚠️  ERRORS ({len(result.errors)}):")
        for error in result.errors[:10]:
            print(f"  - {error}")
    
    if result.warnings:
        print(f"\n⚡ WARNINGS ({len(result.warnings)}):")
        for warning in result.warnings[:10]:
            print(f"  - {warning}")
    
    # Save results to JSON file for inspection
    output_file = Path(__file__).parent / "extraction_results.json"
    
    # Convert to serializable format
    results_dict = {
        "repository": {
            "path": result.repository.repo_path,
            "total_files": result.repository.total_files,
            "total_entities": result.repository.total_entities,
            "total_relationships": result.repository.total_relationships,
            "languages": [lang.value for lang in result.repository.languages_detected],
            "file_counts": result.repository.file_counts,
        },
        "entities": [
            {
                "id": e.id,
                "name": e.name,
                "type": e.entity_type.value,
                "language": e.language.value,
                "file_path": e.file_path,
                "line_start": e.line_start,
                "line_end": e.line_end,
            }
            for e in result.entities
        ],
        "relationships": [
            {
                "id": r.id,
                "source": r.source_entity_id,
                "target": r.target_entity_id,
                "type": r.relationship_type.value,
            }
            for r in result.relationships
        ],
        "dependencies": [
            {
                "name": d.name,
                "version": d.version,
                "language": d.language.value,
                "source_file": d.source_file,
            }
            for d in result.dependencies
        ],
        "stats": {
            "extraction_duration": result.extraction_duration_seconds,
            "errors": result.errors,
            "warnings": result.warnings,
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(results_dict, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")
    
    return result


def test_neo4j_connection():
    """Test Neo4j connection."""
    print("\n" + "="*80)
    print("🔌 TESTING NEO4J CONNECTION")
    print("="*80)
    
    try:
        from neo4j import GraphDatabase
        
        driver = GraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "password"),
            encrypted=False
        )
        
        driver.verify_connectivity()
        print("✅ Connected to Neo4j successfully!")
        
        # Test a simple query
        with driver.session(database="neo4j") as session:
            result = session.run("RETURN 1 as test")
            record = result.single()
            if record and record["test"] == 1:
                print("✅ Test query executed successfully!")
        
        driver.close()
        return True
            
    except Exception as e:
        print(f"❌ Error connecting to Neo4j: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🚀 KnowledgeForge Code Extraction Test")
    print("="*80)
    
    # Test Neo4j connection first
    neo4j_ok = test_neo4j_connection()
    
    # Run extraction test
    print()
    result = test_monorepo_extraction()
    
    print("\n" + "="*80)
    print("✨ Test completed!")
    print("="*80)
