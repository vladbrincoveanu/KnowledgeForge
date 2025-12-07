"""Docker and container configuration extractor."""

import logging
import re
import yaml
from pathlib import Path
from typing import Any, Optional

from domain.models.code_entities import (
    CodeEntity,
    CodeEntityType,
    CodeLanguage,
    CodeRelationship,
    CodeRelationType,
    SourceType,
)
from services.code_extraction.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class DockerExtractor(BaseExtractor):
    """Extract entities and relationships from Dockerfiles and docker-compose files."""
    
    def can_handle(self, file_path: Path) -> bool:
        """Check if file is a Docker configuration file."""
        name_lower = file_path.name.lower()
        return (
            name_lower == 'dockerfile' or
            name_lower.startswith('dockerfile.') or
            name_lower == 'docker-compose.yml' or
            name_lower == 'docker-compose.yaml' or
            name_lower == 'compose.yml' or
            name_lower == 'compose.yaml'
        )
    
    def extract(self, file_path: Path) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract entities and relationships from Docker file."""
        if 'compose' in file_path.name.lower():
            return self._extract_compose(file_path)
        else:
            return self._extract_dockerfile(file_path)
    
    def _extract_dockerfile(self, file_path: Path) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract from Dockerfile."""
        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []
        
        content = self.safe_read_file(file_path)
        if not content:
            return entities, relationships
        
        rel_path = self.get_relative_path(file_path)
        
        # Create container entity for the Dockerfile
        container_name = file_path.stem or "dockerfile"
        container_id = self.generate_entity_id(rel_path, container_name, "container")
        
        attributes = {
            "base_images": [],
            "exposed_ports": [],
            "volumes": [],
            "env_vars": [],
            "commands": [],
        }
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # FROM instruction - base image
            if line.startswith('FROM'):
                image = line.split()[1] if len(line.split()) > 1 else ""
                attributes["base_images"].append(image)
                
                # Create relationship to base image
                base_image_id = self.generate_entity_id(rel_path, image, "container")
                rel_id = self.generate_relationship_id(container_id, base_image_id, "depends_on")
                
                relationships.append(CodeRelationship(
                    id=rel_id,
                    source_entity_id=container_id,
                    target_entity_id=base_image_id,
                    relationship_type=CodeRelationType.DEPENDS_ON,
                    context=line,
                    attributes={"relationship": "uses_base_image"},
                    confidence=1.0,
                ))
            
            # EXPOSE instruction - ports
            elif line.startswith('EXPOSE'):
                ports = line.split()[1:]
                attributes["exposed_ports"].extend(ports)
            
            # VOLUME instruction
            elif line.startswith('VOLUME'):
                volume = line.split()[1] if len(line.split()) > 1 else ""
                attributes["volumes"].append(volume)
            
            # ENV instruction
            elif line.startswith('ENV'):
                env_var = ' '.join(line.split()[1:])
                attributes["env_vars"].append(env_var)
            
            # CMD/ENTRYPOINT
            elif line.startswith(('CMD', 'ENTRYPOINT')):
                attributes["commands"].append(line)
        
        container_entity = CodeEntity(
            id=container_id,
            name=container_name,
            entity_type=CodeEntityType.CONTAINER,
            language=CodeLanguage.UNKNOWN,
            source_type=SourceType.DOCKER,
            file_path=rel_path,
            attributes=attributes,
            confidence=1.0,
        )
        entities.append(container_entity)
        
        return entities, relationships
    
    def _extract_compose(self, file_path: Path) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract from docker-compose file."""
        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []
        
        content = self.safe_read_file(file_path)
        if not content:
            return entities, relationships
        
        rel_path = self.get_relative_path(file_path)
        
        try:
            compose_data = yaml.safe_load(content)
            
            if not compose_data or 'services' not in compose_data:
                return entities, relationships
            
            services = compose_data.get('services', {})
            volumes = compose_data.get('volumes', {})
            networks = compose_data.get('networks', {})
            
            # Extract volume entities
            for vol_name in volumes:
                vol_id = self.generate_entity_id(rel_path, vol_name, "volume")
                vol_entity = CodeEntity(
                    id=vol_id,
                    name=vol_name,
                    entity_type=CodeEntityType.VOLUME,
                    language=CodeLanguage.UNKNOWN,
                    source_type=SourceType.DOCKER,
                    file_path=rel_path,
                    attributes=volumes[vol_name] or {},
                    confidence=1.0,
                )
                entities.append(vol_entity)
            
            # Extract network entities
            for net_name in networks:
                net_id = self.generate_entity_id(rel_path, net_name, "network")
                net_entity = CodeEntity(
                    id=net_id,
                    name=net_name,
                    entity_type=CodeEntityType.NETWORK,
                    language=CodeLanguage.UNKNOWN,
                    source_type=SourceType.DOCKER,
                    file_path=rel_path,
                    attributes=networks[net_name] or {},
                    confidence=1.0,
                )
                entities.append(net_entity)
            
            # Extract service entities
            for service_name, service_config in services.items():
                service_id = self.generate_entity_id(rel_path, service_name, "service")
                
                attributes = {
                    "image": service_config.get('image'),
                    "build": service_config.get('build'),
                    "ports": service_config.get('ports', []),
                    "environment": service_config.get('environment', []),
                    "volumes": service_config.get('volumes', []),
                    "depends_on": service_config.get('depends_on', []),
                    "networks": service_config.get('networks', []),
                }
                
                service_entity = CodeEntity(
                    id=service_id,
                    name=service_name,
                    entity_type=CodeEntityType.SERVICE,
                    language=CodeLanguage.UNKNOWN,
                    source_type=SourceType.DOCKER,
                    file_path=rel_path,
                    attributes=attributes,
                    confidence=1.0,
                )
                entities.append(service_entity)
                
                # Create depends_on relationships
                for dep in service_config.get('depends_on', []):
                    dep_id = self.generate_entity_id(rel_path, dep, "service")
                    rel_id = self.generate_relationship_id(service_id, dep_id, "depends_on")
                    
                    relationships.append(CodeRelationship(
                        id=rel_id,
                        source_entity_id=service_id,
                        target_entity_id=dep_id,
                        relationship_type=CodeRelationType.DEPENDS_ON,
                        confidence=1.0,
                    ))
                
                # Create volume mount relationships
                for vol in service_config.get('volumes', []):
                    # Parse volume (could be named volume or bind mount)
                    if isinstance(vol, str):
                        vol_parts = vol.split(':')
                        vol_name = vol_parts[0]
                        
                        # Only create relationship if it's a named volume
                        if vol_name in volumes:
                            vol_id = self.generate_entity_id(rel_path, vol_name, "volume")
                            rel_id = self.generate_relationship_id(service_id, vol_id, "mounts")
                            
                            relationships.append(CodeRelationship(
                                id=rel_id,
                                source_entity_id=service_id,
                                target_entity_id=vol_id,
                                relationship_type=CodeRelationType.MOUNTS,
                                attributes={"mount_path": vol_parts[1] if len(vol_parts) > 1 else ""},
                                confidence=1.0,
                            ))
                
                # Create network relationships
                for net in service_config.get('networks', []):
                    if isinstance(net, str) and net in networks:
                        net_id = self.generate_entity_id(rel_path, net, "network")
                        rel_id = self.generate_relationship_id(service_id, net_id, "connects_to")
                        
                        relationships.append(CodeRelationship(
                            id=rel_id,
                            source_entity_id=service_id,
                            target_entity_id=net_id,
                            relationship_type=CodeRelationType.CONNECTS_TO,
                            confidence=1.0,
                        ))
        
        except yaml.YAMLError as e:
            self.errors.append(f"Failed to parse YAML in {file_path}: {e}")
        except Exception as e:
            self.errors.append(f"Failed to extract from {file_path}: {e}")
        
        return entities, relationships

