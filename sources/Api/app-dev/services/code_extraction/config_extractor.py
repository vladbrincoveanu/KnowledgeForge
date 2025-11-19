"""Configuration file and dependency extractor."""

import json
import logging
import re
import tomli
import yaml
from pathlib import Path
from typing import Any, Optional
from xml.etree import ElementTree as ET

from app.domain.models.code_entities import (
    CodeEntity,
    CodeEntityType,
    CodeLanguage,
    CodeRelationship,
    CodeRelationType,
    DependencyInfo,
    SourceType,
)
from app.services.code_extraction.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class ConfigExtractor(BaseExtractor):
    """Extract entities and dependencies from project configuration files."""
    
    # Mapping of config files to their languages
    CONFIG_MAP = {
        'package.json': CodeLanguage.JAVASCRIPT,
        'package-lock.json': CodeLanguage.JAVASCRIPT,
        'yarn.lock': CodeLanguage.JAVASCRIPT,
        'pnpm-lock.yaml': CodeLanguage.JAVASCRIPT,
        'pyproject.toml': CodeLanguage.PYTHON,
        'requirements.txt': CodeLanguage.PYTHON,
        'Pipfile': CodeLanguage.PYTHON,
        'Pipfile.lock': CodeLanguage.PYTHON,
        'poetry.lock': CodeLanguage.PYTHON,
        'pom.xml': CodeLanguage.JAVA,
        'build.gradle': CodeLanguage.JAVA,
        'build.gradle.kts': CodeLanguage.KOTLIN,
        'go.mod': CodeLanguage.GO,
        'go.sum': CodeLanguage.GO,
        'Cargo.toml': CodeLanguage.RUST,
        'Cargo.lock': CodeLanguage.RUST,
        'Gemfile': CodeLanguage.RUBY,
        'Gemfile.lock': CodeLanguage.RUBY,
        'composer.json': CodeLanguage.PHP,
        'composer.lock': CodeLanguage.PHP,
    }
    
    def __init__(self, repo_root: Path):
        super().__init__(repo_root)
        self.dependencies: list[DependencyInfo] = []
    
    def can_handle(self, file_path: Path) -> bool:
        """Check if file is a project configuration file."""
        return file_path.name in self.CONFIG_MAP
    
    def extract(self, file_path: Path) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract entities and dependencies from config file."""
        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []
        
        rel_path = self.get_relative_path(file_path)
        language = self.CONFIG_MAP.get(file_path.name, CodeLanguage.UNKNOWN)
        
        # Create config file entity
        config_id = self.generate_entity_id(rel_path, file_path.stem, "config_file")
        
        config_entity = CodeEntity(
            id=config_id,
            name=file_path.name,
            entity_type=CodeEntityType.CONFIG_FILE,
            language=language,
            source_type=SourceType.CONFIG,
            file_path=rel_path,
            confidence=1.0,
        )
        entities.append(config_entity)
        
        # Extract dependencies based on file type
        if file_path.name == 'package.json':
            deps = self._extract_package_json(file_path, rel_path, language)
        elif file_path.name.endswith('.lock') and 'package' in file_path.name:
            deps = self._extract_npm_lock(file_path, rel_path, language)
        elif file_path.name == 'pyproject.toml':
            deps = self._extract_pyproject(file_path, rel_path, language)
        elif file_path.name in ['requirements.txt', 'Pipfile', 'Pipfile.lock']:
            deps = self._extract_python_deps(file_path, rel_path, language)
        elif file_path.name == 'pom.xml':
            deps = self._extract_pom_xml(file_path, rel_path, language)
        elif file_path.name.startswith('build.gradle'):
            deps = self._extract_gradle(file_path, rel_path, language)
        elif file_path.name in ['go.mod', 'go.sum']:
            deps = self._extract_go_mod(file_path, rel_path, language)
        elif file_path.name in ['Cargo.toml', 'Cargo.lock']:
            deps = self._extract_cargo(file_path, rel_path, language)
        elif file_path.name in ['Gemfile', 'Gemfile.lock']:
            deps = self._extract_gemfile(file_path, rel_path, language)
        elif file_path.name in ['composer.json', 'composer.lock']:
            deps = self._extract_composer(file_path, rel_path, language)
        else:
            deps = []
        
        self.dependencies.extend(deps)
        
        # Create dependency entities and relationships
        for dep in deps:
            dep_id = self.generate_entity_id(rel_path, dep.name, "dependency")
            
            dep_entity = CodeEntity(
                id=dep_id,
                name=dep.name,
                entity_type=CodeEntityType.DEPENDENCY,
                language=language,
                source_type=SourceType.CONFIG,
                file_path=rel_path,
                attributes={
                    "version": dep.version,
                    "version_spec": dep.version_spec,
                    "dependency_type": dep.dependency_type,
                    "resolved_version": dep.resolved_version,
                },
                confidence=1.0,
            )
            entities.append(dep_entity)
            
            # Create DEPENDS_ON relationship
            rel_id = self.generate_relationship_id(config_id, dep_id, "depends_on")
            
            relationships.append(CodeRelationship(
                id=rel_id,
                source_entity_id=config_id,
                target_entity_id=dep_id,
                relationship_type=CodeRelationType.DEPENDS_ON,
                attributes={
                    "version": dep.version or dep.version_spec,
                    "dependency_type": dep.dependency_type,
                },
                confidence=1.0,
            ))
        
        return entities, relationships

    def reset(self) -> None:
        """Reset extractor state before a new repository scan."""
        super().reset()
        self.dependencies = []
    
    def _extract_package_json(
        self,
        file_path: Path,
        rel_path: str,
        language: CodeLanguage
    ) -> list[DependencyInfo]:
        """Extract dependencies from package.json."""
        deps: list[DependencyInfo] = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Regular dependencies
            for name, version_spec in data.get('dependencies', {}).items():
                deps.append(DependencyInfo(
                    name=name,
                    version_spec=version_spec,
                    language=language,
                    source_file=rel_path,
                    dependency_type='runtime',
                ))
            
            # Dev dependencies
            for name, version_spec in data.get('devDependencies', {}).items():
                deps.append(DependencyInfo(
                    name=name,
                    version_spec=version_spec,
                    language=language,
                    source_file=rel_path,
                    dependency_type='dev',
                ))
            
            # Peer dependencies
            for name, version_spec in data.get('peerDependencies', {}).items():
                deps.append(DependencyInfo(
                    name=name,
                    version_spec=version_spec,
                    language=language,
                    source_file=rel_path,
                    dependency_type='peer',
                ))
        
        except Exception as e:
            self.errors.append(f"Failed to parse {file_path}: {e}")
        
        return deps
    
    def _extract_npm_lock(
        self,
        file_path: Path,
        rel_path: str,
        language: CodeLanguage
    ) -> list[DependencyInfo]:
        """Extract resolved dependencies from package-lock.json."""
        deps: list[DependencyInfo] = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # package-lock.json v2/v3 format
            packages = data.get('packages', {})
            if packages:
                for package_path, package_info in packages.items():
                    if not package_path or package_path == '':
                        continue
                    
                    name = package_info.get('name', package_path.replace('node_modules/', ''))
                    version = package_info.get('version')
                    dev = package_info.get('dev', False)
                    
                    deps.append(DependencyInfo(
                        name=name,
                        version=version,
                        resolved_version=version,
                        language=language,
                        source_file=rel_path,
                        dependency_type='dev' if dev else 'runtime',
                    ))
            else:
                # package-lock.json v1 format
                for name, package_info in data.get('dependencies', {}).items():
                    version = package_info.get('version')
                    
                    deps.append(DependencyInfo(
                        name=name,
                        version=version,
                        resolved_version=version,
                        language=language,
                        source_file=rel_path,
                        dependency_type='runtime',
                    ))
        
        except Exception as e:
            self.errors.append(f"Failed to parse {file_path}: {e}")
        
        return deps
    
    def _extract_pyproject(
        self,
        file_path: Path,
        rel_path: str,
        language: CodeLanguage
    ) -> list[DependencyInfo]:
        """Extract dependencies from pyproject.toml."""
        deps: list[DependencyInfo] = []
        
        try:
            with open(file_path, 'rb') as f:
                data = tomli.load(f)
            
            # PEP 621 dependencies
            project = data.get('project', {})
            for dep_spec in project.get('dependencies', []):
                name, version_spec = self._parse_python_dep(dep_spec)
                deps.append(DependencyInfo(
                    name=name,
                    version_spec=version_spec,
                    language=language,
                    source_file=rel_path,
                    dependency_type='runtime',
                ))
            
            # Optional dependencies
            for group, dep_list in project.get('optional-dependencies', {}).items():
                for dep_spec in dep_list:
                    name, version_spec = self._parse_python_dep(dep_spec)
                    deps.append(DependencyInfo(
                        name=name,
                        version_spec=version_spec,
                        language=language,
                        source_file=rel_path,
                        dependency_type=group,
                    ))
            
            # Poetry dependencies
            poetry = data.get('tool', {}).get('poetry', {})
            for name, spec in poetry.get('dependencies', {}).items():
                if name == 'python':
                    continue
                version_spec = spec if isinstance(spec, str) else spec.get('version', '*')
                deps.append(DependencyInfo(
                    name=name,
                    version_spec=version_spec,
                    language=language,
                    source_file=rel_path,
                    dependency_type='runtime',
                ))
            
            for name, spec in poetry.get('dev-dependencies', {}).items():
                version_spec = spec if isinstance(spec, str) else spec.get('version', '*')
                deps.append(DependencyInfo(
                    name=name,
                    version_spec=version_spec,
                    language=language,
                    source_file=rel_path,
                    dependency_type='dev',
                ))
        
        except Exception as e:
            self.errors.append(f"Failed to parse {file_path}: {e}")
        
        return deps
    
    def _extract_python_deps(
        self,
        file_path: Path,
        rel_path: str,
        language: CodeLanguage
    ) -> list[DependencyInfo]:
        """Extract dependencies from requirements.txt or Pipfile."""
        deps: list[DependencyInfo] = []
        
        content = self.safe_read_file(file_path)
        if not content:
            return deps
        
        if file_path.name == 'requirements.txt':
            for line in content.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                name, version_spec = self._parse_python_dep(line)
                deps.append(DependencyInfo(
                    name=name,
                    version_spec=version_spec,
                    language=language,
                    source_file=rel_path,
                    dependency_type='runtime',
                ))
        
        elif file_path.name in ['Pipfile', 'Pipfile.lock']:
            try:
                if file_path.name == 'Pipfile':
                    # Pipfile uses TOML-like syntax
                    with open(file_path, 'rb') as f:
                        data = tomli.load(f)
                else:
                    # Pipfile.lock is JSON
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                
                for section in ['packages', 'dev-packages']:
                    dep_type = 'runtime' if section == 'packages' else 'dev'
                    packages = data.get(section, {})
                    
                    for name, spec in packages.items():
                        version_spec = spec if isinstance(spec, str) else spec.get('version', '*')
                        version = spec.get('version') if isinstance(spec, dict) else None
                        
                        deps.append(DependencyInfo(
                            name=name,
                            version=version,
                            version_spec=version_spec,
                            language=language,
                            source_file=rel_path,
                            dependency_type=dep_type,
                        ))
            except Exception as e:
                self.errors.append(f"Failed to parse {file_path}: {e}")
        
        return deps
    
    def _extract_pom_xml(
        self,
        file_path: Path,
        rel_path: str,
        language: CodeLanguage
    ) -> list[DependencyInfo]:
        """Extract dependencies from pom.xml."""
        deps: list[DependencyInfo] = []
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Maven namespace
            ns = {'maven': 'http://maven.apache.org/POM/4.0.0'}
            
            # Find dependencies
            for dep in root.findall('.//maven:dependency', ns):
                group_id = dep.find('maven:groupId', ns)
                artifact_id = dep.find('maven:artifactId', ns)
                version = dep.find('maven:version', ns)
                scope = dep.find('maven:scope', ns)
                
                if group_id is not None and artifact_id is not None:
                    name = f"{group_id.text}:{artifact_id.text}"
                    version_text = version.text if version is not None else None
                    scope_text = scope.text if scope is not None else 'compile'
                    
                    deps.append(DependencyInfo(
                        name=name,
                        version=version_text,
                        language=language,
                        source_file=rel_path,
                        dependency_type=scope_text,
                    ))
        
        except Exception as e:
            self.errors.append(f"Failed to parse {file_path}: {e}")
        
        return deps
    
    def _extract_gradle(
        self,
        file_path: Path,
        rel_path: str,
        language: CodeLanguage
    ) -> list[DependencyInfo]:
        """Extract dependencies from build.gradle."""
        deps: list[DependencyInfo] = []
        
        content = self.safe_read_file(file_path)
        if not content:
            return deps
        
        # Regex to match dependency declarations
        dep_pattern = re.compile(r'(implementation|api|compileOnly|runtimeOnly|testImplementation)\s+[\'"]([^:]+):([^:]+):([^\'\"]+)[\'"]')
        
        for match in dep_pattern.finditer(content):
            dep_type = match.group(1)
            group_id = match.group(2)
            artifact_id = match.group(3)
            version = match.group(4)
            
            name = f"{group_id}:{artifact_id}"
            
            deps.append(DependencyInfo(
                name=name,
                version=version,
                language=language,
                source_file=rel_path,
                dependency_type=dep_type,
            ))
        
        return deps
    
    def _extract_go_mod(
        self,
        file_path: Path,
        rel_path: str,
        language: CodeLanguage
    ) -> list[DependencyInfo]:
        """Extract dependencies from go.mod."""
        deps: list[DependencyInfo] = []
        
        content = self.safe_read_file(file_path)
        if not content:
            return deps
        
        in_require_block = False
        
        for line in content.split('\n'):
            line = line.strip()
            
            if line.startswith('require ('):
                in_require_block = True
                continue
            elif line == ')' and in_require_block:
                in_require_block = False
                continue
            
            if line.startswith('require ') or in_require_block:
                # Parse "module version" format
                parts = line.replace('require ', '').strip().split()
                if len(parts) >= 2:
                    name = parts[0]
                    version = parts[1]
                    
                    deps.append(DependencyInfo(
                        name=name,
                        version=version,
                        language=language,
                        source_file=rel_path,
                        dependency_type='runtime',
                    ))
        
        return deps
    
    def _extract_cargo(
        self,
        file_path: Path,
        rel_path: str,
        language: CodeLanguage
    ) -> list[DependencyInfo]:
        """Extract dependencies from Cargo.toml."""
        deps: list[DependencyInfo] = []
        
        try:
            with open(file_path, 'rb') as f:
                data = tomli.load(f)
            
            for section in ['dependencies', 'dev-dependencies', 'build-dependencies']:
                dep_type = 'dev' if 'dev' in section else 'build' if 'build' in section else 'runtime'
                dependencies = data.get(section, {})
                
                for name, spec in dependencies.items():
                    version_spec = spec if isinstance(spec, str) else spec.get('version', '*')
                    
                    deps.append(DependencyInfo(
                        name=name,
                        version_spec=version_spec,
                        language=language,
                        source_file=rel_path,
                        dependency_type=dep_type,
                    ))
        
        except Exception as e:
            self.errors.append(f"Failed to parse {file_path}: {e}")
        
        return deps
    
    def _extract_gemfile(
        self,
        file_path: Path,
        rel_path: str,
        language: CodeLanguage
    ) -> list[DependencyInfo]:
        """Extract dependencies from Gemfile."""
        deps: list[DependencyInfo] = []
        
        content = self.safe_read_file(file_path)
        if not content:
            return deps
        
        # Regex for gem declarations
        gem_pattern = re.compile(r'gem\s+[\'"]([^\'"]+)[\'"](?:,\s+[\'"]([^\'"]+)[\'"])?')
        
        for match in gem_pattern.finditer(content):
            name = match.group(1)
            version_spec = match.group(2) if match.group(2) else None
            
            deps.append(DependencyInfo(
                name=name,
                version_spec=version_spec,
                language=language,
                source_file=rel_path,
                dependency_type='runtime',
            ))
        
        return deps
    
    def _extract_composer(
        self,
        file_path: Path,
        rel_path: str,
        language: CodeLanguage
    ) -> list[DependencyInfo]:
        """Extract dependencies from composer.json."""
        deps: list[DependencyInfo] = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for name, version_spec in data.get('require', {}).items():
                if name == 'php':
                    continue
                deps.append(DependencyInfo(
                    name=name,
                    version_spec=version_spec,
                    language=language,
                    source_file=rel_path,
                    dependency_type='runtime',
                ))
            
            for name, version_spec in data.get('require-dev', {}).items():
                deps.append(DependencyInfo(
                    name=name,
                    version_spec=version_spec,
                    language=language,
                    source_file=rel_path,
                    dependency_type='dev',
                ))
        
        except Exception as e:
            self.errors.append(f"Failed to parse {file_path}: {e}")
        
        return deps
    
    def _parse_python_dep(self, dep_spec: str) -> tuple[str, str]:
        """Parse Python dependency specification."""
        # Handle extras: package[extra1,extra2]>=1.0
        if '[' in dep_spec:
            dep_spec = dep_spec.split('[')[0]
        
        # Split on version operators
        for op in ['>=', '<=', '==', '!=', '~=', '>', '<']:
            if op in dep_spec:
                parts = dep_spec.split(op)
                return parts[0].strip(), f"{op}{parts[1].strip()}"
        
        return dep_spec.strip(), '*'
