"""Service extractor that identifies services from code and configuration files."""

import logging
import re
import yaml
import json
from pathlib import Path
from typing import Any, Optional

from app.domain.models.services import Service, ServiceStatus, ServiceTier
from app.domain.models.code_entities import CodeEntity, CodeEntityType, SourceType
from app.services.service_extraction.extraction_config import ExtractionConfig
from app.services.service_extraction.domain_extractor import DomainExtractor
from app.services.service_extraction.dependency_extractor import DependencyExtractor
from app.services.service_extraction.description_generator import ServiceDescriptionGenerator
from app.services.service_extraction.llm_service_enricher import ServiceLLMEnricher
from app.services.service_extraction.llm_budget import LLMCallBudget
# Import order matters: GitContributorAnalyzer must be imported before GitStatusAnalyzer
# because GitStatusAnalyzer depends on GitContributorAnalyzer
from app.services.service_extraction.git_contributor_analyzer import GitContributorAnalyzer
from app.services.service_extraction.git_status_analyzer import GitStatusAnalyzer

logger = logging.getLogger(__name__)


class ServiceExtractor:
    """Extract services from repository code and configuration files."""
    
    def __init__(self, repo_root: Path, llm_manager: Optional[Any] = None):
        """
        Initialize service extractor.
        
        Args:
            repo_root: Root path of the repository
            llm_manager: Optional LLMManager for description generation
        """
        self.repo_root = Path(repo_root).resolve()
        self.services: list[Service] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.git_analyzer = GitStatusAnalyzer(self.repo_root)
        self.contributor_analyzer = GitContributorAnalyzer(self.repo_root)
        self.domain_extractor = DomainExtractor(self.repo_root)
        self.dependency_extractor: Optional[DependencyExtractor] = None
        self.llm_manager = llm_manager
        self.llm_budget: Optional[LLMCallBudget] = None
        if llm_manager and getattr(ExtractionConfig, 'LLM_BUDGET_TOKENS', 0) > 0:
            self.llm_budget = LLMCallBudget(getattr(ExtractionConfig, 'LLM_BUDGET_TOKENS', 0))
        self.description_generator = ServiceDescriptionGenerator(
            llm_manager=llm_manager,
            max_tokens=ExtractionConfig.LLM_MAX_TOKENS,
            budget=self.llm_budget,
        )
        self.llm_enricher = (
            ServiceLLMEnricher(
                llm_manager=llm_manager,
                max_tokens=ExtractionConfig.LLM_MAX_TOKENS,
                budget=self.llm_budget,
            )
            if llm_manager
            else None
        )
    
    def extract_services(self) -> list[Service]:
        """
        Extract all services from the repository.
        
        Returns:
            List of extracted services
        """
        self.services = []
        self.errors = []
        self.warnings = []
        
        logger.info(f"Starting service extraction from {self.repo_root}")
        
        try:
            logger.info("Step 1/6: Extracting from docker-compose files...")
            self._extract_from_docker_compose()
            logger.info(f"After docker-compose: {len(self.services)} services found")
        except Exception as e:
            logger.error(f"Error in _extract_from_docker_compose: {e}", exc_info=True)
            self.errors.append(f"docker-compose extraction failed: {str(e)}")
        
        try:
            logger.info("Step 2/6: Extracting from Kubernetes manifests...")
            self._extract_from_kubernetes()
            logger.info(f"After kubernetes: {len(self.services)} services found")
        except Exception as e:
            logger.error(f"Error in _extract_from_kubernetes: {e}", exc_info=True)
            self.errors.append(f"kubernetes extraction failed: {str(e)}")
        
        try:
            logger.info("Step 3/6: Extracting from API route files...")
            self._extract_from_api_routes()
            logger.info(f"After API routes: {len(self.services)} services found")
        except Exception as e:
            logger.error(f"Error in _extract_from_api_routes: {e}", exc_info=True)
            self.errors.append(f"API routes extraction failed: {str(e)}")
        
        try:
            logger.info("Step 4/6: Extracting from service configuration files...")
            self._extract_from_service_configs()
            logger.info(f"After service configs: {len(self.services)} services found")
        except Exception as e:
            logger.error(f"Error in _extract_from_service_configs: {e}", exc_info=True)
            self.errors.append(f"service configs extraction failed: {str(e)}")
        
        try:
            logger.info("Step 5/6: Extracting from microservice patterns...")
            self._extract_from_microservice_patterns()
            logger.info(f"After microservice patterns: {len(self.services)} services found")
        except Exception as e:
            logger.error(f"Error in _extract_from_microservice_patterns: {e}", exc_info=True)
            self.errors.append(f"microservice patterns extraction failed: {str(e)}")
        
        try:
            logger.info("Step 6/6: Extracting from top-level directories...")
            self._extract_from_top_level_directories()
            logger.info(f"After top-level directories: {len(self.services)} services found")
        except Exception as e:
            logger.error(f"Error in _extract_from_top_level_directories: {e}", exc_info=True)
            self.errors.append(f"top-level directories extraction failed: {str(e)}")
        
        # Enhance with git history analysis for status
        if ExtractionConfig.ENABLE_GIT_ANALYSIS:
            try:
                logger.info("Enhancing with git status analysis...")
                self._enhance_with_git_status()
                logger.info("Git status enhancement completed")
            except Exception as e:
                logger.error(f"Error in _enhance_with_git_status: {e}", exc_info=True)
                self.errors.append(f"git status enhancement failed: {str(e)}")
        
        # Infer domain from imports/namespaces
        if ExtractionConfig.ENABLE_DOMAIN_DETECTION:
            try:
                logger.info("Enhancing with domain detection...")
                self._enhance_with_domain_detection()
                logger.info("Domain detection enhancement completed")
            except Exception as e:
                logger.error(f"Error in _enhance_with_domain_detection: {e}", exc_info=True)
                self.errors.append(f"domain detection enhancement failed: {str(e)}")
        
        # Populate direct dependencies from imports
        if ExtractionConfig.ENABLE_DEPENDENCY_SCAN:
            try:
                logger.info("Enhancing with dependency scan...")
                self._enhance_with_dependencies()
                logger.info("Dependency scan enhancement completed")
            except Exception as e:
                logger.error(f"Error in _enhance_with_dependencies: {e}", exc_info=True)
                self.errors.append(f"dependency scan enhancement failed: {str(e)}")
        
        # Generate short descriptions via LLM (optional)
        enable_llm = getattr(ExtractionConfig, 'ENABLE_LLM_DESCRIPTIONS', False)
        enable_llm_labels = getattr(ExtractionConfig, 'ENABLE_LLM_LABELS', False)
        # #region agent log
        logger.info(f"LLM enrichment check: enable_llm_labels={enable_llm_labels}, llm_enricher={self.llm_enricher is not None}, llm_manager={self.llm_manager is not None}")
        # #endregion
        
        # Check if LLM is available before attempting enrichment (to avoid hanging)
        llm_available = False
        if enable_llm_labels or enable_llm:
            try:
                if self.llm_manager:
                    # Quick connectivity check with 2 second timeout
                    import requests
                    if hasattr(self.llm_manager, 'base_url'):
                        base_url = str(self.llm_manager.base_url).rstrip("/")
                        if base_url.endswith("/v1"):
                            test_url = f"{base_url}/models"
                        else:
                            test_url = f"{base_url}/v1/models"
                        try:
                            headers = {}
                            if getattr(self.llm_manager, "use_openai", False) and getattr(self.llm_manager, "openai_api_key", None):
                                headers["Authorization"] = f"Bearer {self.llm_manager.openai_api_key}"
                            response = requests.get(test_url, headers=headers, timeout=2)
                            if headers:
                                llm_available = response.status_code == 200
                            else:
                                llm_available = response.status_code in [200, 401, 403]
                        except Exception:
                            llm_available = False
                    else:
                        llm_available = False
            except Exception as e:
                logger.warning(f"LLM availability check failed: {e}, skipping LLM enrichment")
                llm_available = False
        
        if enable_llm_labels:
            try:
                if not llm_available:
                    logger.warning("LLM labels enabled but models probe failed; attempting enrichment anyway - LLM may not be reachable")
                if not self.llm_enricher:
                    logger.error("LLM labels enabled but llm_enricher is None - LLM manager was not initialized")
                else:
                    logger.info("Enhancing with LLM labels...")
                    self._enhance_with_llm_enrichment()
                logger.info("LLM labels enhancement completed")
            except Exception as e:
                logger.error(f"Error in _enhance_with_llm_enrichment: {e}", exc_info=True)
                self.errors.append(f"LLM labels enhancement failed: {str(e)}")
        elif enable_llm_labels and not llm_available:
            logger.info("Skipping LLM labels enrichment - LLM not available")
        
        if enable_llm and llm_available:
            try:
                logger.info("Enhancing with LLM descriptions...")
                self._enhance_with_descriptions()
                logger.info("LLM descriptions enhancement completed")
            except Exception as e:
                logger.error(f"Error in _enhance_with_descriptions: {e}", exc_info=True)
                self.errors.append(f"LLM descriptions enhancement failed: {str(e)}")
        elif enable_llm and not llm_available:
            logger.info("Skipping LLM descriptions enrichment - LLM not available")
        
        logger.info(f"Extraction completed: {len(self.services)} services extracted, {len(self.errors)} errors, {len(self.warnings)} warnings")
        
        return self.services
    
    def _extract_from_docker_compose(self) -> None:
        """Extract services from docker-compose files."""
        compose_files = list(self.repo_root.rglob('docker-compose*.yml')) + \
                       list(self.repo_root.rglob('docker-compose*.yaml')) + \
                       list(self.repo_root.rglob('compose.yml')) + \
                       list(self.repo_root.rglob('compose.yaml'))
        
        for compose_file in compose_files:
            try:
                with open(compose_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    compose_data = yaml.safe_load(content)
                
                if not compose_data or 'services' not in compose_data:
                    continue
                
                rel_path = str(compose_file.relative_to(self.repo_root))
                
                for service_name, service_config in compose_data.get('services', {}).items():
                    # Skip if service already exists
                    if any(s.name == service_name for s in self.services):
                        continue
                    
                    service_id = f"svc-{service_name}"
                    
                    # Get labels and environment for metadata extraction
                    labels = service_config.get('labels', {})
                    if isinstance(labels, list):
                        labels = {item.split('=')[0]: item.split('=')[1] if '=' in item else None 
                                  for item in labels if isinstance(item, str)}
                    
                    env = service_config.get('environment', {})
                    if isinstance(env, list):
                        env = {item.split('=')[0]: item.split('=')[1] if '=' in item else None 
                               for item in env if isinstance(item, str)}
                    
                    # ═══════════════════════════════════════════════════════════
                    # EXTRACT THE 5 PRIMARY FIELDS
                    # ═══════════════════════════════════════════════════════════
                    
                    # 1. DOMAIN - Business area
                    domain = self._extract_field_value(
                        labels, env, service_config,
                        ['domain', 'business_domain', 'service_domain', 'area']
                    )
                    
                    # 2. OWNER - Squad/team
                    owner = self._extract_field_value(
                        labels, env, service_config,
                        ['owner', 'team', 'squad', 'maintainer', 'owners']
                    )
                    
                    # 3. STATUS - Lifecycle stage
                    status = self._extract_status(labels, env, service_config)
                    
                    # 4. TIER - Criticality
                    tier = self._extract_tier(labels, env, service_config)
                    
                    # 5. DATA_CLASS - Data sensitivity
                    data_class = self._extract_field_value(
                        labels, env, service_config,
                        ['data_class', 'dataClass', 'data-class', 'data_classification', 
                         'sensitivity', 'data_sensitivity', 'pii_level']
                    )
                    
                    service = Service(
                        id=service_id,
                        name=service_name,
                        display_name=service_name.replace('-', ' ').replace('_', ' ').title(),
                        domain=domain,
                        owner=owner,
                        status=status,
                        tier=tier,
                        data_class=data_class,
                        docker_compose_service=service_name,
                        file_path=rel_path,
                        source='docker_compose',
                    )
                    
                    self.services.append(service)
            
            except Exception as e:
                error_msg = f"Failed to extract from {compose_file}: {e}"
                self.errors.append(error_msg)
                logger.error(error_msg, exc_info=True)
    
    def _extract_from_kubernetes(self) -> None:
        """Extract services from Kubernetes manifests."""
        # Limit search to avoid hanging on large repos - only check common k8s locations
        k8s_patterns = [
            '**/k8s/**/*.yaml',
            '**/k8s/**/*.yml',
            '**/kubernetes/**/*.yaml',
            '**/kubernetes/**/*.yml',
            '**/manifests/**/*.yaml',
            '**/manifests/**/*.yml',
            '*.yaml',  # Root level only
            '*.yml',   # Root level only
        ]
        k8s_files = []
        for pattern in k8s_patterns:
            try:
                k8s_files.extend(list(self.repo_root.glob(pattern))[:50])  # Limit per pattern
            except Exception as e:
                logger.warning(f"Error searching for k8s files with pattern {pattern}: {e}")
        
        # Remove duplicates while preserving order
        seen = set()
        k8s_files = [f for f in k8s_files if f not in seen and not seen.add(f)]
        k8s_files = k8s_files[:200]  # Overall limit to prevent hangs
        
        for k8s_file in k8s_files:
            # Skip docker-compose files
            if 'docker-compose' in k8s_file.name.lower() or 'compose' in k8s_file.name.lower():
                continue
            
            try:
                with open(k8s_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    k8s_data = yaml.safe_load(content)
                
                if not k8s_data:
                    continue
                
                kind = k8s_data.get('kind', '').lower()
                
                # Extract from Service resources
                if kind == 'service':
                    metadata = k8s_data.get('metadata', {})
                    service_name = metadata.get('name', '')
                    
                    if not service_name or any(s.name == service_name for s in self.services):
                        continue
                    
                    spec = k8s_data.get('spec', {})
                    ports = spec.get('ports', [])
                    port = None
                    if ports:
                        port = ports[0].get('port')
                    
                    service_id = f"svc-{service_name}"
                    rel_path = str(k8s_file.relative_to(self.repo_root))
                    
                    # Get annotations and labels for metadata extraction
                    annotations = metadata.get('annotations', {})
                    labels_dict = metadata.get('labels', {})
                    combined = {**labels_dict, **annotations}  # Annotations take precedence
                    
                    # Extract the 5 primary fields
                    domain = self._extract_field_value(combined, {}, {}, ['domain', 'business_domain', 'area'])
                    owner = self._extract_field_value(combined, {}, {}, ['owner', 'team', 'squad', 'maintainer'])
                    status = self._extract_status(combined, {}, {})
                    tier = self._extract_tier(combined, {}, {})
                    data_class = self._extract_field_value(combined, {}, {}, ['data_class', 'dataClass', 'data-class', 'sensitivity'])
                    
                    service = Service(
                        id=service_id,
                        name=service_name,
                        display_name=service_name.replace('-', ' ').title(),
                        domain=domain,
                        owner=owner,
                        status=status,
                        tier=tier,
                        data_class=data_class,
                        port=port,
                        file_path=rel_path,
                        source='kubernetes',
                    )
                    
                    self.services.append(service)
                
                # Extract from Deployment resources
                elif kind == 'deployment':
                    metadata = k8s_data.get('metadata', {})
                    service_name = metadata.get('name', '')
                    
                    if not service_name:
                        continue
                    
                    # Check if service already exists, if not create from deployment
                    if not any(s.name == service_name for s in self.services):
                        service_id = f"svc-{service_name}"
                        rel_path = str(k8s_file.relative_to(self.repo_root))
                        
                        # Get annotations and labels for metadata extraction
                        annotations = metadata.get('annotations', {})
                        labels_dict = metadata.get('labels', {})
                        combined = {**labels_dict, **annotations}
                        
                        # Extract the 5 primary fields
                        domain = self._extract_field_value(combined, {}, {}, ['domain', 'business_domain', 'area'])
                        owner = self._extract_field_value(combined, {}, {}, ['owner', 'team', 'squad', 'maintainer'])
                        status = self._extract_status(combined, {}, {})
                        tier = self._extract_tier(combined, {}, {})
                        data_class = self._extract_field_value(combined, {}, {}, ['data_class', 'dataClass', 'data-class', 'sensitivity'])
                        
                        service = Service(
                            id=service_id,
                            name=service_name,
                            display_name=service_name.replace('-', ' ').title(),
                            domain=domain,
                            owner=owner,
                            status=status,
                            tier=tier,
                            data_class=data_class,
                            file_path=rel_path,
                            source='kubernetes_deployment',
                        )
                        
                        self.services.append(service)
            
            except yaml.YAMLError:
                # Not a YAML file or invalid YAML, skip
                continue
            except Exception as e:
                error_msg = f"Failed to extract from {k8s_file}: {e}"
                self.errors.append(error_msg)
                logger.debug(error_msg)
    
    def _extract_from_api_routes(self) -> None:
        """Extract services from API route files (FastAPI, Express, etc.)."""
        # Look for common API route patterns
        route_patterns = [
            '**/routes/**/*.py',
            '**/routes/**/*.js',
            '**/routes/**/*.ts',
            '**/endpoint/**/*.py',
            '**/api/**/*.py',
            '**/api/**/*.js',
            '**/api/**/*.ts',
            '**/controllers/**/*.py',
            '**/controllers/**/*.js',
            '**/controllers/**/*.ts',
        ]
        
        route_files = []
        for pattern in route_patterns:
            route_files.extend(self.repo_root.glob(pattern))
        
        # Group by directory to identify services
        service_dirs: dict[str, list[Path]] = {}
        
        for route_file in route_files:
            # Try to identify service from directory structure
            parts = route_file.parts
            repo_parts = self.repo_root.parts
            
            # Find service directory (usually one level above routes/endpoint/api)
            for i, part in enumerate(parts):
                if part in ['routes', 'endpoint', 'api', 'controllers']:
                    if i > 0:
                        service_dir = Path(*parts[:i])
                        service_name = parts[i-1] if i > len(repo_parts) else 'api'
                        
                        if service_name not in service_dirs:
                            service_dirs[service_name] = []
                        service_dirs[service_name].append(route_file)
                        break
        
        # Create services from identified directories
        for service_name, files in service_dirs.items():
            if any(s.name == service_name for s in self.services):
                continue
            
            # Try to extract port and other info from files
            port = None
            framework = None
            
            for file_path in files[:3]:  # Check first few files
                content = self._safe_read_file(file_path)
                if not content:
                    continue
                
                # Look for port definitions
                port_match = re.search(r'port\s*[=:]\s*(\d+)', content, re.IGNORECASE)
                if port_match:
                    try:
                        port = int(port_match.group(1))
                    except ValueError:
                        pass
                
                # Detect framework
                if 'fastapi' in content.lower() or 'from fastapi' in content.lower():
                    framework = 'FastAPI'
                elif 'express' in content.lower() or 'require.*express' in content.lower():
                    framework = 'Express'
                elif 'flask' in content.lower() or 'from flask' in content.lower():
                    framework = 'Flask'
                elif 'django' in content.lower():
                    framework = 'Django'
            
            service_id = f"svc-{service_name}"
            rel_path = str(files[0].relative_to(self.repo_root).parent) if files else None
            
            # Try to extract status and data_class from code files
            status = ServiceStatus.UNKNOWN
            data_class = None
            
            # Extract all 5 primary fields from code files
            domain = None
            owner = None
            status = ServiceStatus.UNKNOWN
            tier = ServiceTier.UNKNOWN
            data_class = None
            
            for file_path in files[:5]:  # Check first few files
                content = self._safe_read_file(file_path)
                if not content:
                    continue
                
                # Try to extract all 5 fields from code comments and config
                field_patterns = {
                    'domain': r'domain\s*[=:]\s*["\']?([^"\'\s,\n]+)["\']?',
                    'owner': r'(?:owner|team|squad)\s*[=:]\s*["\']?([^"\'\s,\n]+)["\']?',
                    'status': r'status\s*[=:]\s*["\']?([^"\'\s,\n]+)["\']?',
                    'tier': r'(?:tier|criticality)\s*[=:]\s*["\']?([^"\'\s,\n]+)["\']?',
                    'data_class': r'data_class\s*[=:]\s*["\']?([^"\'\s,\n]+)["\']?',
                }
                
                for field_name, pattern in field_patterns.items():
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        value = match.group(1)
                        if field_name == 'domain' and not domain:
                            domain = value
                        elif field_name == 'owner' and not owner:
                            owner = value
                        elif field_name == 'status' and status == ServiceStatus.UNKNOWN:
                            status = self._extract_status({'status': value}, {}, {})
                        elif field_name == 'tier' and tier == ServiceTier.UNKNOWN:
                            tier = self._extract_tier({'tier': value}, {}, {})
                        elif field_name == 'data_class' and not data_class:
                            data_class = value
            
            service = Service(
                id=service_id,
                name=service_name,
                display_name=service_name.replace('-', ' ').replace('_', ' ').title(),
                domain=domain,
                owner=owner,
                status=status,
                tier=tier,
                data_class=data_class,
                port=port,
                file_path=rel_path,
                source='api_routes',
            )
            
            self.services.append(service)
    
    def _extract_from_service_configs(self) -> None:
        """Extract services from service configuration files."""
        # Look for service configuration files
        config_patterns = [
            '**/service*.yml',
            '**/service*.yaml',
            '**/service*.json',
            '**/services.yml',
            '**/services.yaml',
        ]
        
        config_files = []
        for pattern in config_patterns:
            config_files.extend(self.repo_root.glob(pattern))
        
        for config_file in config_files:
            try:
                content = self._safe_read_file(config_file)
                if not content:
                    continue
                
                if config_file.suffix in ['.yml', '.yaml']:
                    data = yaml.safe_load(content)
                elif config_file.suffix == '.json':
                    data = json.loads(content)
                else:
                    continue
                
                if not isinstance(data, dict):
                    continue
                
                rel_path = str(config_file.relative_to(self.repo_root))
                
                # Handle different config formats
                services_data = data.get('services', data)
                
                if isinstance(services_data, dict):
                    for service_name, service_config in services_data.items():
                        if any(s.name == service_name for s in self.services):
                            continue
                        
                        if isinstance(service_config, dict):
                            service_id = f"svc-{service_name}"
                            
                            # Extract the 5 primary fields using helper methods
                            domain = self._extract_field_value({}, {}, service_config, ['domain', 'business_domain', 'area'])
                            owner = self._extract_field_value({}, {}, service_config, ['owner', 'team', 'squad', 'maintainer'])
                            status = self._extract_status({}, {}, service_config)
                            tier = self._extract_tier({}, {}, service_config)
                            data_class = self._extract_field_value({}, {}, service_config, ['data_class', 'dataClass', 'data-class', 'sensitivity'])
                            
                            service = Service(
                                id=service_id,
                                name=service_name,
                                display_name=service_config.get('display_name') or service_name.replace('-', ' ').title(),
                                domain=domain,
                                owner=owner,
                                status=status,
                                tier=tier,
                                data_class=data_class,
                                file_path=rel_path,
                                source='service_config',
                            )
                            
                            self.services.append(service)
            
            except Exception as e:
                error_msg = f"Failed to extract from {config_file}: {e}"
                self.errors.append(error_msg)
                logger.debug(error_msg)
    
    def _extract_from_microservice_patterns(self) -> None:
        """Extract services from microservice directory patterns."""
        # Look for common microservice directory patterns
        # e.g., services/, microservices/, apps/, packages/
        service_dirs = [
            'services',
            'microservices',
            'apps',
            'packages',
            'modules',
        ]
        
        for service_dir_name in service_dirs:
            service_dir = self.repo_root / service_dir_name
            if not service_dir.exists() or not service_dir.is_dir():
                continue
            
            # Each subdirectory might be a service
            for subdir in service_dir.iterdir():
                if not subdir.is_dir():
                    continue
                
                service_name = subdir.name
                
                # Skip common non-service directories
                if service_name in ['.git', 'node_modules', '__pycache__', '.venv', 'venv']:
                    continue
                
                if any(s.name == service_name for s in self.services):
                    continue
                
                # Check if it looks like a service (has package.json, requirements.txt, etc.)
                has_service_files = any(
                    (subdir / f).exists()
                    for f in ['package.json', 'requirements.txt', 'pyproject.toml', 'Dockerfile', 'main.py', 'app.py', 'server.js', 'index.js']
                )
                
                if has_service_files:
                    service_id = f"svc-{service_name}"
                    rel_path = str(subdir.relative_to(self.repo_root))
                    
                    # Try to detect language and framework
                    language = None
                    framework = None
                    
                    if (subdir / 'package.json').exists():
                        language = 'JavaScript'
                        try:
                            with open(subdir / 'package.json', 'r') as f:
                                pkg_data = json.load(f)
                                deps = {**pkg_data.get('dependencies', {}), **pkg_data.get('devDependencies', {})}
                                if 'express' in deps:
                                    framework = 'Express'
                                elif 'fastify' in deps:
                                    framework = 'Fastify'
                        except Exception:
                            pass
                    elif (subdir / 'requirements.txt').exists() or (subdir / 'pyproject.toml').exists():
                        language = 'Python'
                    
                    # Try to extract the 5 primary fields from config files
                    domain = None
                    owner = None
                    status = ServiceStatus.UNKNOWN
                    tier = ServiceTier.UNKNOWN
                    data_class = None
                    
                    # Check package.json, pyproject.toml, or config files
                    config_file_paths = [
                        subdir / 'package.json',
                        subdir / 'pyproject.toml',
                        subdir / 'config.json',
                        subdir / 'service.json',
                        subdir / 'service.yaml',
                        subdir / 'service.yml',
                    ]
                    
                    for config_file_path in config_file_paths:
                        if config_file_path.exists():
                            content = self._safe_read_file(config_file_path)
                            if not content:
                                continue
                            
                            try:
                                if config_file_path.suffix == '.json':
                                    config_data = json.loads(content)
                                elif config_file_path.suffix in ['.yaml', '.yml']:
                                    config_data = yaml.safe_load(content)
                                else:
                                    continue
                                
                                if isinstance(config_data, dict):
                                    # Extract all 5 fields
                                    domain = domain or self._extract_field_value({}, {}, config_data, ['domain', 'business_domain', 'area'])
                                    owner = owner or self._extract_field_value({}, {}, config_data, ['owner', 'team', 'squad', 'maintainer'])
                                    if status == ServiceStatus.UNKNOWN:
                                        status = self._extract_status({}, {}, config_data)
                                    if tier == ServiceTier.UNKNOWN:
                                        tier = self._extract_tier({}, {}, config_data)
                                    data_class = data_class or self._extract_field_value({}, {}, config_data, ['data_class', 'dataClass', 'data-class', 'sensitivity'])
                            except Exception:
                                pass
                    
                    service = Service(
                        id=service_id,
                        name=service_name,
                        display_name=service_name.replace('-', ' ').replace('_', ' ').title(),
                        domain=domain,
                        owner=owner,
                        status=status,
                        tier=tier,
                        data_class=data_class,
                        language=language,
                        file_path=rel_path,
                        source='microservice_pattern',
                    )
                    
                    self.services.append(service)
    
    def _extract_from_top_level_directories(self) -> None:
        """
        Extract services from top-level directories (for monorepos like Django, addons, etc.).
        
        This looks for directories at the repo root that could be services/modules,
        such as 'addons', 'admin', 'campaigns', 'core', etc.
        """
        logger.info("Extracting services from top-level directories")
        
        # Common non-service directories to skip
        skip_dirs = {
            '.git', '.github', '.vscode', '.idea', 'node_modules', '__pycache__',
            '.venv', 'venv', 'env', '.env', 'dist', 'build', 'target', 'out',
            'docs', 'documentation', 'tests', 'test', 'testing', 'spec', 'specs',
            'scripts', 'tools', 'utils', 'utilities', 'migrations', 'locale',
            'static', 'assets', 'media', 'public', 'resources', 'config', 'conf',
            'settings', 'deploy', 'deployment', 'ci', '.circleci', '.travis',
            'examples', 'sample', 'samples', 'demo', 'demos', 'tmp', 'temp',
            'log', 'logs', 'var', 'cache', '.cache', 'coverage', '.coverage',
            'vendor', 'lib', 'libs', 'third_party', 'third-party', 'external'
        }
        
        # Look for top-level directories
        for item in self.repo_root.iterdir():
            if not item.is_dir():
                continue
            
            dir_name = item.name
            
            # Skip hidden directories and known non-service dirs
            if dir_name.startswith('.') or dir_name.lower() in skip_dirs:
                continue
            
            # Skip if already extracted
            if any(s.name == dir_name for s in self.services):
                continue
            
            # Check if it looks like a service/module (has Python package files, Django app files, etc.)
            service_indicators = [
                '__init__.py',  # Python package
                'apps.py',      # Django app
                'models.py',    # Django models
                'views.py',     # Django views
                'urls.py',      # Django URLs
                'package.json', # Node.js package
                'setup.py',     # Python package setup
                'pyproject.toml', # Python project
                'Dockerfile',   # Containerized service
                'service.yml',  # Service config
                'service.yaml', # Service config
                'main.py',      # Python entry point
                'app.py',       # Python app
                'index.js',     # Node.js entry point
                'server.js',    # Node.js server
            ]
            
            has_service_files = any((item / indicator).exists() for indicator in service_indicators)
            
            # Also check if it's a Python package (has __init__.py in subdirectories)
            # Limit search depth to avoid hanging on large repos - only check immediate subdirs
            if not has_service_files:
                try:
                    # Only check immediate subdirectories, not full recursive search
                    for subdir in item.iterdir():
                        if subdir.is_dir() and (subdir / '__init__.py').exists():
                            has_service_files = True
                            break
                except (PermissionError, OSError) as e:
                    logger.warning(f"Error checking subdirectories in {item}: {e}")
                    # Continue without this check if we can't access the directory
            
            if has_service_files:
                service_id = f"svc-{dir_name}"
                rel_path = str(item.relative_to(self.repo_root))
                
                # Try to detect language and framework
                language = None
                framework = None
                
                if (item / '__init__.py').exists() or (item / 'setup.py').exists() or (item / 'pyproject.toml').exists():
                    language = 'Python'
                    # Check for Django
                    if (item / 'apps.py').exists() or (item / 'models.py').exists():
                        framework = 'Django'
                    # Check for Flask
                    elif (item / 'app.py').exists():
                        try:
                            content = self._safe_read_file(item / 'app.py')
                            if content and ('from flask' in content.lower() or 'Flask(' in content):
                                framework = 'Flask'
                        except Exception:
                            pass
                elif (item / 'package.json').exists():
                    language = 'JavaScript'
                    try:
                        with open(item / 'package.json', 'r') as f:
                            pkg_data = json.load(f)
                            deps = {**pkg_data.get('dependencies', {}), **pkg_data.get('devDependencies', {})}
                            if 'django' in deps or 'djangorestframework' in deps:
                                framework = 'Django'
                            elif 'express' in deps:
                                framework = 'Express'
                            elif 'fastify' in deps:
                                framework = 'Fastify'
                            elif 'react' in deps:
                                framework = 'React'
                    except Exception:
                        pass
                
                # Try to extract the 5 primary fields from config files
                domain = None
                owner = None
                status = ServiceStatus.UNKNOWN
                tier = ServiceTier.UNKNOWN
                data_class = None
                
                # Check various config files
                config_file_paths = [
                    item / 'package.json',
                    item / 'pyproject.toml',
                    item / 'setup.py',
                    item / 'config.json',
                    item / 'service.json',
                    item / 'service.yaml',
                    item / 'service.yml',
                    item / '__init__.py',  # Check for metadata in Python package
                ]
                
                for config_file_path in config_file_paths:
                    if config_file_path.exists():
                        content = self._safe_read_file(config_file_path)
                        if not content:
                            continue
                        
                        try:
                            if config_file_path.suffix == '.json':
                                config_data = json.loads(content)
                                if isinstance(config_data, dict):
                                    domain = domain or self._extract_field_value({}, {}, config_data, ['domain', 'business_domain', 'area'])
                                    owner = owner or self._extract_field_value({}, {}, config_data, ['owner', 'team', 'squad', 'maintainer'])
                                    if status == ServiceStatus.UNKNOWN:
                                        status = self._extract_status({}, {}, config_data)
                                    if tier == ServiceTier.UNKNOWN:
                                        tier = self._extract_tier({}, {}, config_data)
                                    data_class = data_class or self._extract_field_value({}, {}, config_data, ['data_class', 'dataClass', 'data-class', 'sensitivity'])
                            elif config_file_path.suffix in ['.yaml', '.yml']:
                                config_data = yaml.safe_load(content)
                                if isinstance(config_data, dict):
                                    domain = domain or self._extract_field_value({}, {}, config_data, ['domain', 'business_domain', 'area'])
                                    owner = owner or self._extract_field_value({}, {}, config_data, ['owner', 'team', 'squad', 'maintainer'])
                                    if status == ServiceStatus.UNKNOWN:
                                        status = self._extract_status({}, {}, config_data)
                                    if tier == ServiceTier.UNKNOWN:
                                        tier = self._extract_tier({}, {}, config_data)
                                    data_class = data_class or self._extract_field_value({}, {}, config_data, ['data_class', 'dataClass', 'data-class', 'sensitivity'])
                            elif config_file_path.name == '__init__.py':
                                # Try to extract from Python docstrings or comments
                                field_patterns = {
                                    'domain': r'domain\s*[=:]\s*["\']?([^"\'\s,\n]+)["\']?',
                                    'owner': r'(?:owner|team|squad)\s*[=:]\s*["\']?([^"\'\s,\n]+)["\']?',
                                    'status': r'status\s*[=:]\s*["\']?([^"\'\s,\n]+)["\']?',
                                    'tier': r'(?:tier|criticality)\s*[=:]\s*["\']?([^"\'\s,\n]+)["\']?',
                                    'data_class': r'data_class\s*[=:]\s*["\']?([^"\'\s,\n]+)["\']?',
                                }
                                for field_name, pattern in field_patterns.items():
                                    match = re.search(pattern, content, re.IGNORECASE)
                                    if match:
                                        value = match.group(1)
                                        if field_name == 'domain' and not domain:
                                            domain = value
                                        elif field_name == 'owner' and not owner:
                                            owner = value
                                        elif field_name == 'status' and status == ServiceStatus.UNKNOWN:
                                            status = self._extract_status({'status': value}, {}, {})
                                        elif field_name == 'tier' and tier == ServiceTier.UNKNOWN:
                                            tier = self._extract_tier({'tier': value}, {}, {})
                                        elif field_name == 'data_class' and not data_class:
                                            data_class = value
                        except Exception:
                            pass
                
                service = Service(
                    id=service_id,
                    name=dir_name,
                    display_name=dir_name.replace('-', ' ').replace('_', ' ').title(),
                    domain=domain,
                    owner=owner,
                    status=status,
                    tier=tier,
                    data_class=data_class,
                    language=language,
                    framework=framework,
                    file_path=rel_path,
                    source='top_level_directory',
                )
                
                self.services.append(service)
                logger.debug(f"Extracted service from top-level directory: {dir_name}")
    
    def _safe_read_file(self, file_path: Path) -> Optional[str]:
        """Safely read file content."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.warnings.append(f"Failed to read {file_path}: {e}")
            return None
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HELPER METHODS FOR EXTRACTING THE 5 PRIMARY FIELDS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _extract_field_value(
        self,
        labels: dict,
        env: dict,
        config: dict,
        field_names: list[str]
    ) -> Optional[str]:
        """
        Extract a field value from labels, environment, or config.
        Tries multiple possible field names.
        """
        # Try labels first
        if isinstance(labels, dict):
            for name in field_names:
                value = labels.get(name)
                if value:
                    return str(value)
        
        # Try environment variables (uppercase versions)
        if isinstance(env, dict):
            for name in field_names:
                upper_name = name.upper()
                value = env.get(upper_name) or env.get(name)
                if value:
                    return str(value)
        
        # Try config directly
        if isinstance(config, dict):
            for name in field_names:
                value = config.get(name)
                if value:
                    return str(value)
        
        return None
    
    def _extract_status(
        self,
        labels: dict,
        env: dict,
        config: dict
    ) -> ServiceStatus:
        """
        Extract service status from labels, environment, or config.
        
        Maps to: Active-Dev, Maintenance-Only, Deprecated/Frozen
        """
        status_value = self._extract_field_value(
            labels, env, config,
            ['status', 'service_status', 'lifecycle', 'lifecycle_status', 'state']
        )
        
        if not status_value:
            return ServiceStatus.UNKNOWN
        
        status_str = status_value.lower()
        
        # Check for Deprecated / Frozen
        if any(keyword in status_str for keyword in [
            'deprecated', 'sunset', 'retired', 'frozen', 'shutdown', 'legacy', 'end-of-life', 'eol'
        ]):
            return ServiceStatus.DEPRECATED
        
        # Check for Maintenance-Only
        if any(keyword in status_str for keyword in [
            'maintenance', 'maint', 'stable', 'support', 'bugfix', 'sustaining'
        ]):
            return ServiceStatus.MAINTENANCE_ONLY
        
        # Check for Active-Dev
        if any(keyword in status_str for keyword in [
            'active', 'dev', 'development', 'running', 'live', 'production', 'prod'
        ]):
            return ServiceStatus.ACTIVE_DEV
        
        return ServiceStatus.UNKNOWN
    
    def _extract_tier(
        self,
        labels: dict,
        env: dict,
        config: dict
    ) -> ServiceTier:
        """
        Extract service criticality tier from labels, environment, or config.
        
        Maps to: Tier 1 (site-wide), Tier 2 (journey), Tier 3 (minor)
        """
        tier_value = self._extract_field_value(
            labels, env, config,
            ['tier', 'criticality', 'priority', 'sla_tier', 'service_tier', 'severity']
        )
        
        if not tier_value:
            return ServiceTier.UNKNOWN
        
        tier_str = tier_value.lower().strip()
        
        # Check for Tier 1 (critical / site-wide)
        if any(keyword in tier_str for keyword in [
            'tier 1', 'tier1', 't1', 'critical', 'p1', 'p0', 'high', 'site-wide', 'sitewide'
        ]):
            return ServiceTier.TIER_1
        
        # Check for Tier 2 (important / journey-specific)
        if any(keyword in tier_str for keyword in [
            'tier 2', 'tier2', 't2', 'important', 'p2', 'medium', 'journey'
        ]):
            return ServiceTier.TIER_2
        
        # Check for Tier 3 (minor / cosmetic)
        if any(keyword in tier_str for keyword in [
            'tier 3', 'tier3', 't3', 'minor', 'p3', 'low', 'cosmetic'
        ]):
            return ServiceTier.TIER_3
        
        # Try to parse numeric tier
        try:
            tier_num = int(tier_str.replace('tier', '').replace('t', '').strip())
            if tier_num == 1:
                return ServiceTier.TIER_1
            elif tier_num == 2:
                return ServiceTier.TIER_2
            elif tier_num >= 3:
                return ServiceTier.TIER_3
        except ValueError:
            pass
        
        return ServiceTier.UNKNOWN
    
    def _resolve_service_path(self, service: Service) -> Optional[Path]:
        """
        Resolve the filesystem path for a service based on known metadata.
        
        Prefers the recorded file_path; falls back to a directory matching the
        service name if the recorded path is missing.
        """
        if service.file_path:
            potential_path = self.repo_root / service.file_path
            if potential_path.exists():
                return potential_path
            fallback = self.repo_root / service.name
            if fallback.exists() and fallback.is_dir():
                return fallback
        else:
            potential_path = self.repo_root / service.name
            if potential_path.exists() and potential_path.is_dir():
                return potential_path
        return None
    
    def _enhance_with_git_status(self) -> None:
        """
        Enhance service with git history analysis:
        - Owner (from top contributors)
        - Status (from commit patterns)
        - Commit statistics (counts, dates)
        - Status evidence (for debugging)
        """
        if not self.git_analyzer.is_git_repo:
            logger.debug("Not a git repository, skipping git analysis")
            return
        
        logger.info("Enhancing services with git history analysis (owner, status, stats)")
        max_contributors = max(1, ExtractionConfig.GIT_CONTRIBUTOR_LIMIT)
        
        for service in self.services:
            # Try to find service path - prioritize directory path
            service_path = self._resolve_service_path(service)
            
            # ═══════════════════════════════════════════════════════════
            # 1. GET CONTRIBUTOR STATS (owners, commit counts, dates)
            # ═══════════════════════════════════════════════════════════
            contributor_stats = self.contributor_analyzer.analyze_service_contributors(
                service_path=service_path,
                service_name=service.name,
                max_contributors=max_contributors,
            )
            
            if contributor_stats:
                top_contributors = contributor_stats.top_contributors
                if top_contributors:
                    if not service.owner:  # Only if not already set from config
                        # Use name if available, fallback to email
                        top_contributor = top_contributors[0]
                        service.owner = top_contributor.name or top_contributor.email
                        logger.debug(
                            f"Service '{service.name}': extracted owner '{service.owner}' "
                            f"from git (contributors: {len(top_contributors)})"
                        )
                    service.owner_contributors = [contributor.email for contributor in top_contributors]
                    service.owner_contributor_stats = [
                        {
                            "email": contributor.email,
                            "name": contributor.name,
                            "commit_count": contributor.commit_count,
                        }
                        for contributor in top_contributors
                    ]
                service.contributor_count = contributor_stats.unique_contributors

                # Populate commit statistics
                service.last_commit_date = contributor_stats.last_commit_date
                service.commit_count_30d = contributor_stats.commits_30d
                service.commit_count_90d = contributor_stats.commits_90d
                service.commit_count_180d = contributor_stats.commits_180d
                
                # Build status evidence (include recent commit messages for LLM enrichment)
                service.status_evidence = {
                    'total_commits': contributor_stats.total_commits,
                    'commits_30d': contributor_stats.commits_30d,
                    'commits_90d': contributor_stats.commits_90d,
                    'commits_180d': contributor_stats.commits_180d,
                    'feature_commits': contributor_stats.feature_commits,
                    'bugfix_commits': contributor_stats.bugfix_commits,
                    'chore_commits': contributor_stats.chore_commits,
                    'last_commit_date': contributor_stats.last_commit_date.isoformat() if contributor_stats.last_commit_date else None,
                    'first_commit_date': contributor_stats.first_commit_date.isoformat() if contributor_stats.first_commit_date else None,
                    'unique_contributors': contributor_stats.unique_contributors,
                    'top_contributors': [contributor.email for contributor in top_contributors],
                    'top_contributor_stats': [
                        {
                            "email": contributor.email,
                            "name": contributor.name,
                            "commit_count": contributor.commit_count,
                        }
                        for contributor in top_contributors
                    ],
                    'recent_commit_messages': contributor_stats.recent_commit_messages[:10],  # Last 10 for LLM context
                }
            
            # ═══════════════════════════════════════════════════════════
            # 3. ANALYZE STATUS FROM GIT HISTORY
            # ═══════════════════════════════════════════════════════════
            git_status = self.git_analyzer.analyze_service_status(
                service_path=service_path,
                service_name=service.name
            )
            
            # Get detailed activity summary for logging
            activity_summary = self.git_analyzer.get_service_activity_summary(
                service_path=service_path,
                service_name=service.name
            )
            
            # Always use git analysis if available (it's more accurate)
            if git_status != ServiceStatus.UNKNOWN:
                old_status = service.status
                service.status = git_status
                
                if activity_summary:
                    logger.info(
                        f"Service '{service.name}': git analysis -> {git_status.value} "
                        f"(was: {old_status.value}, commits: {activity_summary['total_commits']}, "
                        f"last: {activity_summary['days_since_last']}d ago, "
                        f"recent: {activity_summary['recent_commits_30d']} in 30d)"
                    )
                else:
                    logger.debug(
                        f"Enhanced {service.name} status to {git_status.value} "
                        f"based on git history"
                    )
                
                # Override if git suggests deprecated (more reliable)
                if git_status == ServiceStatus.DEPRECATED:
                    service.status = ServiceStatus.DEPRECATED
                    logger.debug(
                        f"Overrode {service.name} status to Deprecated "
                        f"based on git history (was {service.status.value})"
                    )
                # Override if config says active but git shows maintenance-only pattern
                elif (service.status == ServiceStatus.ACTIVE_DEV and 
                      git_status == ServiceStatus.MAINTENANCE_ONLY):
                    # Check if git analysis is confident (has commit history)
                    activity = self.git_analyzer.get_service_activity_summary(
                        service_path=service_path,
                        service_name=service.name
                    )
                    if activity and activity.get('total_commits', 0) > 5:
                        # Git has enough history to be confident
                        service.status = ServiceStatus.MAINTENANCE_ONLY
                        logger.debug(
                            f"Overrode {service.name} status to Maintenance-Only "
                            f"based on git history (was Active-Dev)"
                        )

    def _enhance_with_domain_detection(self) -> None:
        """Infer domain from imports and namespaces when missing."""
        if not self.services:
            return
        
        logger.info("Enhancing services with domain detection")
        
        for service in self.services:
            if service.domain:
                continue
            
            service_path = self._resolve_service_path(service)
            if not service_path:
                continue
            
            scan_path = service_path if service_path.is_dir() else service_path.parent
            domain = self.domain_extractor.extract_domain(scan_path, service.name)
            if domain:
                service.domain = domain
                logger.debug(f"Service '{service.name}': inferred domain '{domain}' from imports")

    def _enhance_with_dependencies(self) -> None:
        """Populate direct_depends by scanning imports for cross-service references."""
        if not self.services:
            return
        
        logger.info("Scanning for direct service dependencies from imports")
        self.dependency_extractor = DependencyExtractor(self.repo_root, self.services)
        
        for service in self.services:
            deps = self.dependency_extractor.extract_dependencies(service)
            if not deps:
                continue
            
            # Merge with any existing entries
            merged = sorted(set(service.direct_depends or []) | set(deps))
            service.direct_depends = merged
            
            # Also reflect in dependencies/dependents fields
            for dep_id in deps:
                if dep_id not in service.dependencies:
                    service.dependencies.append(dep_id)
                target_service = self.dependency_extractor.service_map.get(dep_id)
                if target_service and service.id not in target_service.dependents:
                    target_service.dependents.append(service.id)
            
            logger.debug(
                f"Service '{service.name}': detected direct dependencies {merged}"
            )
    
    def _enhance_with_descriptions(self) -> None:
        """Generate short descriptions for services."""
        if not self.services or not self.description_generator:
            return
        
        logger.info("Generating service descriptions (LLM flag enabled)")
        
        for service in self.services:
            if service.description:
                continue
            
            service_path = self._resolve_service_path(service)
            if not service_path:
                continue
            
            scan_path = service_path if service_path.is_dir() else service_path.parent
            description = self.description_generator.generate_description(
                service_name=service.name,
                service_path=scan_path,
                language=service.language,
                repo_root=self.repo_root,
            )
            
            if description:
                service.description = description
                logger.debug(f"Service '{service.name}': generated description")

    def _enhance_with_llm_enrichment(self) -> None:
        """Use LLM to fill missing labels and notes."""
        # #region agent log
        logger.info(f"_enhance_with_llm_enrichment called: services={len(self.services) if self.services else 0}, llm_enricher={self.llm_enricher is not None}")
        # #endregion
        if not self.services or not self.llm_enricher:
            # #region agent log
            logger.warning(f"LLM enrichment skipped: services={self.services is not None}, llm_enricher={self.llm_enricher is not None}")
            # #endregion
            return

        logger.info("Enhancing services with LLM labels and notes")
        
        # Track if LLM is working - stop after a hard failure to avoid hanging
        llm_working = True

        for service in self.services:
            if not llm_working:
                break
            # #region agent log
            logger.debug(f"Service '{service.name}': requesting LLM enrichment")
            # #endregion

            service_path = self._resolve_service_path(service)
            if not service_path:
                # #region agent log
                logger.debug(f"Service '{service.name}': no service_path resolved, using repo root")
                # #endregion
                service_path = self.repo_root

            scan_path = service_path if service_path.is_dir() else service_path.parent
            enrichment = {}
            try:
                # Use threading timeout to prevent hanging if LLM is unavailable
                import threading
                result_container = {'enrichment': None, 'error': None, 'completed': False}
                
                def enrich_with_timeout():
                    try:
                        result_container['enrichment'] = self.llm_enricher.enrich_service(
                            service,
                            scan_path,
                            repo_root=self.repo_root,
                        )
                        result_container['completed'] = True
                    except Exception as e:
                        result_container['error'] = e
                        result_container['completed'] = True
                
                thread = threading.Thread(target=enrich_with_timeout)
                thread.daemon = True
                thread.start()
                thread.join(timeout=5)  # 5 second timeout per service (reduced from 10)
                
                if thread.is_alive():
                    logger.warning(f"LLM enrichment timed out for service '{service.name}' after 5 seconds - LLM appears unavailable, skipping remaining services")
                    llm_working = False
                    enrichment = {}
                elif result_container['error']:
                    logger.warning(f"LLM enrichment failed for service '{service.name}': {result_container['error']}")
                    # If it's a connection error, mark LLM as not working
                    if 'connection' in str(result_container['error']).lower() or 'refused' in str(result_container['error']).lower():
                        llm_working = False
                    enrichment = {}
                else:
                    enrichment = result_container['enrichment'] or {}
            except Exception as e:
                logger.warning(f"LLM enrichment error for service '{service.name}': {e}")
                llm_working = False
                enrichment = {}
            
            # #region agent log
            logger.info(f"Service '{service.name}': LLM enrichment result={enrichment}")
            # #endregion
            if not enrichment:
                continue

            inferred = service.attributes.setdefault("inferred_fields", {})

            domain = enrichment.get("domain")
            if domain:
                service.domain = domain
                inferred["domain"] = {"confidence": "low", "source": "llm"}

            owner = enrichment.get("owner")
            if self._is_missing_label(service.owner) and owner:
                service.owner = owner
                inferred["owner"] = {"confidence": "low", "source": "llm"}

            data_class = enrichment.get("data_class")
            if self._is_missing_label(service.data_class) and data_class:
                service.data_class = data_class
                inferred["data_class"] = {"confidence": "low", "source": "llm"}

            status = self._normalize_status_label(enrichment.get("status"))
            if service.status == ServiceStatus.UNKNOWN and status:
                service.status = status
                inferred["status"] = {"confidence": "low", "source": "llm"}

            tier = self._normalize_tier_label(enrichment.get("tier"))
            if service.tier == ServiceTier.UNKNOWN and tier:
                service.tier = tier
                inferred["tier"] = {"confidence": "low", "source": "llm"}

            notes = enrichment.get("notes")
            if notes:
                service.notes = notes
                service.description = notes
                inferred["notes"] = {"confidence": "low", "source": "llm"}

    def _needs_llm_enrichment(self, service: Service) -> bool:
        """Check if service has missing labels or notes."""
        if self._is_missing_label(service.domain):
            return True
        if self._is_missing_label(service.data_class):
            return True
        if service.status == ServiceStatus.UNKNOWN:
            return True
        if service.tier == ServiceTier.UNKNOWN:
            return True
        if not service.description:
            return True
        return False

    def _is_missing_label(self, value: Optional[str]) -> bool:
        """Normalize missing label values."""
        if not value:
            return True
        if not isinstance(value, str):
            return True
        lowered = value.strip().lower()
        return lowered in {"unknown", "unclassified", "none", "n/a", "null"}

    def _normalize_status_label(self, value: Optional[str]) -> Optional[ServiceStatus]:
        if not value:
            return None
        if not isinstance(value, str):
            return None
        lowered = value.strip().lower()
        if not lowered:
            return None
        if any(token in lowered for token in ["deprecat", "sunset", "retire", "frozen", "legacy", "eol"]):
            return ServiceStatus.DEPRECATED
        if any(token in lowered for token in ["maint", "bugfix", "support", "stabil", "patch"]):
            return ServiceStatus.MAINTENANCE_ONLY
        if any(token in lowered for token in ["active", "dev", "feature"]):
            return ServiceStatus.ACTIVE_DEV
        if lowered in {"unknown", "unclassified", "n/a", "null"}:
            return None
        return None

    def _normalize_tier_label(self, value: Optional[str]) -> Optional[ServiceTier]:
        if not value:
            return None
        if not isinstance(value, str):
            return None
        lowered = value.strip().lower()
        if not lowered:
            return None
        if any(token in lowered for token in ["tier 1", "tier1", "t1", "critical", "p0", "p1"]):
            return ServiceTier.TIER_1
        if any(token in lowered for token in ["tier 2", "tier2", "t2", "important", "p2", "medium"]):
            return ServiceTier.TIER_2
        if any(token in lowered for token in ["tier 3", "tier3", "t3", "minor", "p3", "low"]):
            return ServiceTier.TIER_3
        if lowered in {"unknown", "unclassified", "n/a", "null"}:
            return None
        return None
