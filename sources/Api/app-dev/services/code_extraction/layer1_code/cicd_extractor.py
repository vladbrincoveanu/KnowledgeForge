"""CI/CD configuration extractor."""

import logging
import yaml
from pathlib import Path
from typing import Any

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


class CICDExtractor(BaseExtractor):
    """Extract entities and relationships from CI/CD configuration files."""
    
    def can_handle(self, file_path: Path) -> bool:
        """Check if file is a CI/CD configuration file."""
        # GitHub Actions
        if '.github/workflows' in str(file_path) and file_path.suffix in ['.yml', '.yaml']:
            return True
        
        # GitLab CI
        if file_path.name == '.gitlab-ci.yml':
            return True
        
        # Azure Pipelines
        if file_path.name in ['azure-pipelines.yml', 'azure-pipelines.yaml']:
            return True
        
        # Jenkins
        if file_path.name == 'Jenkinsfile':
            return True
        
        # Circle CI
        if '.circleci' in str(file_path) and file_path.name == 'config.yml':
            return True
        
        return False
    
    def extract(self, file_path: Path) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract entities and relationships from CI/CD file."""
        if '.github/workflows' in str(file_path):
            return self._extract_github_actions(file_path)
        elif file_path.name == '.gitlab-ci.yml':
            return self._extract_gitlab_ci(file_path)
        elif 'azure-pipelines' in file_path.name:
            return self._extract_azure_pipelines(file_path)
        elif file_path.name == 'Jenkinsfile':
            return self._extract_jenkinsfile(file_path)
        elif '.circleci' in str(file_path):
            return self._extract_circleci(file_path)
        
        return [], []
    
    def _extract_github_actions(
        self,
        file_path: Path
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract from GitHub Actions workflow file."""
        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []
        
        content = self.safe_read_file(file_path)
        if not content:
            return entities, relationships
        
        rel_path = self.get_relative_path(file_path)
        
        try:
            workflow = yaml.safe_load(content)
            
            if not workflow:
                return entities, relationships
            
            # Create pipeline entity
            workflow_name = workflow.get('name', file_path.stem)
            pipeline_id = self.generate_entity_id(rel_path, workflow_name, "pipeline")
            
            # Extract triggers
            on_config = workflow.get('on', {})
            triggers = []
            if isinstance(on_config, dict):
                triggers = list(on_config.keys())
            elif isinstance(on_config, list):
                triggers = on_config
            elif isinstance(on_config, str):
                triggers = [on_config]
            
            pipeline_entity = CodeEntity(
                id=pipeline_id,
                name=workflow_name,
                entity_type=CodeEntityType.PIPELINE,
                language=CodeLanguage.UNKNOWN,
                source_type=SourceType.CICD,
                file_path=rel_path,
                attributes={
                    "platform": "github_actions",
                    "triggers": triggers,
                    "env": workflow.get('env', {}),
                },
                confidence=1.0,
            )
            entities.append(pipeline_entity)
            
            # Extract jobs
            jobs = workflow.get('jobs', {})
            for job_name, job_config in jobs.items():
                job_id = self.generate_entity_id(rel_path, f"{workflow_name}.{job_name}", "job")
                
                # Extract steps
                steps = job_config.get('steps', [])
                step_names = []
                for step in steps:
                    if isinstance(step, dict):
                        step_name = step.get('name', step.get('uses', 'unnamed'))
                        step_names.append(step_name)
                
                job_entity = CodeEntity(
                    id=job_id,
                    name=job_name,
                    entity_type=CodeEntityType.JOB,
                    language=CodeLanguage.UNKNOWN,
                    source_type=SourceType.CICD,
                    file_path=rel_path,
                    parent_entity_id=pipeline_id,
                    attributes={
                        "runs_on": job_config.get('runs-on'),
                        "needs": job_config.get('needs', []),
                        "if": job_config.get('if'),
                        "steps": step_names,
                        "environment": job_config.get('environment'),
                    },
                    confidence=1.0,
                )
                entities.append(job_entity)
                
                # Create relationship: pipeline contains job
                rel_id = self.generate_relationship_id(pipeline_id, job_id, "contains")
                relationships.append(CodeRelationship(
                    id=rel_id,
                    source_entity_id=pipeline_id,
                    target_entity_id=job_id,
                    relationship_type=CodeRelationType.CONTAINS,
                    confidence=1.0,
                ))
                
                # Create dependencies between jobs
                needs = job_config.get('needs', [])
                if isinstance(needs, str):
                    needs = [needs]
                
                for dep_job_name in needs:
                    dep_job_id = self.generate_entity_id(rel_path, f"{workflow_name}.{dep_job_name}", "job")
                    rel_id = self.generate_relationship_id(job_id, dep_job_id, "depends_on")
                    
                    relationships.append(CodeRelationship(
                        id=rel_id,
                        source_entity_id=job_id,
                        target_entity_id=dep_job_id,
                        relationship_type=CodeRelationType.DEPENDS_ON,
                        confidence=1.0,
                    ))
        
        except yaml.YAMLError as e:
            self.errors.append(f"Failed to parse YAML in {file_path}: {e}")
        except Exception as e:
            self.errors.append(f"Failed to extract from {file_path}: {e}")
        
        return entities, relationships
    
    def _extract_gitlab_ci(
        self,
        file_path: Path
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract from GitLab CI configuration."""
        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []
        
        content = self.safe_read_file(file_path)
        if not content:
            return entities, relationships
        
        rel_path = self.get_relative_path(file_path)
        
        try:
            config = yaml.safe_load(content)
            
            if not config:
                return entities, relationships
            
            # Create pipeline entity
            pipeline_name = "gitlab-ci"
            pipeline_id = self.generate_entity_id(rel_path, pipeline_name, "pipeline")
            
            stages = config.get('stages', [])
            
            pipeline_entity = CodeEntity(
                id=pipeline_id,
                name=pipeline_name,
                entity_type=CodeEntityType.PIPELINE,
                language=CodeLanguage.UNKNOWN,
                source_type=SourceType.CICD,
                file_path=rel_path,
                attributes={
                    "platform": "gitlab",
                    "stages": stages,
                    "variables": config.get('variables', {}),
                },
                confidence=1.0,
            )
            entities.append(pipeline_entity)
            
            # Extract jobs
            for key, value in config.items():
                if isinstance(value, dict) and 'script' in value:
                    job_id = self.generate_entity_id(rel_path, f"{pipeline_name}.{key}", "job")
                    
                    job_entity = CodeEntity(
                        id=job_id,
                        name=key,
                        entity_type=CodeEntityType.JOB,
                        language=CodeLanguage.UNKNOWN,
                        source_type=SourceType.CICD,
                        file_path=rel_path,
                        parent_entity_id=pipeline_id,
                        attributes={
                            "stage": value.get('stage'),
                            "image": value.get('image'),
                            "script": value.get('script', []),
                            "only": value.get('only'),
                            "except": value.get('except'),
                            "needs": value.get('needs', []),
                        },
                        confidence=1.0,
                    )
                    entities.append(job_entity)
                    
                    # Create relationship
                    rel_id = self.generate_relationship_id(pipeline_id, job_id, "contains")
                    relationships.append(CodeRelationship(
                        id=rel_id,
                        source_entity_id=pipeline_id,
                        target_entity_id=job_id,
                        relationship_type=CodeRelationType.CONTAINS,
                        confidence=1.0,
                    ))
        
        except yaml.YAMLError as e:
            self.errors.append(f"Failed to parse YAML in {file_path}: {e}")
        except Exception as e:
            self.errors.append(f"Failed to extract from {file_path}: {e}")
        
        return entities, relationships
    
    def _extract_azure_pipelines(
        self,
        file_path: Path
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract from Azure Pipelines configuration."""
        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []
        
        content = self.safe_read_file(file_path)
        if not content:
            return entities, relationships
        
        rel_path = self.get_relative_path(file_path)
        
        try:
            config = yaml.safe_load(content)
            
            if not config:
                return entities, relationships
            
            # Create pipeline entity
            pipeline_name = config.get('name', 'azure-pipeline')
            pipeline_id = self.generate_entity_id(rel_path, pipeline_name, "pipeline")
            
            pipeline_entity = CodeEntity(
                id=pipeline_id,
                name=pipeline_name,
                entity_type=CodeEntityType.PIPELINE,
                language=CodeLanguage.UNKNOWN,
                source_type=SourceType.CICD,
                file_path=rel_path,
                attributes={
                    "platform": "azure_pipelines",
                    "trigger": config.get('trigger'),
                    "pool": config.get('pool'),
                    "variables": config.get('variables', []),
                },
                confidence=1.0,
            )
            entities.append(pipeline_entity)
            
            # Extract stages and jobs
            stages = config.get('stages', [])
            if stages:
                for stage in stages:
                    stage_name = stage.get('stage')
                    jobs = stage.get('jobs', [])
                    
                    for job in jobs:
                        job_name = job.get('job', 'unnamed')
                        job_id = self.generate_entity_id(rel_path, f"{pipeline_name}.{job_name}", "job")
                        
                        job_entity = CodeEntity(
                            id=job_id,
                            name=job_name,
                            entity_type=CodeEntityType.JOB,
                            language=CodeLanguage.UNKNOWN,
                            source_type=SourceType.CICD,
                            file_path=rel_path,
                            parent_entity_id=pipeline_id,
                            attributes={
                                "stage": stage_name,
                                "pool": job.get('pool'),
                                "steps": job.get('steps', []),
                            },
                            confidence=1.0,
                        )
                        entities.append(job_entity)
                        
                        rel_id = self.generate_relationship_id(pipeline_id, job_id, "contains")
                        relationships.append(CodeRelationship(
                            id=rel_id,
                            source_entity_id=pipeline_id,
                            target_entity_id=job_id,
                            relationship_type=CodeRelationType.CONTAINS,
                            confidence=1.0,
                        ))
        
        except yaml.YAMLError as e:
            self.errors.append(f"Failed to parse YAML in {file_path}: {e}")
        except Exception as e:
            self.errors.append(f"Failed to extract from {file_path}: {e}")
        
        return entities, relationships
    
    def _extract_jenkinsfile(
        self,
        file_path: Path
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract from Jenkinsfile (basic extraction - Groovy parsing would be complex)."""
        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []
        
        content = self.safe_read_file(file_path)
        if not content:
            return entities, relationships
        
        rel_path = self.get_relative_path(file_path)
        
        # Create pipeline entity
        pipeline_name = "jenkins-pipeline"
        pipeline_id = self.generate_entity_id(rel_path, pipeline_name, "pipeline")
        
        pipeline_entity = CodeEntity(
            id=pipeline_id,
            name=pipeline_name,
            entity_type=CodeEntityType.PIPELINE,
            language=CodeLanguage.UNKNOWN,
            source_type=SourceType.CICD,
            file_path=rel_path,
            attributes={
                "platform": "jenkins",
                "type": "declarative" if "pipeline {" in content else "scripted",
            },
            confidence=0.9,
        )
        entities.append(pipeline_entity)
        
        # Basic stage extraction using regex (limited)
        import re
        stage_pattern = re.compile(r'stage\([\'"]([^\'"]+)[\'"]\)')
        
        for match in stage_pattern.finditer(content):
            stage_name = match.group(1)
            stage_id = self.generate_entity_id(rel_path, f"{pipeline_name}.{stage_name}", "job")
            
            stage_entity = CodeEntity(
                id=stage_id,
                name=stage_name,
                entity_type=CodeEntityType.JOB,
                language=CodeLanguage.UNKNOWN,
                source_type=SourceType.CICD,
                file_path=rel_path,
                parent_entity_id=pipeline_id,
                confidence=0.8,
            )
            entities.append(stage_entity)
            
            rel_id = self.generate_relationship_id(pipeline_id, stage_id, "contains")
            relationships.append(CodeRelationship(
                id=rel_id,
                source_entity_id=pipeline_id,
                target_entity_id=stage_id,
                relationship_type=CodeRelationType.CONTAINS,
                confidence=0.8,
            ))
        
        return entities, relationships
    
    def _extract_circleci(
        self,
        file_path: Path
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract from CircleCI configuration."""
        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []
        
        content = self.safe_read_file(file_path)
        if not content:
            return entities, relationships
        
        rel_path = self.get_relative_path(file_path)
        
        try:
            config = yaml.safe_load(content)
            
            if not config:
                return entities, relationships
            
            # Create pipeline entity
            pipeline_name = "circleci-pipeline"
            pipeline_id = self.generate_entity_id(rel_path, pipeline_name, "pipeline")
            
            pipeline_entity = CodeEntity(
                id=pipeline_id,
                name=pipeline_name,
                entity_type=CodeEntityType.PIPELINE,
                language=CodeLanguage.UNKNOWN,
                source_type=SourceType.CICD,
                file_path=rel_path,
                attributes={
                    "platform": "circleci",
                    "version": config.get('version'),
                },
                confidence=1.0,
            )
            entities.append(pipeline_entity)
            
            # Extract jobs
            jobs = config.get('jobs', {})
            for job_name, job_config in jobs.items():
                job_id = self.generate_entity_id(rel_path, f"{pipeline_name}.{job_name}", "job")
                
                job_entity = CodeEntity(
                    id=job_id,
                    name=job_name,
                    entity_type=CodeEntityType.JOB,
                    language=CodeLanguage.UNKNOWN,
                    source_type=SourceType.CICD,
                    file_path=rel_path,
                    parent_entity_id=pipeline_id,
                    attributes={
                        "docker": job_config.get('docker', []),
                        "steps": job_config.get('steps', []),
                    },
                    confidence=1.0,
                )
                entities.append(job_entity)
                
                rel_id = self.generate_relationship_id(pipeline_id, job_id, "contains")
                relationships.append(CodeRelationship(
                    id=rel_id,
                    source_entity_id=pipeline_id,
                    target_entity_id=job_id,
                    relationship_type=CodeRelationType.CONTAINS,
                    confidence=1.0,
                ))
        
        except yaml.YAMLError as e:
            self.errors.append(f"Failed to parse YAML in {file_path}: {e}")
        except Exception as e:
            self.errors.append(f"Failed to extract from {file_path}: {e}")
        
        return entities, relationships

