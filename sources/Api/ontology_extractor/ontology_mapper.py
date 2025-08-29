"""Ontology mapping module for mapping extracted entities to standard ontologies."""

import logging
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set
from pathlib import Path
from urllib.parse import urlparse, urljoin
import requests
from difflib import SequenceMatcher
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import rdflib
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, XSD
from rdflib.namespace import DC, FOAF, SKOS
import owlready2
from owlready2 import *
from pydantic import BaseModel

from .models import Entity, Relationship, Ontology
from .llm_manager import LLMManager

logger = logging.getLogger(__name__)


class OntologyMappingResult(BaseModel):
    """Result of ontology mapping operation."""
    mapped_entities: List[Dict[str, Any]]
    unmapped_entities: List[Entity]
    ontology_classes: List[Dict[str, Any]]
    confidence_scores: Dict[str, float]
    mapping_metadata: Dict[str, Any]
    processing_time: float


class StandardOntology:
    """Represents a standard ontology with its classes and properties."""
    
    def __init__(self, name: str, namespace: str, prefix: str):
        self.name = name
        self.namespace = namespace
        self.prefix = prefix
        self.classes: Dict[str, Dict[str, Any]] = {}
        self.properties: Dict[str, Dict[str, Any]] = {}
        self.hierarchy: Dict[str, List[str]] = {}
        
    def add_class(self, class_name: str, class_info: Dict[str, Any]):
        """Add a class to the ontology."""
        self.classes[class_name] = class_info
        
    def add_property(self, property_name: str, property_info: Dict[str, Any]):
        """Add a property to the ontology."""
        self.properties[property_name] = property_info
        
    def add_hierarchy(self, parent: str, children: List[str]):
        """Add hierarchy information."""
        if parent not in self.hierarchy:
            self.hierarchy[parent] = []
        self.hierarchy[parent].extend(children)


