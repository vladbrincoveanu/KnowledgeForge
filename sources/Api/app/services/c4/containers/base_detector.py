"""Base interface for container detectors."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseContainerDetector(ABC):
    """Abstract base class for container detection strategies."""
    
    def __init__(self, repo_path: Path):
        """Initialize detector.
        
        Args:
            repo_path: Absolute path to repository root
        """
        self.repo_path = Path(repo_path).resolve()
    
    @abstractmethod
    def detect(self) -> list[dict[str, Any]]:
        """Detect containers and return list of container dictionaries.
        
        Returns:
            List of container dictionaries with keys:
                - name: Container name
                - container_type: Type (API, Database, Frontend, etc.)
                - technology: Tech stack (Python, Node.js, etc.)
                - protocol: Communication protocol (HTTP, gRPC, etc.)
                - path: Relative path from repo root
                - runtime_environment: Kubernetes, Docker, etc.
                - deployment: Helm, Kustomize, Manifest, etc.
                - description: Service description
                - repository_url: Git repository URL
                - runtime_info: Runtime version info
                - dependencies_internal: List of internal service names
                - health_endpoint: Health check URL
                - relationships: List of relationship dicts with keys:
                    - target: Target container name
                    - protocol: Communication protocol (HTTP, gRPC, etc.)
                    - metadata: Dict of source-specific details (e.g., port,
                      path, network, Helm values key, K8s resource kind)
        """
        pass
    
    @abstractmethod
    def can_detect(self) -> bool:
        """Check if this detector can find containers in the repository.
        
        Returns:
            True if detection is possible, False otherwise
        """
        pass
