"""Service relationship discoverer that finds connections between services."""

import logging
import re
import yaml
import json
from pathlib import Path
from typing import Any, Optional

from app.domain.models.services import Service, ServiceConnection, ConnectionType
from app.domain.models.code_entities import CodeRelationship, CodeRelationType

logger = logging.getLogger(__name__)


class ServiceRelationshipDiscoverer:
    """Discover relationships and connections between services."""
    
    def __init__(self, repo_root: Path, services: list[Service]):
        """
        Initialize relationship discoverer.
        
        Args:
            repo_root: Root path of the repository
            services: List of discovered services
        """
        self.repo_root = Path(repo_root).resolve()
        self.services = services
        self.service_map = {s.id: s for s in services}
        self.service_name_map = {s.name: s for s in services}
        self.connections: list[ServiceConnection] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []
    
    def discover_connections(self) -> list[ServiceConnection]:
        """
        Discover all connections between services.
        
        Returns:
            List of discovered connections
        """
        self.connections = []
        self.errors = []
        self.warnings = []
        
        logger.info(f"Starting relationship discovery for {len(self.services)} services")
        
        # Discover from docker-compose dependencies
        self._discover_from_docker_compose()
        
        # Discover from HTTP calls in code
        self._discover_from_http_calls()
        
        # Discover from API client usage
        self._discover_from_api_clients()
        
        # Discover from message queue configurations
        self._discover_from_message_queues()
        
        # Discover from database connections
        self._discover_from_database_configs()
        
        # Discover from service discovery configs
        self._discover_from_service_discovery()
        
        logger.info(f"Discovered {len(self.connections)} connections")
        
        return self.connections
    
    def _discover_from_docker_compose(self) -> None:
        """Discover connections from docker-compose depends_on relationships."""
        compose_files = list(self.repo_root.rglob('docker-compose*.yml')) + \
                       list(self.repo_root.rglob('docker-compose*.yaml')) + \
                       list(self.repo_root.rglob('compose.yml')) + \
                       list(self.repo_root.rglob('compose.yaml'))
        
        for compose_file in compose_files:
            try:
                with open(compose_file, 'r', encoding='utf-8') as f:
                    compose_data = yaml.safe_load(f)
                
                if not compose_data or 'services' not in compose_data:
                    continue
                
                rel_path = str(compose_file.relative_to(self.repo_root))
                
                for service_name, service_config in compose_data.get('services', {}).items():
                    source_service = self.service_name_map.get(service_name)
                    if not source_service:
                        continue
                    
                    # Check depends_on
                    depends_on = service_config.get('depends_on', [])
                    if isinstance(depends_on, list):
                        for dep_name in depends_on:
                            target_service = self.service_name_map.get(dep_name)
                            if target_service and target_service.id != source_service.id:
                                self._add_connection(
                                    source_service.id,
                                    target_service.id,
                                    ConnectionType.DEPENDS_ON,
                                    file_path=rel_path,
                                    attributes={'docker_compose_depends_on': True},
                                )
                    
                    # Check environment variables for service URLs
                    env = service_config.get('environment', {})
                    if isinstance(env, dict):
                        for key, value in env.items():
                            if isinstance(value, str) and any(
                                svc.name.lower() in value.lower() 
                                for svc in self.services 
                                if svc.id != source_service.id
                            ):
                                # Try to find target service from URL
                                for target_service in self.services:
                                    if target_service.id != source_service.id:
                                        if target_service.name.lower() in value.lower():
                                            self._add_connection(
                                                source_service.id,
                                                target_service.id,
                                                ConnectionType.HTTP,
                                                file_path=rel_path,
                                                attributes={'env_var': key, 'url': value},
                                            )
                                            break
                    
                    # Check links (legacy docker-compose)
                    links = service_config.get('links', [])
                    if isinstance(links, list):
                        for link in links:
                            link_name = link.split(':')[0] if ':' in link else link
                            target_service = self.service_name_map.get(link_name)
                            if target_service and target_service.id != source_service.id:
                                self._add_connection(
                                    source_service.id,
                                    target_service.id,
                                    ConnectionType.CALLS,
                                    file_path=rel_path,
                                    attributes={'docker_compose_link': True},
                                )
            
            except Exception as e:
                error_msg = f"Failed to discover from {compose_file}: {e}"
                self.errors.append(error_msg)
                logger.debug(error_msg)
    
    def _discover_from_http_calls(self) -> None:
        """Discover connections from HTTP client calls in code."""
        # Look for HTTP client patterns in code files
        code_files = list(self.repo_root.rglob('*.py')) + \
                    list(self.repo_root.rglob('*.js')) + \
                    list(self.repo_root.rglob('*.ts')) + \
                    list(self.repo_root.rglob('*.java')) + \
                    list(self.repo_root.rglob('*.go'))
        
        # Patterns to match HTTP calls
        http_patterns = [
            (r'https?://([^/\s"\']+)', 'http'),
            (r'fetch\([\'"]([^"\']+)[\'"]', 'http'),
            (r'axios\.(get|post|put|delete)\([\'"]([^"\']+)[\'"]', 'http'),
            (r'requests\.(get|post|put|delete)\([\'"]([^"\']+)[\'"]', 'http'),
            (r'http\.(get|post|put|delete)\([\'"]([^"\']+)[\'"]', 'http'),
            (r'urllib\.request\.urlopen\([\'"]([^"\']+)[\'"]', 'http'),
        ]
        
        for code_file in code_files:
            # Skip node_modules, venv, etc.
            if any(skip in str(code_file) for skip in ['node_modules', 'venv', '__pycache__', '.git']):
                continue
            
            try:
                content = self._safe_read_file(code_file)
                if not content:
                    continue
                
                rel_path = str(code_file.relative_to(self.repo_root))
                
                # Find which service this file belongs to
                source_service = self._find_service_for_file(code_file)
                if not source_service:
                    continue
                
                # Match HTTP patterns
                for pattern, conn_type in http_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        # BUG FIX: Handle different capture group patterns correctly
                        # Patterns with 1 group: (url) -> group 1 is URL, no method
                        # Patterns with 2 groups: (method, url) -> group 1 is method, group 2 is URL
                        num_groups = len(match.groups())
                        
                        if num_groups == 0:
                            url = match.group(0)
                            method = None
                        elif num_groups == 1:
                            url = match.group(1)
                            method = None
                        else:  # 2 or more groups
                            method = match.group(1)  # First group is method
                            url = match.group(2)     # Second group is URL
                        
                        # Try to find target service from URL
                        target_service = self._find_service_from_url(url)
                        if target_service and target_service.id != source_service.id:
                            
                            self._add_connection(
                                source_service.id,
                                target_service.id,
                                ConnectionType.HTTP,
                                endpoint=url,
                                method=method,
                                file_path=rel_path,
                                context=match.group(0),
                            )
            
            except Exception as e:
                self.warnings.append(f"Failed to process {code_file}: {e}")
    
    def _discover_from_api_clients(self) -> None:
        """Discover connections from API client configurations."""
        # Look for API client config files
        config_patterns = [
            '**/api_client*.py',
            '**/api_client*.js',
            '**/api_client*.ts',
            '**/clients*.py',
            '**/clients*.js',
            '**/clients*.ts',
            '**/client*.json',
            '**/api*.json',
        ]
        
        config_files = []
        for pattern in config_patterns:
            config_files.extend(self.repo_root.glob(pattern))
        
        for config_file in config_files:
            try:
                content = self._safe_read_file(config_file)
                if not content:
                    continue
                
                rel_path = str(config_file.relative_to(self.repo_root))
                source_service = self._find_service_for_file(config_file)
                if not source_service:
                    continue
                
                # Try to parse as JSON or YAML
                if config_file.suffix == '.json':
                    try:
                        data = json.loads(content)
                        self._extract_connections_from_config(data, source_service, rel_path)
                    except json.JSONDecodeError:
                        pass
                elif config_file.suffix in ['.yml', '.yaml']:
                    try:
                        data = yaml.safe_load(content)
                        self._extract_connections_from_config(data, source_service, rel_path)
                    except yaml.YAMLError:
                        pass
                
                # Also search for service URLs in content
                for service in self.services:
                    if service.id == source_service.id:
                        continue
                    
                    # Look for service name or ID in config
                    if service.name.lower() in content.lower() or service.id.lower() in content.lower():
                        # Try to extract URL
                        url_pattern = rf'{re.escape(service.name)}[:\s]*["\']?([^"\'\s]+)["\']?'
                        url_match = re.search(url_pattern, content, re.IGNORECASE)
                        url = url_match.group(1) if url_match else None
                        
                        self._add_connection(
                            source_service.id,
                            service.id,
                            ConnectionType.HTTP,
                            endpoint=url,
                            file_path=rel_path,
                        )
            
            except Exception as e:
                self.warnings.append(f"Failed to process {config_file}: {e}")
    
    def _discover_from_message_queues(self) -> None:
        """Discover connections from message queue configurations."""
        # Look for message queue configs
        mq_patterns = [
            '**/rabbitmq*.yml',
            '**/rabbitmq*.yaml',
            '**/kafka*.yml',
            '**/kafka*.yaml',
            '**/redis*.yml',
            '**/redis*.yaml',
            '**/sqs*.yml',
            '**/sqs*.yaml',
        ]
        
        mq_files = []
        for pattern in mq_patterns:
            mq_files.extend(self.repo_root.glob(pattern))
        
        for mq_file in mq_files:
            try:
                content = self._safe_read_file(mq_file)
                if not content:
                    continue
                
                rel_path = str(mq_file.relative_to(self.repo_root))
                
                if mq_file.suffix in ['.yml', '.yaml']:
                    data = yaml.safe_load(content)
                    if not isinstance(data, dict):
                        continue
                    
                    # Look for publishers and subscribers
                    publishers = data.get('publishers', {})
                    subscribers = data.get('subscribers', {})
                    
                    for pub_name, pub_config in publishers.items() if isinstance(publishers, dict) else []:
                        pub_service = self.service_name_map.get(pub_name)
                        if not pub_service:
                            continue
                        
                        topics = pub_config.get('topics', []) if isinstance(pub_config, dict) else []
                        for topic in topics if isinstance(topics, list) else []:
                            # Find subscribers for this topic
                            for sub_name, sub_config in subscribers.items() if isinstance(subscribers, dict) else []:
                                sub_service = self.service_name_map.get(sub_name)
                                if not sub_service or sub_service.id == pub_service.id:
                                    continue
                                
                                sub_topics = sub_config.get('topics', []) if isinstance(sub_config, dict) else []
                                if topic in (sub_topics if isinstance(sub_topics, list) else []):
                                    self._add_connection(
                                        pub_service.id,
                                        sub_service.id,
                                        ConnectionType.PUBLISHES,
                                        file_path=rel_path,
                                        attributes={'topic': topic},
                                    )
            
            except Exception as e:
                self.warnings.append(f"Failed to process {mq_file}: {e}")
    
    def _discover_from_database_configs(self) -> None:
        """Discover connections from database configuration files."""
        # Look for database configs
        db_patterns = [
            '**/database*.yml',
            '**/database*.yaml',
            '**/db*.yml',
            '**/db*.yaml',
            '**/datasource*.yml',
            '**/datasource*.yaml',
        ]
        
        db_files = []
        for pattern in db_patterns:
            db_files.extend(self.repo_root.glob(pattern))
        
        for db_file in db_files:
            try:
                content = self._safe_read_file(db_file)
                if not content:
                    continue
                
                rel_path = str(db_file.relative_to(self.repo_root))
                
                if db_file.suffix in ['.yml', '.yaml']:
                    data = yaml.safe_load(content)
                    if not isinstance(data, dict):
                        continue
                    
                    # Look for service-database mappings
                    for service_name, db_config in data.items():
                        service = self.service_name_map.get(service_name)
                        if not service:
                            continue
                        
                        # Database connections are typically storage connections
                        db_name = db_config.get('database') if isinstance(db_config, dict) else None
                        if db_name:
                            # Create a virtual database service or connection
                            # For now, we'll just note it in attributes
                            pass
            
            except Exception as e:
                self.warnings.append(f"Failed to process {db_file}: {e}")
    
    def _discover_from_service_discovery(self) -> None:
        """Discover connections from service discovery configurations."""
        # Look for service discovery configs (Consul, Eureka, etc.)
        sd_patterns = [
            '**/consul*.yml',
            '**/consul*.yaml',
            '**/eureka*.yml',
            '**/eureka*.yaml',
            '**/service-discovery*.yml',
            '**/service-discovery*.yaml',
        ]
        
        sd_files = []
        for pattern in sd_patterns:
            sd_files.extend(self.repo_root.glob(pattern))
        
        for sd_file in sd_files:
            try:
                content = self._safe_read_file(sd_file)
                if not content:
                    continue
                
                rel_path = str(sd_file.relative_to(self.repo_root))
                
                if sd_file.suffix in ['.yml', '.yaml']:
                    data = yaml.safe_load(content)
                    if not isinstance(data, dict):
                        continue
                    
                    # Look for service registrations and dependencies
                    services = data.get('services', {})
                    if isinstance(services, dict):
                        for service_name, service_config in services.items():
                            source_service = self.service_name_map.get(service_name)
                            if not source_service:
                                continue
                            
                            dependencies = service_config.get('dependencies', []) if isinstance(service_config, dict) else []
                            for dep_name in dependencies if isinstance(dependencies, list) else []:
                                target_service = self.service_name_map.get(dep_name)
                                if target_service and target_service.id != source_service.id:
                                    self._add_connection(
                                        source_service.id,
                                        target_service.id,
                                        ConnectionType.CALLS,
                                        file_path=rel_path,
                                        attributes={'service_discovery': True},
                                    )
            
            except Exception as e:
                self.warnings.append(f"Failed to process {sd_file}: {e}")
    
    def _extract_connections_from_config(self, data: dict, source_service: Service, file_path: str) -> None:
        """Extract connections from configuration data."""
        if not isinstance(data, dict):
            return
        
        # Look for service URLs or endpoints
        for key, value in data.items():
            if isinstance(value, str):
                # Check if value contains a service name or URL
                for service in self.services:
                    if service.id == source_service.id:
                        continue
                    
                    if service.name.lower() in value.lower() or service.id.lower() in value.lower():
                        self._add_connection(
                            source_service.id,
                            service.id,
                            ConnectionType.HTTP,
                            endpoint=value if 'http' in value.lower() else None,
                            file_path=file_path,
                            attributes={'config_key': key},
                        )
            elif isinstance(value, dict):
                self._extract_connections_from_config(value, source_service, file_path)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._extract_connections_from_config(item, source_service, file_path)
    
    def _find_service_for_file(self, file_path: Path) -> Optional[Service]:
        """Find which service a file belongs to."""
        rel_path = str(file_path.relative_to(self.repo_root))
        
        # Check if file path matches any service's file_path
        for service in self.services:
            if service.file_path and service.file_path in rel_path:
                return service
        
        # Try to match by directory structure
        parts = file_path.parts
        repo_parts = self.repo_root.parts
        
        # Look for service name in path
        for i, part in enumerate(parts):
            if part in self.service_name_map:
                return self.service_name_map[part]
        
        return None
    
    def _find_service_from_url(self, url: str) -> Optional[Service]:
        """Find service from URL pattern."""
        url_lower = url.lower()
        
        # Try exact name match
        for service in self.services:
            if service.name.lower() in url_lower:
                return service
        
        # Try ID match
        for service in self.services:
            if service.id.lower() in url_lower:
                return service
        
        return None
    
    def _add_connection(
        self,
        source_id: str,
        target_id: str,
        connection_type: ConnectionType,
        protocol: Optional[str] = None,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        file_path: Optional[str] = None,
        context: Optional[str] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add a connection if it doesn't already exist."""
        # Check if connection already exists
        conn_id = f"conn-{source_id}-{target_id}-{connection_type.value}"
        
        if any(c.id == conn_id for c in self.connections):
            return
        
        connection = ServiceConnection(
            id=conn_id,
            source_service_id=source_id,
            target_service_id=target_id,
            connection_type=connection_type,
            protocol=protocol,
            endpoint=endpoint,
            method=method,
            file_path=file_path,
            context=context,
            attributes=attributes or {},
        )
        
        self.connections.append(connection)
        
        # Update service dependencies
        source_service = self.service_map.get(source_id)
        target_service = self.service_map.get(target_id)
        
        if source_service and target_service:
            if target_id not in source_service.dependencies:
                source_service.dependencies.append(target_id)
            if source_id not in target_service.dependents:
                target_service.dependents.append(source_id)
    
    def _safe_read_file(self, file_path: Path) -> Optional[str]:
        """Safely read file content."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.warnings.append(f"Failed to read {file_path}: {e}")
            return None