class OntologyMapper:
    """Maps extracted entities to standard ontologies and generates RDF/OWL output."""
    
    def __init__(self, llm_manager: Optional[LLMManager] = None, 
                 cache_dir: Optional[str] = None,
                 use_embeddings: bool = True):
        """Initialize the ontology mapper.
        
        Args:
            llm_manager: LLM manager for mapping suggestions
            cache_dir: Directory for caching ontology data
            use_embeddings: Whether to use embeddings for similarity matching
        """
        self.llm_manager = llm_manager
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.use_embeddings = use_embeddings
        
        # Initialize standard ontologies
        self.standard_ontologies = self._initialize_standard_ontologies()
        
        # Initialize embedding model if enabled
        self.vectorizer = None
        if self.use_embeddings:
            self.vectorizer = TfidfVectorizer(
                max_features=1000,
                stop_words='english',
                ngram_range=(1, 2)
            )
        
        # Cache for ontology data
        self.ontology_cache = {}
        
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _initialize_standard_ontologies(self) -> Dict[str, StandardOntology]:
        """Initialize standard ontologies with their classes and properties."""
        ontologies = {}
        
        # Schema.org ontology
        schema_org = StandardOntology("Schema.org", "https://schema.org/", "schema")
        schema_org.add_class("Person", {
            "description": "A person (alive, dead, undead, or fictional).",
            "properties": ["name", "email", "telephone", "address", "birthDate"],
            "superclass": "Thing"
        })
        schema_org.add_class("Organization", {
            "description": "An organization such as a school, NGO, corporation, club, etc.",
            "properties": ["name", "url", "logo", "description", "address"],
            "superclass": "Thing"
        })
        schema_org.add_class("Product", {
            "description": "Any offered product or service.",
            "properties": ["name", "description", "brand", "category", "price"],
            "superclass": "Thing"
        })
        schema_org.add_class("Event", {
            "description": "An event happening at a certain time and location.",
            "properties": ["name", "startDate", "endDate", "location", "description"],
            "superclass": "Thing"
        })
        schema_org.add_hierarchy("Thing", ["Person", "Organization", "Product", "Event"])
        ontologies["schema.org"] = schema_org
        
        # Dublin Core ontology
        dublin_core = StandardOntology("Dublin Core", "http://purl.org/dc/elements/1.1/", "dc")
        dublin_core.add_class("Resource", {
            "description": "A resource that can be described.",
            "properties": ["title", "creator", "subject", "description", "publisher", "date"],
            "superclass": None
        })
        dublin_core.add_property("title", {"type": "string", "description": "A name given to the resource"})
        dublin_core.add_property("creator", {"type": "string", "description": "An entity primarily responsible for making the resource"})
        dublin_core.add_property("subject", {"type": "string", "description": "The topic of the resource"})
        ontologies["dublin_core"] = dublin_core
        
        # FOAF ontology
        foaf = StandardOntology("FOAF", "http://xmlns.com/foaf/0.1/", "foaf")
        foaf.add_class("Person", {
            "description": "A person.",
            "properties": ["name", "mbox", "homepage", "knows", "based_near"],
            "superclass": "Agent"
        })
        foaf.add_class("Organization", {
            "description": "An organization.",
            "properties": ["name", "homepage", "member", "fundedBy"],
            "superclass": "Agent"
        })
        foaf.add_hierarchy("Agent", ["Person", "Organization"])
        ontologies["foaf"] = foaf
        
        return ontologies
    
    def load_ontology_from_url(self, url: str, ontology_type: str) -> bool:
        """Load ontology from URL (RDF/OWL format)."""
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                # Parse RDF/OWL content
                graph = Graph()
                graph.parse(data=response.text, format='xml')
                
                # Extract classes and properties
                ontology = StandardOntology(ontology_type, url, ontology_type.lower())
                
                # Extract classes
                for s, p, o in graph.triples((None, RDF.type, OWL.Class)):
                    class_name = str(s).split('#')[-1] if '#' in str(s) else str(s).split('/')[-1]
                    ontology.add_class(class_name, {
                        "uri": str(s),
                        "description": "",
                        "properties": [],
                        "superclass": None
                    })
                
                # Extract properties
                for s, p, o in graph.triples((None, RDF.type, OWL.ObjectProperty)):
                    prop_name = str(s).split('#')[-1] if '#' in str(s) else str(s).split('/')[-1]
                    ontology.add_property(prop_name, {
                        "uri": str(s),
                        "type": "object",
                        "description": ""
                    })
                
                self.standard_ontologies[ontology_type] = ontology
                logger.info(f"Successfully loaded ontology from {url}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to load ontology from {url}: {e}")
            return False
        
        return False
    
    def map_entities_to_ontologies(self, entities: List[Entity], 
                                 relationships: List[Relationship],
                                 target_ontologies: Optional[List[str]] = None) -> OntologyMappingResult:
        """Map extracted entities to standard ontologies.
        
        Args:
            entities: List of extracted entities
            relationships: List of relationships between entities
            target_ontologies: List of ontology names to use for mapping
            
        Returns:
            OntologyMappingResult with mapping information
        """
        import time
        start_time = time.time()
        
        if target_ontologies is None:
            target_ontologies = list(self.standard_ontologies.keys())
        
        mapped_entities = []
        unmapped_entities = []
        ontology_classes = []
        confidence_scores = {}
        
        # Prepare text for embeddings if enabled
        if self.use_embeddings and self.vectorizer:
            entity_texts = [f"{e.name} {e.entity_type} {' '.join(str(v) for v in e.attributes.values())}" 
                           for e in entities]
            try:
                entity_vectors = self.vectorizer.fit_transform(entity_texts)
            except Exception as e:
                logger.warning(f"Failed to create embeddings: {e}")
                entity_vectors = None
        else:
            entity_vectors = None
        
        # Ensure all entities have valid IDs
        for i, entity in enumerate(entities):
            if entity.id is None or entity.id == "":
                # Create a stable ID based on entity name and index
                entity.id = f"entity_{i}_{abs(hash(str(entity.name))) % 1000000}"
        
        # Map each entity
        for i, entity in enumerate(entities):
            best_mapping = None
            best_confidence = 0.0
            
            for ontology_name in target_ontologies:
                if ontology_name not in self.standard_ontologies:
                    continue
                    
                ontology = self.standard_ontologies[ontology_name]
                
                # Find best matching class
                for class_name, class_info in ontology.classes.items():
                    confidence = self._calculate_mapping_confidence(
                        entity, class_name, class_info, 
                        entity_vectors[i] if entity_vectors is not None else None
                    )
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_mapping = {
                            "entity_id": entity.id,
                            "entity_name": entity.name,
                            "entity_type": entity.entity_type,
                            "ontology_name": ontology_name,
                            "ontology_class": class_name,
                            "ontology_uri": class_info.get("uri", f"{ontology.namespace}{class_name}"),
                            "confidence": confidence,
                            "mapping_type": "class",
                            "attributes_mapped": self._map_attributes(entity, class_info)
                        }
            
            # Use LLM for additional mapping suggestions if available
            if self.llm_manager and best_confidence < 0.7:
                llm_mapping = self._get_llm_mapping_suggestion(entity, target_ontologies)
                if llm_mapping and llm_mapping["confidence"] > best_confidence:
                    best_mapping = llm_mapping
                    best_confidence = llm_mapping["confidence"]
            
            if best_mapping and best_confidence > 0.5:
                mapped_entities.append(best_mapping)
                confidence_scores[entity.id] = best_confidence
                
                # Add ontology class information
                ontology_classes.append({
                    "name": best_mapping["ontology_class"],
                    "ontology": best_mapping["ontology_name"],
                    "uri": best_mapping["ontology_uri"],
                    "description": self.standard_ontologies[best_mapping["ontology_name"]]
                                    .classes[best_mapping["ontology_class"]].get("description", "")
                })
            else:
                unmapped_entities.append(entity)
                confidence_scores[entity.id] = best_confidence if best_mapping else 0.0
        
        processing_time = time.time() - start_time
        
        # Ensure confidence_scores only contains valid keys
        valid_confidence_scores = {k: v for k, v in confidence_scores.items() if k is not None}
        
        return OntologyMappingResult(
            mapped_entities=mapped_entities,
            unmapped_entities=unmapped_entities,
            ontology_classes=ontology_classes,
            confidence_scores=valid_confidence_scores,
            mapping_metadata={
                "target_ontologies": target_ontologies,
                "total_entities": len(entities),
                "mapped_count": len(mapped_entities),
                "unmapped_count": len(unmapped_entities),
                "average_confidence": np.mean(list(valid_confidence_scores.values())) if valid_confidence_scores else 0.0
            },
            processing_time=processing_time
        )
    
    def _calculate_mapping_confidence(self, entity: Entity, class_name: str, 
                                    class_info: Dict[str, Any], 
                                    entity_vector: Optional[np.ndarray] = None) -> float:
        """Calculate confidence score for entity-to-class mapping."""
        confidence = 0.0
        
        # 1. Exact name matching
        if entity.name.lower() == class_name.lower():
            confidence += 0.4
        elif entity.entity_type.lower() == class_name.lower():
            confidence += 0.3
        
        # 2. Fuzzy string matching
        name_similarity = SequenceMatcher(None, entity.name.lower(), class_name.lower()).ratio()
        confidence += name_similarity * 0.2
        
        # 3. Attribute matching
        if class_info.get("properties"):
            attribute_matches = 0
            for attr in class_info["properties"]:
                if any(attr.lower() in str(v).lower() for v in entity.attributes.values()):
                    attribute_matches += 1
            
            if class_info["properties"]:
                attribute_confidence = attribute_matches / len(class_info["properties"])
                confidence += attribute_confidence * 0.2
        
        # 4. Embedding similarity (if available)
        if entity_vector is not None and self.vectorizer:
            try:
                class_text = f"{class_name} {class_info.get('description', '')}"
                class_vector = self.vectorizer.transform([class_text])
                
                # Safety check: ensure vectors are valid
                if entity_vector is not None and class_vector is not None:
                    # Check for zero vectors
                    if not np.allclose(entity_vector, 0) and not np.allclose(class_vector, 0):
                        similarity = cosine_similarity(entity_vector, class_vector)[0][0]
                        confidence += similarity * 0.1
                    else:
                        logger.debug("Skipping cosine similarity due to zero vectors")
                else:
                    logger.debug("Skipping cosine similarity due to invalid vectors")
                    
            except Exception as e:
                logger.debug(f"Failed to calculate embedding similarity: {e}")
        
        return min(confidence, 1.0)
    
    def _map_attributes(self, entity: Entity, class_info: Dict[str, Any]) -> Dict[str, str]:
        """Map entity attributes to ontology properties."""
        attribute_mappings = {}
        
        if not class_info.get("properties"):
            return attribute_mappings
        
        for prop in class_info["properties"]:
            # Find best matching attribute
            best_match = None
            best_score = 0.0
            
            for attr_name, attr_value in entity.attributes.items():
                score = SequenceMatcher(None, attr_name.lower(), prop.lower()).ratio()
                if score > best_score and score > 0.6:
                    best_score = score
                    best_match = attr_name
            
            if best_match:
                attribute_mappings[best_match] = prop
        
        return attribute_mappings
    
    def _get_llm_mapping_suggestion(self, entity: Entity, 
                                  target_ontologies: List[str]) -> Optional[Dict[str, Any]]:
        """Get LLM-based mapping suggestion for entity."""
        try:
            # Create context for LLM
            context = {
                "entity_name": entity.name,
                "entity_type": entity.entity_type,
                "attributes": entity.attributes,
                "available_ontologies": target_ontologies
            }
            
            # Use LLM to suggest mapping
            response = self.llm_manager.generate_ontology_mapping(context)
            if response:
                # Parse LLM response and create mapping
                # This is a simplified version - you might want to enhance the LLM prompt
                return {
                    "entity_id": entity.id,
                    "entity_name": entity.name,
                    "entity_type": entity.entity_type,
                    "ontology_name": "llm_suggested",
                    "ontology_class": "CustomClass",
                    "ontology_uri": f"http://custom.ontology/{entity.entity_type}",
                    "confidence": 0.6,
                    "mapping_type": "llm_suggested",
                    "attributes_mapped": {}
                }
        except Exception as e:
            logger.debug(f"LLM mapping suggestion failed: {e}")
        
        return None
    
    def generate_custom_ontology_extension(self, mapped_entities: List[Dict[str, Any]], 
                                         unmapped_entities: List[Entity]) -> Dict[str, Any]:
        """Generate custom ontology extension for domain-specific entities."""
        custom_ontology = {
            "name": "CustomDomainOntology",
            "namespace": "http://custom.ontology/",
            "prefix": "custom",
            "classes": {},
            "properties": {},
            "relationships": []
        }
        
        # Add custom classes for unmapped entities
        for entity in unmapped_entities:
            class_name = f"{entity.entity_type}Entity"
            custom_ontology["classes"][class_name] = {
                "description": f"Custom entity class for {entity.entity_type}",
                "properties": list(entity.attributes.keys()),
                "superclass": "Thing",
                "source_entity": entity.id
            }
        
        # Add custom properties based on common attributes
        all_attributes = set()
        for entity in mapped_entities + [{"attributes": e.attributes} for e in unmapped_entities]:
            all_attributes.update(entity.get("attributes", {}).keys())
        
        for attr in all_attributes:
            if attr not in custom_ontology["properties"]:
                custom_ontology["properties"][attr] = {
                    "type": "string",
                    "description": f"Property for {attr}",
                    "domain": "Thing"
                }
        
        return custom_ontology
    
    def create_rdf_triples(self, mapped_entities: List[Dict[str, Any]], 
                          custom_ontology: Optional[Dict[str, Any]] = None) -> str:
        """Create RDF triples with proper namespaces and URIs."""
        # Create RDF graph
        g = Graph()
        
        # Define namespaces
        namespaces = {
            "rdf": RDF,
            "rdfs": RDFS,
            "owl": OWL,
            "xsd": XSD,
            "dc": DC,
            "foaf": FOAF,
            "skos": SKOS
        }
        
        # Add custom ontology namespace if provided
        if custom_ontology:
            custom_ns = Namespace(custom_ontology["namespace"])
            namespaces["custom"] = custom_ns
            g.bind("custom", custom_ns)
        
        # Bind all namespaces
        for prefix, namespace in namespaces.items():
            g.bind(prefix, namespace)
        
        # Add entity instances
        for entity in mapped_entities:
            # Create entity URI
            entity_uri = URIRef(f"http://example.org/entity/{entity['entity_id']}")
            
            # Add entity type
            if entity["ontology_uri"]:
                class_uri = URIRef(entity["ontology_uri"])
                g.add((entity_uri, RDF.type, class_uri))
            
            # Add entity properties
            for attr_name, attr_value in entity.get("attributes_mapped", {}).items():
                if attr_value in entity.get("attributes", {}):
                    value = entity["attributes"][attr_value]
                    if isinstance(value, (int, float)):
                        literal = Literal(value, datatype=XSD.decimal)
                    elif isinstance(value, bool):
                        literal = Literal(value, datatype=XSD.boolean)
                    else:
                        literal = Literal(str(value))
                    
                    # Use custom property URI
                    prop_uri = URIRef(f"http://custom.ontology/{attr_name}")
                    g.add((entity_uri, prop_uri, literal))
        
        # Serialize to Turtle format
        return g.serialize(format='turtle')
    
    def validate_ontology_consistency(self, mapped_entities: List[Dict[str, Any]], 
                                    custom_ontology: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate ontology consistency and provide feedback."""
        validation_results = {
            "is_consistent": True,
            "warnings": [],
            "errors": [],
            "suggestions": []
        }
        
        # Check for circular inheritance
        if custom_ontology:
            inheritance_graph = {}
            for class_name, class_info in custom_ontology["classes"].items():
                superclass = class_info.get("superclass")
                if superclass:
                    if superclass not in inheritance_graph:
                        inheritance_graph[superclass] = []
                    inheritance_graph[superclass].append(class_name)
            
            # Check for cycles (simplified)
            visited = set()
            rec_stack = set()
            
            def has_cycle(node):
                visited.add(node)
                rec_stack.add(node)
                
                for neighbor in inheritance_graph.get(node, []):
                    if neighbor not in visited:
                        if has_cycle(neighbor):
                            return True
                    elif neighbor in rec_stack:
                        return True
                
                rec_stack.remove(node)
                return False
            
            for node in inheritance_graph:
                if node not in visited:
                    if has_cycle(node):
                        validation_results["is_consistent"] = False
                        validation_results["errors"].append(f"Circular inheritance detected involving {node}")
        
        # Check for orphaned properties
        if custom_ontology:
            used_properties = set()
            for class_info in custom_ontology["classes"].values():
                used_properties.update(class_info.get("properties", []))
            
            orphaned_properties = set(custom_ontology["properties"].keys()) - used_properties
            if orphaned_properties:
                validation_results["warnings"].append(f"Orphaned properties: {', '.join(orphaned_properties)}")
        
        # Check mapping confidence distribution
        confidence_scores = [e.get("confidence", 0.0) for e in mapped_entities]
        if confidence_scores:
            avg_confidence = np.mean(confidence_scores)
            if avg_confidence < 0.6:
                validation_results["warnings"].append(f"Low average mapping confidence: {avg_confidence:.2f}")
            
            low_confidence_count = sum(1 for c in confidence_scores if c < 0.5)
            if low_confidence_count > len(mapped_entities) * 0.3:
                validation_results["suggestions"].append("Consider reviewing low-confidence mappings")
        
        return validation_results
    
    def export_owl_format(self, mapped_entities: List[Dict[str, Any]], 
                         custom_ontology: Optional[Dict[str, Any]] = None,
                         output_format: str = "xml") -> str:
        """Export ontology in OWL format."""
        try:
            # Create OWL ontology using owlready2
            onto = get_ontology("http://custom.ontology/")
            
            with onto:
                # Define custom classes
                if custom_ontology:
                    for class_name, class_info in custom_ontology["classes"].items():
                        # Create class dynamically
                        new_class = type(class_name, (Thing,), {})
                        new_class.__doc__ = class_info.get("description", "")
                        
                        # Add properties
                        for prop_name in class_info.get("properties", []):
                            if prop_name in custom_ontology.get("properties", {}):
                                prop_info = custom_ontology["properties"][prop_name]
                                if prop_info.get("type") == "string":
                                    setattr(new_class, prop_name, str)
                                elif prop_info.get("type") == "int":
                                    setattr(new_class, prop_name, int)
                                elif prop_info.get("type") == "float":
                                    setattr(new_class, prop_name, float)
                                elif prop_info.get("type") == "bool":
                                    setattr(new_class, prop_name, bool)
            
            # Export to specified format
            if output_format == "xml":
                return onto.get_owl()
            elif output_format == "rdfxml":
                return onto.get_rdf()
            else:
                return str(onto)
                
        except Exception as e:
            logger.error(f"Failed to export OWL format: {e}")
            return ""
    
    def track_ontology_evolution(self, previous_mapping: OntologyMappingResult, 
                                current_mapping: OntologyMappingResult) -> Dict[str, Any]:
        """Track ontology evolution and changes between mappings."""
        evolution_data = {
            "timestamp": str(datetime.now()),
            "changes": {
                "entities_added": [],
                "entities_removed": [],
                "entities_modified": [],
                "confidence_changes": []
            },
            "summary": {
                "total_changes": 0,
                "mapping_improvements": 0,
                "mapping_degradations": 0
            }
        }
        
        # Compare entity mappings
        previous_entities = {e["entity_id"]: e for e in previous_mapping.mapped_entities}
        current_entities = {e["entity_id"]: e for e in current_mapping.mapped_entities}
        
        # Find added entities
        for entity_id in current_entities:
            if entity_id not in previous_entities:
                evolution_data["changes"]["entities_added"].append({
                    "entity_id": entity_id,
                    "mapping": current_entities[entity_id]
                })
                evolution_data["summary"]["total_changes"] += 1
        
        # Find removed entities
        for entity_id in previous_entities:
            if entity_id not in current_entities:
                evolution_data["changes"]["entities_removed"].append({
                    "entity_id": entity_id,
                    "mapping": previous_entities[entity_id]
                })
                evolution_data["summary"]["total_changes"] += 1
        
        # Find modified entities
        for entity_id in current_entities:
            if entity_id in previous_entities:
                prev_entity = previous_entities[entity_id]
                curr_entity = current_entities[entity_id]
                
                if (prev_entity["ontology_class"] != curr_entity["ontology_class"] or
                    prev_entity["ontology_name"] != curr_entity["ontology_name"]):
                    
                    evolution_data["changes"]["entities_modified"].append({
                        "entity_id": entity_id,
                        "previous_mapping": prev_entity,
                        "current_mapping": curr_entity
                    })
                    evolution_data["summary"]["total_changes"] += 1
                
                # Track confidence changes
                prev_conf = previous_mapping.confidence_scores.get(entity_id, 0.0)
                curr_conf = current_mapping.confidence_scores.get(entity_id, 0.0)
                
                if abs(curr_conf - prev_conf) > 0.1:
                    evolution_data["changes"]["confidence_changes"].append({
                        "entity_id": entity_id,
                        "previous_confidence": prev_conf,
                        "current_confidence": curr_conf,
                        "change": curr_conf - prev_conf
                    })
                    
                    if curr_conf > prev_conf:
                        evolution_data["summary"]["mapping_improvements"] += 1
                    else:
                        evolution_data["summary"]["mapping_degradations"] += 1
        
        return evolution_data
    
    def save_mapping_results(self, mapping_result: OntologyMappingResult, 
                           file_path: str) -> bool:
        """Save mapping results to file."""
        try:
            output_data = {
                "mapped_entities": mapping_result.mapped_entities,
                "unmapped_entities": [e.dict() for e in mapping_result.unmapped_entities],
                "ontology_classes": mapping_result.ontology_classes,
                "confidence_scores": mapping_result.confidence_scores,
                "mapping_metadata": mapping_result.mapping_metadata,
                "processing_time": mapping_result.processing_time
            }
            
            with open(file_path, 'w') as f:
                json.dump(output_data, f, indent=2, default=str)
            
            logger.info(f"Mapping results saved to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save mapping results: {e}")
            return False
    
    def load_mapping_results(self, file_path: str) -> Optional[OntologyMappingResult]:
        """Load mapping results from file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Reconstruct unmapped entities
            unmapped_entities = []
            for entity_data in data.get("unmapped_entities", []):
                unmapped_entities.append(Entity(**entity_data))
            
            return OntologyMappingResult(
                mapped_entities=data.get("mapped_entities", []),
                unmapped_entities=unmapped_entities,
                ontology_classes=data.get("ontology_classes", []),
                confidence_scores=data.get("confidence_scores", {}),
                mapping_metadata=data.get("mapping_metadata", {}),
                processing_time=data.get("processing_time", 0.0)
            )
            
        except Exception as e:
            logger.error(f"Failed to load mapping results: {e}")
            return None
