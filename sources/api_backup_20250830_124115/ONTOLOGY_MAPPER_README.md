# OntologyMapper - KnowledgeForge Ontology Mapping System

The `OntologyMapper` class is a comprehensive solution for mapping extracted entities to standard ontologies and generating semantic knowledge representations. It integrates seamlessly with the existing KnowledgeForge ontology extraction pipeline.

## 🎯 Features

### ✅ Core Functionality
- **Standard Ontology Support**: Built-in support for Schema.org, Dublin Core, and FOAF ontologies
- **Dynamic Ontology Loading**: Load custom ontologies from URLs (RDF/OWL format)
- **Intelligent Entity Mapping**: Multi-strategy mapping using fuzzy matching, embeddings, and LLM suggestions
- **Custom Ontology Extensions**: Generate domain-specific ontology extensions for unmapped entities
- **RDF/OWL Generation**: Export mappings in standard semantic web formats
- **Ontology Validation**: Consistency checking and validation with detailed feedback
- **Evolution Tracking**: Monitor ontology changes and mapping improvements over time

### 🔧 Technical Capabilities
- **Fuzzy Matching**: Edit distance and semantic similarity for property alignment
- **Embedding-based Similarity**: TF-IDF vectorization for semantic matching
- **LLM Integration**: AI-powered mapping suggestions for complex entities
- **Confidence Scoring**: Detailed confidence metrics for each mapping
- **Namespace Management**: Proper URI and namespace handling for RDF output
- **Inheritance Hierarchy**: Support for class hierarchies and property inheritance

## 🚀 Quick Start

### Basic Usage

```python
from ontology_extractor import OntologyMapper, Entity, Relationship

# Initialize the mapper
mapper = OntologyMapper(use_embeddings=True)

# Map entities to ontologies
entities = [Entity(...), Entity(...)]
relationships = [Relationship(...), Relationship(...)]

mapping_result = mapper.map_entities_to_ontologies(entities, relationships)

# Generate custom ontology for unmapped entities
custom_ontology = mapper.generate_custom_ontology_extension(
    mapping_result.mapped_entities,
    mapping_result.unmapped_entities
)

# Create RDF output
rdf_output = mapper.create_rdf_triples(mapping_result.mapped_entities, custom_ontology)

# Validate ontology consistency
validation = mapper.validate_ontology_consistency(
    mapping_result.mapped_entities, 
    custom_ontology
)
```

### Advanced Usage

```python
# Load custom ontology from URL
mapper.load_ontology_from_url(
    "https://example.org/ontology.rdf",
    "CustomOntology"
)

# Export in OWL format
owl_output = mapper.export_owl_format(
    mapping_result.mapped_entities,
    custom_ontology,
    output_format="xml"
)

# Track ontology evolution
evolution_data = mapper.track_ontology_evolution(
    previous_mapping,
    current_mapping
)

# Save/load mapping results
mapper.save_mapping_results(mapping_result, "mappings.json")
loaded_results = mapper.load_mapping_results("mappings.json")
```

## 🏗️ Architecture

### Class Structure

```
OntologyMapper
├── StandardOntology (per ontology)
│   ├── classes: Dict[str, Dict]
│   ├── properties: Dict[str, Dict]
│   └── hierarchy: Dict[str, List[str]]
├── OntologyMappingResult
│   ├── mapped_entities: List[Dict]
│   ├── unmapped_entities: List[Entity]
│   ├── ontology_classes: List[Dict]
│   ├── confidence_scores: Dict[str, float]
│   ├── mapping_metadata: Dict
│   └── processing_time: float
└── Core Methods
    ├── map_entities_to_ontologies()
    ├── generate_custom_ontology_extension()
    ├── create_rdf_triples()
    ├── validate_ontology_consistency()
    ├── export_owl_format()
    └── track_ontology_evolution()
```

### Mapping Strategy

1. **Exact Matching**: Direct name and type matching
2. **Fuzzy Matching**: String similarity using edit distance
3. **Attribute Matching**: Property alignment between entities and classes
4. **Embedding Similarity**: Semantic similarity using TF-IDF vectors
5. **LLM Suggestions**: AI-powered mapping for complex cases

## 📊 Output Formats

### RDF Triples (Turtle)
```turtle
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix schema: <https://schema.org/> .
@prefix custom: <http://custom.ontology/> .

<http://example.org/entity/customer_001> 
    rdf:type schema:Person ;
    custom:email "john.doe@example.com" ;
    custom:phone "+1-555-1234" .
```

### OWL XML
```xml
<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:owl="http://www.w3.org/2002/07/owl#"
         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#">
  <owl:Class rdf:about="http://custom.ontology/CustomerEntity">
    <rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
    <rdfs:comment>Custom entity class for Customer</rdfs:comment>
  </owl:Class>
</rdf:RDF>
```

### JSON Mapping Results
```json
{
  "mapped_entities": [
    {
      "entity_id": "customer_001",
      "entity_name": "John Doe",
      "entity_type": "Customer",
      "ontology_name": "schema.org",
      "ontology_class": "Person",
      "ontology_uri": "https://schema.org/Person",
      "confidence": 0.85,
      "mapping_type": "class",
      "attributes_mapped": {
        "email": "email",
        "phone": "telephone"
      }
    }
  ],
  "mapping_metadata": {
    "target_ontologies": ["schema.org", "dublin_core", "foaf"],
    "total_entities": 3,
    "mapped_count": 2,
    "unmapped_count": 1,
    "average_confidence": 0.78
  }
}
```

