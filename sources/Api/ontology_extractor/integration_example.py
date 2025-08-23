"""Integration example showing how to use OntologyMapper in the KnowledgeForge pipeline."""

import sys
import os
from pathlib import Path

# Add the parent directory to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ontology_extractor import (
    DataProfiler,
    EntityExtractor,
    RelationshipDiscoverer,
    OntologyMapper,
    GraphManager,
    LLMManager
)


def run_ontology_extraction_pipeline(csv_file_path: str, output_dir: str = "./output"):
    """Run the complete ontology extraction pipeline with ontology mapping."""
    
    print("🚀 Starting KnowledgeForge Ontology Extraction Pipeline")
    print(f"📁 Input file: {csv_file_path}")
    print(f"📁 Output directory: {output_dir}")
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        # Step 1: Profile the data
        print("\n📊 Step 1: Profiling data...")
        profiler = DataProfiler()
        profile = profiler.profile_dataset(csv_file_path)
        print(f"✅ Data profiling completed. Found {len(profile.columns)} columns")
        
        # Step 2: Extract entities
        print("\n🔍 Step 2: Extracting entities...")
        entity_extractor = EntityExtractor()
        entities = entity_extractor.extract_entities(
            csv_file_path, 
            profile.columns, 
            {"extraction_method": "hybrid"}
        )
        print(f"✅ Entity extraction completed. Found {len(entities)} entities")
        
        # Step 3: Discover relationships
        print("\n🔗 Step 3: Discovering relationships...")
        relationship_discoverer = RelationshipDiscoverer()
        relationships = relationship_discoverer.discover_relationships(
            csv_file_path, 
            entities, 
            {"discovery_method": "statistical"}
        )
        print(f"✅ Relationship discovery completed. Found {len(relationships)} relationships")
        
        # Step 4: Map entities to ontologies
        print("\n🗺️  Step 4: Mapping entities to ontologies...")
        
        # Initialize LLM manager (optional)
        llm_manager = None
        try:
            llm_manager = LLMManager()
            print("✅ LLM manager initialized successfully")
        except Exception as e:
            print(f"⚠️  LLM manager not available: {e}")
        
        # Initialize ontology mapper
        ontology_mapper = OntologyMapper(
            llm_manager=llm_manager,
            cache_dir=output_path / "ontology_cache",
            use_embeddings=True
        )
        
        # Perform ontology mapping
        mapping_result = ontology_mapper.map_entities_to_ontologies(
            entities, 
            relationships,
            target_ontologies=["schema.org", "dublin_core", "foaf"]
        )
        
        print(f"✅ Ontology mapping completed:")
        print(f"   - Mapped entities: {mapping_result.mapping_metadata['mapped_count']}")
        print(f"   - Unmapped entities: {mapping_result.mapping_metadata['unmapped_count']}")
        print(f"   - Average confidence: {mapping_result.mapping_metadata['average_confidence']:.2f}")
        
        # Step 5: Generate custom ontology extension
        print("\n🔧 Step 5: Generating custom ontology extension...")
        custom_ontology = ontology_mapper.generate_custom_ontology_extension(
            mapping_result.mapped_entities,
            mapping_result.unmapped_entities
        )
        print(f"✅ Custom ontology generated with {len(custom_ontology['classes'])} classes")
        
        # Step 6: Create RDF output
        print("\n📝 Step 6: Generating RDF output...")
        rdf_output = ontology_mapper.create_rdf_triples(
            mapping_result.mapped_entities,
            custom_ontology
        )
        
        # Save RDF output
        rdf_file = output_path / "ontology_output.ttl"
        with open(rdf_file, 'w') as f:
            f.write(rdf_output)
        print(f"✅ RDF output saved to {rdf_file}")
        
        # Step 7: Validate ontology consistency
        print("\n✅ Step 7: Validating ontology consistency...")
        validation_results = ontology_mapper.validate_ontology_consistency(
            mapping_result.mapped_entities,
            custom_ontology
        )
        
        print(f"   - Is consistent: {validation_results['is_consistent']}")
        print(f"   - Warnings: {len(validation_results['warnings'])}")
        print(f"   - Errors: {len(validation_results['errors'])}")
        
        if validation_results['warnings']:
            print("   ⚠️  Warnings:")
            for warning in validation_results['warnings']:
                print(f"      - {warning}")
        
        if validation_results['errors']:
            print("   ❌ Errors:")
            for error in validation_results['errors']:
                print(f"      - {error}")
        
        # Step 8: Export OWL format
        print("\n🦉 Step 8: Exporting OWL format...")
        owl_output = ontology_mapper.export_owl_format(
            mapping_result.mapped_entities,
            custom_ontology,
            output_format="xml"
        )
        
        if owl_output:
            owl_file = output_path / "ontology_output.owl"
            with open(owl_file, 'w') as f:
                f.write(owl_output)
            print(f"✅ OWL output saved to {owl_file}")
        else:
            print("⚠️  OWL export failed")
        
        # Step 9: Save mapping results
        print("\n💾 Step 9: Saving mapping results...")
        mapping_file = output_path / "mapping_results.json"
        if ontology_mapper.save_mapping_results(mapping_result, mapping_file):
            print(f"✅ Mapping results saved to {mapping_file}")
        else:
            print("❌ Failed to save mapping results")
        
        # Step 10: Store in knowledge graph (optional)
        print("\n🗄️  Step 10: Storing in knowledge graph...")
        try:
            graph_manager = GraphManager()
            if graph_manager.is_connected():
                # Create ontology object for storage
                from ontology_extractor.models import Ontology
                ontology = Ontology(
                    entities=entities,
                    relationships=relationships,
                    metadata={
                        "source_file": csv_file_path,
                        "mapping_result": mapping_result.mapping_metadata,
                        "custom_ontology": custom_ontology
                    },
                    created_at=str(Path(csv_file_path).stat().st_mtime),
                    version="1.0"
                )
                
                if graph_manager.store_ontology(ontology, "integrated_dataset"):
                    print("✅ Ontology stored in knowledge graph successfully")
                else:
                    print("⚠️  Failed to store ontology in knowledge graph")
            else:
                print("⚠️  Knowledge graph not available, skipping storage")
        except Exception as e:
            print(f"⚠️  Knowledge graph storage failed: {e}")
        
        # Summary
        print("\n🎉 Pipeline completed successfully!")
        print(f"📊 Summary:")
        print(f"   - Input file: {csv_file_path}")
        print(f"   - Entities extracted: {len(entities)}")
        print(f"   - Relationships discovered: {len(relationships)}")
        print(f"   - Entities mapped to ontologies: {mapping_result.mapping_metadata['mapped_count']}")
        print(f"   - Custom ontology classes: {len(custom_ontology['classes'])}")
        print(f"   - Output files saved to: {output_path}")
        
        return {
            "success": True,
            "entities": entities,
            "relationships": relationships,
            "mapping_result": mapping_result,
            "custom_ontology": custom_ontology,
            "output_directory": str(output_path)
        }
        
    except Exception as e:
        print(f"❌ Pipeline failed with error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def main():
    """Main function to run the integration example."""
    
    # Example usage
    csv_file = input("Enter the path to your CSV file: ").strip()
    
    if not csv_file or not Path(csv_file).exists():
        print("❌ Invalid file path. Please provide a valid CSV file.")
        return
    
    output_directory = input("Enter output directory (default: ./output): ").strip()
    if not output_directory:
        output_directory = "./output"
    
    # Run the pipeline
    result = run_ontology_extraction_pipeline(csv_file, output_directory)
    
    if result["success"]:
        print("\n🎯 Next steps:")
        print("   1. Review the generated RDF/OWL files")
        print("   2. Validate the ontology consistency")
        print("   3. Import into your preferred ontology editor")
        print("   4. Use the mapping results for further analysis")
    else:
        print(f"\n❌ Pipeline failed: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
