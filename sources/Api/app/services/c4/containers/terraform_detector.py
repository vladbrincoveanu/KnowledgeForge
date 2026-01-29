"""Terraform-based passive container detector."""

import logging
import re
from pathlib import Path
from typing import Any, Optional

from .base_detector import BaseContainerDetector
from . import utils

logger = logging.getLogger(__name__)


class TerraformDetector(BaseContainerDetector):
    """Detect passive containers (datastores/external services) from Terraform."""

    RESOURCE_TYPES: dict[str, str] = {
        "aws_db_instance": "Database",
        "aws_rds_cluster": "Database",
        "aws_rds_cluster_instance": "Database",
        "google_sql_database_instance": "Database",
        "azurerm_cosmosdb_account": "Database",
        "azurerm_postgresql_flexible_server": "Database",
        "azurerm_mysql_flexible_server": "Database",
        "aws_s3_bucket": "Storage",
        "google_storage_bucket": "Storage",
        "azurerm_storage_account": "Storage",
    }

    PROVIDER_HINTS: dict[str, str] = {
        "aws_": "AWS",
        "google_": "GCP",
        "azurerm_": "Azure",
    }

    def can_detect(self) -> bool:
        return bool(list(self.repo_path.rglob("*.tf")))

    def detect(self) -> list[dict[str, Any]]:
        containers: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()

        for tf_file in self.repo_path.rglob("*.tf"):
            try:
                content = tf_file.read_text(encoding="utf-8", errors="ignore")
            except Exception as exc:
                logger.debug("Failed to read %s: %s", tf_file, exc)
                continue

            for resource_type, resource_name in self._extract_resources(content):
                container_type = self.RESOURCE_TYPES.get(resource_type)
                if not container_type:
                    continue

                rel_path = str(tf_file.parent.relative_to(self.repo_path))
                identity = (resource_type, resource_name, rel_path)
                if identity in seen:
                    continue
                seen.add(identity)

                provider = self._infer_provider(resource_type)
                name = resource_name or resource_type

                containers.append({
                    "c4_level": 2,
                    "type": "container",
                    "name": name,
                    "container_type": container_type,
                    "technology": provider or "Unknown",
                    "protocol": "N/A",
                    "path": rel_path if rel_path else ".",
                    "runtime_environment": "Cloud",
                    "deployment": "Terraform",
                    "description": f"Terraform {resource_type} resource.",
                    "repository_url": utils.get_repository_url(self.repo_path, tf_file.parent),
                    "runtime_info": utils.extract_runtime_version(tf_file.parent),
                    "dependencies_internal": [],
                    "health_endpoint": "",
                })

        return containers

    def _extract_resources(self, content: str) -> list[tuple[str, str]]:
        matches = re.findall(r"^\s*resource\s+\"([^\"]+)\"\s+\"([^\"]+)\"", content, re.MULTILINE)
        return [(resource_type, name) for resource_type, name in matches]

    def _infer_provider(self, resource_type: str) -> Optional[str]:
        for prefix, provider in self.PROVIDER_HINTS.items():
            if resource_type.startswith(prefix):
                return provider
        return None
