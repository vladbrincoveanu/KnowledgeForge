"""Ownership signal detection for C4 Container vs SoftwareSystem boundary.

The C4 book rule: "Do you control its internals?"
- Yes → Container (even if hosted externally: your S3 bucket, your RDS instance)
- No  → SoftwareSystem (external API; vendor controls the runtime)

Ownership is detected by scanning the repo for:
- Migration files (you define the schema)
- Dockerfiles that build/run the dependency
- Terraform resources that provision it
- docker-compose service blocks
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_MIGRATION_DIR_PATTERNS = re.compile(
    r"(migrations?|alembic|flyway|liquibase|db/migrate|prisma/migrations)/",
    re.IGNORECASE,
)

_TERRAFORM_OWNERSHIP_RESOURCES: dict[str, list[str]] = {
    "aws_s3_bucket": ["s3", "blob", "storage", "bucket"],
    "aws_rds_instance": ["rds", "postgres", "mysql", "database", "db"],
    "aws_rds_cluster": ["rds", "aurora", "postgres", "mysql", "database"],
    "aws_elasticache_cluster": ["redis", "memcached", "cache"],
    "aws_sqs_queue": ["sqs", "queue"],
    "aws_dynamodb_table": ["dynamodb", "dynamo"],
    "aws_msk_cluster": ["kafka", "msk"],
    "google_sql_database_instance": ["cloudsql", "postgres", "mysql", "database"],
    "azurerm_sql_server": ["sql", "database", "db"],
    "azurerm_storage_account": ["blob", "storage", "azure"],
    "azurerm_cosmosdb_account": ["cosmos", "mongo", "database"],
}

_SOURCE_EXTENSIONS = {".py", ".ts", ".js", ".java", ".cs", ".go", ".rb", ".tf"}


@dataclass
class OwnershipSignal:
    """Evidence that a dependency is owned by this team."""

    signal_type: str  # migration | terraform | dockerfile | compose
    file_path: str
    confidence: float
    evidence: str


class OwnershipSignalDetector:
    """Scans a repository for signals that a dependency is team-owned."""

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = Path(repo_path).resolve()

    def detect_ownership_signals(self, dep_name: str) -> list[OwnershipSignal]:
        """Return all ownership signals found for this dependency name."""
        name_lower = dep_name.lower()
        signals: list[OwnershipSignal] = []
        signals.extend(self._scan_migration_dirs())
        signals.extend(self._scan_terraform(name_lower))
        signals.extend(self._scan_dockerfile(name_lower))
        signals.extend(self._scan_compose(name_lower))
        return signals

    def is_owned(
        self, dep_name: str, dep_type: str = ""
    ) -> tuple[bool, float, str]:
        """Return (is_owned, confidence, reason).

        A dependency is considered owned when at least one ownership signal
        exists in the repository with confidence >= 0.75.
        """
        signals = self.detect_ownership_signals(dep_name)
        if not signals:
            return False, 0.5, "No ownership signals found in repository"

        best = max(signals, key=lambda s: s.confidence)
        return True, best.confidence, f"Ownership signal ({best.signal_type}): {best.evidence}"

    # ------------------------------------------------------------------ #
    # Private scanners                                                     #
    # ------------------------------------------------------------------ #

    def _scan_migration_dirs(self) -> list[OwnershipSignal]:
        signals: list[OwnershipSignal] = []
        seen: set[str] = set()

        for path in self.repo_path.rglob("*"):
            if not path.is_file():
                continue
            rel = str(path.relative_to(self.repo_path))
            if _MIGRATION_DIR_PATTERNS.search(rel) and rel not in seen:
                seen.add(rel)
                signals.append(
                    OwnershipSignal(
                        signal_type="migration",
                        file_path=rel,
                        confidence=0.9,
                        evidence=f"Migration file: {path.name}",
                    )
                )
                break  # one signal per repo is enough

        return signals

    def _scan_terraform(self, dep_name_lower: str) -> list[OwnershipSignal]:
        signals: list[OwnershipSignal] = []

        for tf_file in self.repo_path.rglob("*.tf"):
            try:
                content = tf_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for resource_type, keywords in _TERRAFORM_OWNERSHIP_RESOURCES.items():
                if resource_type not in content:
                    continue
                if any(kw in dep_name_lower for kw in keywords):
                    rel = str(tf_file.relative_to(self.repo_path))
                    signals.append(
                        OwnershipSignal(
                            signal_type="terraform",
                            file_path=rel,
                            confidence=0.95,
                            evidence=f"Terraform resource '{resource_type}' in {tf_file.name}",
                        )
                    )

        return signals

    def _scan_dockerfile(self, dep_name_lower: str) -> list[OwnershipSignal]:
        signals: list[OwnershipSignal] = []

        for df in self.repo_path.rglob("Dockerfile*"):
            try:
                content = df.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue

            if dep_name_lower in content:
                rel = str(df.relative_to(self.repo_path))
                signals.append(
                    OwnershipSignal(
                        signal_type="dockerfile",
                        file_path=rel,
                        confidence=0.8,
                        evidence=f"Dependency referenced in {df.name}",
                    )
                )

        return signals

    def _scan_compose(self, dep_name_lower: str) -> list[OwnershipSignal]:
        """Find docker-compose service definitions that run this dependency."""
        signals: list[OwnershipSignal] = []
        compose_files = list(self.repo_path.rglob("docker-compose*.yml")) + list(
            self.repo_path.rglob("docker-compose*.yaml")
        )

        for cf in compose_files:
            try:
                content = cf.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue

            if dep_name_lower in content and "image:" in content:
                rel = str(cf.relative_to(self.repo_path))
                signals.append(
                    OwnershipSignal(
                        signal_type="compose",
                        file_path=rel,
                        confidence=0.85,
                        evidence=f"Service image for '{dep_name_lower}' in {cf.name}",
                    )
                )

        return signals