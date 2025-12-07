"""End-to-end test: Extract code entities and store in Neo4j."""

import sys
import json
from pathlib import Path

# Add app-dev to path
sys.path.insert(0, str(Path(__file__).parent))

from services.code_extraction.repository_scanner import RepositoryScanner
from infrastructure.graph.code_entity_storage import CodeEntityNeo4jStorage


def main():
    """Run full extraction and storage pipeline."""
    
    print("="*80)
    print("🚀 CODE EXTRACTION & NEO4J STORAGE PIPELINE")
    print("="*80)
    
    # Configuration
    monorepo_path = Path(__file__).parent.parent.parent.parent / "monorepo"
    
    if not monorepo_path.exists():
        print(f"❌ Monorepo path not found: {monorepo_path}")
        return 1
    
    # Step 1: Extract entities
    print("\n📂 STEP 1: Extract Code Entities")
    print("-" * 80)
    print(f"Repository: {monorepo_path}")
    
    scanner = RepositoryScanner(
        repo_path=monorepo_path,
        max_file_size_mb=10.0
    )
    
    print("🔍 Scanning repository...")
    result = scanner.scan(force_full=True)
    
    print(f"✅ Extraction complete!")
    print(f"   - Entities: {len(result.entities)}")
    print(f"   - Relationships: {len(result.relationships)}")
    print(f"   - Dependencies: {len(result.dependencies)}")
    print(f"   - Duration: {result.extraction_duration_seconds:.2f}s")
    
    # Step 2: Connect to Neo4j
    print("\n🔌 STEP 2: Connect to Neo4j")
    print("-" * 80)
    
    storage = CodeEntityNeo4jStorage(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="password",
        database="neo4j",
        encrypted=False,
    )
    
    if not storage.connect():
        print("❌ Failed to connect to Neo4j")
        return 1
    
    print("✅ Connected to Neo4j")
    
    # Step 3: Create schema
    print("\n📋 STEP 3: Create Schema")
    print("-" * 80)
    
    try:
        storage.create_schema()
        print("✅ Schema created/verified")
    except Exception as e:
        print(f"⚠️  Schema creation warning: {e}")
    
    # Step 4: Store data
    print("\n💾 STEP 4: Store Entities and Relationships")
    print("-" * 80)
    
    print("Storing data in Neo4j...")
    stats = storage.store_extraction_result(result, clear_existing=True)
    
    print(f"✅ Storage complete!")
    print(f"   - Entities stored: {stats['entities_stored']}")
    print(f"   - Relationships stored: {stats['relationships_stored']}")
    print(f"   - Errors: {stats['errors']}")
    
    # Step 5: Verify data
    print("\n🔍 STEP 5: Verify Stored Data")
    print("-" * 80)
    
    db_stats = storage.get_statistics()
    
    print("\n📊 Entity Distribution:")
    for item in db_stats["entities_by_type"]:
        print(f"   - {item['type']}: {item['count']}")
    
    print("\n🔗 Relationship Distribution:")
    for item in db_stats["relationships_by_type"]:
        print(f"   - {item['type']}: {item['count']}")
    
    print("\n🔤 Language Distribution:")
    for item in db_stats["languages"]:
        print(f"   - {item['language']}: {item['count']}")
    
    print("\n📁 Top Files by Entity Count:")
    for item in db_stats["top_files"][:10]:
        print(f"   - {item['file']}: {item['count']} entities")
    
    # Step 6: Example queries
    print("\n🔍 STEP 6: Example Queries")
    print("-" * 80)
    
    # Query Python functions
    print("\n📝 Python Functions:")
    functions = storage.query_entities(
        entity_type="function",
        language="python",
        limit=5
    )
    for func in functions:
        print(f"   - {func['name']} in {func['file_path']}")
    
    # Query classes
    print("\n📦 Python Classes:")
    classes = storage.query_entities(
        entity_type="class",
        language="python",
        limit=5
    )
    for cls in classes:
        print(f"   - {cls['name']} in {cls['file_path']}")
    
    # Get relationships for a specific entity
    if result.entities:
        sample_entity = result.entities[0]
        print(f"\n🔗 Relationships for '{sample_entity.name}':")
        relationships = storage.get_entity_relationships(sample_entity.id)
        print(f"   - Outgoing: {len(relationships['outgoing'])}")
        print(f"   - Incoming: {len(relationships['incoming'])}")
    
    # Step 7: Generate Cypher queries for exploration
    print("\n📝 STEP 7: Useful Cypher Queries")
    print("-" * 80)
    
    queries = [
        ("All entities", "MATCH (e:CodeEntity) RETURN e LIMIT 25"),
        ("Function call graph", """
            MATCH (source:CodeEntity)-[r:CODE_RELATIONSHIP {relationship_type: 'calls'}]->(target:CodeEntity)
            RETURN source.name, target.name
            LIMIT 25
        """),
        ("Class hierarchy", """
            MATCH (child:CodeEntity)-[r:CODE_RELATIONSHIP {relationship_type: 'inherits_from'}]->(parent:CodeEntity)
            RETURN child.name, parent.name
        """),
        ("Module imports", """
            MATCH (source:CodeEntity)-[r:CODE_RELATIONSHIP {relationship_type: 'imports'}]->(target:CodeEntity)
            RETURN source.file_path, target.name
            LIMIT 25
        """),
        ("Dependency graph", """
            MATCH (e:CodeEntity {entity_type: 'dependency'})
            RETURN e.name, e.language
        """),
        ("Files by entity count", """
            MATCH (e:CodeEntity)
            RETURN e.file_path, count(e) as entity_count
            ORDER BY entity_count DESC
            LIMIT 10
        """),
    ]
    
    print("\nCopy these queries to Neo4j Browser:")
    print()
    for title, query in queries:
        print(f"// {title}")
        print(query.strip())
        print()
    
    # Close connection
    storage.close()
    
    print("="*80)
    print("✨ PIPELINE COMPLETE!")
    print("="*80)
    print("\n🌐 Next Steps:")
    print("1. Open Neo4j Browser: http://localhost:7474")
    print("2. Login with neo4j/password")
    print("3. Run the Cypher queries above to explore the data")
    print("4. Try visualization queries like:")
    print("   MATCH (n:CodeEntity)-[r:CODE_RELATIONSHIP]->(m:CodeEntity)")
    print("   RETURN n, r, m LIMIT 50")
    print()
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
