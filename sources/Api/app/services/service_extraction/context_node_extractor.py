"""Extract context nodes (README, Dockerfile, project files) for architecture visualization."""

import logging
from pathlib import Path
from typing import Optional

from app.domain.models.services import ContextNode, ContextNodeType

logger = logging.getLogger(__name__)


# Mapping of file patterns to context node types
CONTEXT_FILE_PATTERNS = {
    ContextNodeType.README: ["README.md", "README.rst", "README.txt", "README"],
    ContextNodeType.DOCKERFILE: ["Dockerfile", "Dockerfile.prod", "Dockerfile.dev"],
    ContextNodeType.DOCKER_COMPOSE: ["docker-compose.yml", "docker-compose.yaml", "compose.yml"],
    ContextNodeType.REQUIREMENTS: ["requirements.txt", "requirements-dev.txt", "pyproject.toml"],
    ContextNodeType.PACKAGE_JSON: ["package.json"],
    ContextNodeType.CSPROJ: ["*.csproj"],
    ContextNodeType.GEMFILE: ["Gemfile", "Gemfile.lock"],
    ContextNodeType.GO_MOD: ["go.mod", "go.sum"],
    ContextNodeType.CARGO_TOML: ["Cargo.toml", "Cargo.lock"],
    ContextNodeType.BUILD_GRADLE: ["build.gradle", "build.gradle.kts"],
    ContextNodeType.POM_XML: ["pom.xml"],
    ContextNodeType.APPSETTINGS: ["appsettings.json", "appsettings.*.json"],
}


class ContextNodeExtractor:
    """Extract context nodes from repository for architecture visualization."""
    
    def __init__(self, repo_root: Path):
        """
        Initialize context node extractor.
        
        Args:
            repo_root: Root path of the repository
        """
        self.repo_root = Path(repo_root).resolve()
    
    def extract_context_nodes(
        self,
        service_path: Optional[Path] = None,
        service_id: Optional[str] = None,
    ) -> list[ContextNode]:
        """
        Extract context nodes from a service directory or repository root.
        
        Args:
            service_path: Path to service directory (if None, uses repo root)
            service_id: Associated service ID
        
        Returns:
            List of context nodes found
        """
        context_nodes: list[ContextNode] = []
        
        # Determine search path
        search_path = service_path if service_path else self.repo_root
        if not search_path.exists():
            logger.warning(f"Search path does not exist: {search_path}")
            return context_nodes
        
        # If search_path is a file, use its parent directory
        if search_path.is_file():
            search_path = search_path.parent
        
        logger.info(f"Extracting context nodes from {search_path}")
        
        # Search for each type of context file
        for node_type, patterns in CONTEXT_FILE_PATTERNS.items():
            for pattern in patterns:
                # Handle glob patterns (e.g., *.csproj)
                if "*" in pattern:
                    for file_path in search_path.glob(pattern):
                        if file_path.is_file():
                            node = self._create_context_node(
                                file_path=file_path,
                                node_type=node_type,
                                service_id=service_id,
                            )
                            if node:
                                context_nodes.append(node)
                else:
                    # Direct file match
                    file_path = search_path / pattern
                    if file_path.exists() and file_path.is_file():
                        node = self._create_context_node(
                            file_path=file_path,
                            node_type=node_type,
                            service_id=service_id,
                        )
                        if node:
                            context_nodes.append(node)
        
        logger.info(f"Found {len(context_nodes)} context nodes in {search_path}")
        for node in context_nodes:
            logger.info(f"  - {node.name} ({node.type})")
        
        return context_nodes
    
    def _create_context_node(
        self,
        file_path: Path,
        node_type: ContextNodeType,
        service_id: Optional[str],
    ) -> Optional[ContextNode]:
        """
        Create a context node from a file.
        
        Args:
            file_path: Path to the file
            node_type: Type of context node
            service_id: Associated service ID
        
        Returns:
            ContextNode or None if creation failed
        """
        try:
            # Read file preview (first 500 characters)
            content_preview = None
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content_preview = f.read(500)
            except (OSError, ValueError) as read_error:
                logger.info(f"Could not read {file_path}: {read_error}")
            
            # Get relative path from repo root
            try:
                relative_path = file_path.relative_to(self.repo_root)
            except ValueError:
                relative_path = file_path
            
            # Create unique ID
            node_id = f"context-{node_type.value}-{file_path.name.replace('.', '-')}"
            if service_id:
                node_id = f"{service_id}-{node_id}"
            
            node = ContextNode(
                id=node_id,
                name=file_path.name,
                type=node_type,
                file_path=str(relative_path),
                content_preview=content_preview,
                service_id=service_id,
                attributes={
                    "size_bytes": file_path.stat().st_size,
                    "full_path": str(file_path),
                },
            )
            
            logger.info(f"Created context node: {node.name} ({node.type})")
            return node
        
        except Exception as e:
            logger.error(f"Failed to create context node for {file_path}: {e}", exc_info=True)
            return None