## 🔍 Validation & Quality

### Consistency Checks
- **Circular Inheritance**: Detect cycles in class hierarchies
- **Orphaned Properties**: Identify unused properties
- **Confidence Distribution**: Monitor mapping quality metrics
- **Attribute Coverage**: Ensure comprehensive property mapping

### Quality Metrics
- **Mapping Coverage**: Percentage of entities successfully mapped
- **Confidence Distribution**: Statistical analysis of mapping confidence
- **Ontology Alignment**: Degree of alignment with standard ontologies
- **Custom Extension Quality**: Validation of generated custom classes

## 🔗 Integration with KnowledgeForge

### Pipeline Integration
```
CSV Data → EntityExtractor → RelationshipDiscoverer → OntologyMapper → GraphManager
                                    ↓
                            Custom Ontologies + RDF/OWL Output
```

### Usage in Main Pipeline
```python
from ontology_extractor import (
    EntityExtractor, 
    RelationshipDiscoverer, 
    OntologyMapper,
    GraphManager
)

# Extract entities and relationships
entity_extractor = EntityExtractor()
entities = entity_extractor.extract_entities(file_path, columns, config)

relationship_discoverer = RelationshipDiscoverer()
relationships = relationship_discoverer.discover_relationships(file_path, entities, config)

# Map to ontologies
ontology_mapper = OntologyMapper()
mapping_result = ontology_mapper.map_entities_to_ontologies(entities, relationships)

# Store in knowledge graph
graph_manager = GraphManager()
graph_manager.store_ontology(mapping_result, dataset_name)
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
cd sources/Api/ontology_extractor
python test_ontology_mapper.py
```

The test suite covers:
- Standard ontology initialization
- Entity mapping functionality
- Custom ontology generation
- RDF/OWL export
- Validation and consistency checking
- Save/load operations

## 📦 Dependencies

### Required Packages
- `rdflib>=6.3.0`: RDF processing and serialization
- `owlready2>=0.45.0`: OWL ontology management
- `scikit-learn>=1.3.0`: Machine learning for embeddings
- `numpy>=1.24.0`: Numerical operations
- `requests>=2.31.0`: HTTP requests for ontology loading

### Optional Dependencies
- `sentence-transformers`: Advanced embedding models
- `torch`: PyTorch for deep learning embeddings

## 🚧 Configuration

### Environment Variables
```bash
# Ontology mapping settings
ONTOLOGY_USE_EMBEDDINGS=true
ONTOLOGY_CACHE_DIR=./ontology_cache
ONTOLOGY_LLM_ENABLED=true
ONTOLOGY_CONFIDENCE_THRESHOLD=0.5
```

### Configuration File
```json
{
  "ontology_mapping": {
    "use_embeddings": true,
    "cache_dir": "./ontology_cache",
    "llm_enabled": true,
    "confidence_threshold": 0.5,
    "target_ontologies": ["schema.org", "dublin_core", "foaf"]
  }
}
```

## 🔮 Future Enhancements

### Planned Features
- **Advanced Embedding Models**: Support for BERT, GPT, and other transformer models
- **Semantic Similarity**: Enhanced similarity metrics using knowledge graphs
- **Ontology Alignment**: Automatic alignment between different ontologies
- **Version Control**: Git-like versioning for ontology evolution
- **Collaborative Mapping**: Multi-user mapping with conflict resolution
- **Performance Optimization**: Caching and parallel processing for large datasets

### Research Areas
- **Zero-shot Learning**: Mapping entities without training data
- **Cross-lingual Mapping**: Support for multiple languages
- **Domain Adaptation**: Automatic adaptation to specific domains
- **Quality Assessment**: Advanced metrics for mapping quality

## 📚 References

### Standards & Specifications
- [RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/)
- [OWL 2 Web Ontology Language](https://www.w3.org/TR/owl2-overview/)
- [Schema.org](https://schema.org/)
- [Dublin Core Metadata Initiative](https://dublincore.org/)
- [FOAF Vocabulary](http://xmlns.com/foaf/spec/)

### Academic Papers
- "Ontology Matching: State of the Art and Future Challenges" (Euzenat & Shvaiko, 2013)
- "A Survey of Ontology Alignment Evaluation" (Otero-Cerdeira et al., 2015)
- "Semantic Similarity in Biomedical Ontologies" (Pesquita et al., 2009)

## 🤝 Contributing

We welcome contributions to improve the OntologyMapper:

1. **Fork** the repository
2. **Create** a feature branch
3. **Implement** your improvements
4. **Add** comprehensive tests
5. **Submit** a pull request

### Development Guidelines
- Follow PEP 8 style guidelines
- Add type hints for all functions
- Include comprehensive docstrings
- Write unit tests for new functionality
- Update documentation for API changes

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

### Getting Help
- **Documentation**: This README and inline code documentation
- **Issues**: GitHub Issues for bug reports and feature requests
- **Discussions**: GitHub Discussions for questions and ideas
- **Email**: support@knowledgeforge.com

### Common Issues
- **Import Errors**: Ensure all dependencies are installed
- **Memory Issues**: Large datasets may require memory optimization
- **Performance**: Use caching and consider batch processing for large files
- **LLM Integration**: Check LLM Server service availability and configuration

---

**OntologyMapper** - Transforming extracted entities into semantic knowledge networks with confidence and precision. 🚀
