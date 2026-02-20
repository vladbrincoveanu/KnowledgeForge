"""Metadata harvesters for canonical C4 context extraction."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path

import yaml

from .canonical_models import FieldCandidate


def _safe_hash(content: str) -> str:
    return sha1(content.encode("utf-8")).hexdigest()


class ServiceUniverseHarvester:
    """Harvest metadata candidates from service-universe YAML files."""

    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path).resolve()

    def harvest(self, system_name: str) -> list[FieldCandidate]:
        """Extract candidate fields for a target system from service-universe YAML."""
        candidates: list[FieldCandidate] = []
        files = list(self.repo_path.rglob("*service-universe*.y*ml"))
        files.extend(self.repo_path.glob("service-universe.y*ml"))

        for file_path in files:
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                parsed = yaml.safe_load(content) or {}
            except (OSError, ValueError, yaml.YAMLError):
                continue

            systems = parsed.get("systems", [])
            if isinstance(systems, dict):
                systems = [systems]
            for system in systems:
                if not isinstance(system, dict):
                    continue
                name = str(system.get("name", "")).strip()
                if name.lower() != system_name.lower():
                    continue

                field_map = {
                    "owner": "owner",
                    "domain": "domain",
                    "lifecycle": "lifecycle",
                    "tier": "tier",
                    "data_class": "data_class",
                    "experts": "experts",
                    "compliance_flags": "compliance_flags",
                }
                for source_key, field_name in field_map.items():
                    if source_key not in system:
                        continue
                    candidates.append(
                        FieldCandidate(
                            field_name=field_name,
                            value=system.get(source_key),
                            source_type="service_universe",
                            source_path=str(file_path.relative_to(self.repo_path)),
                            source_hash=_safe_hash(content),
                            artifact_version=str(system.get("version", "")),
                            extraction_rule=f"service_universe:{source_key}",
                            confidence=0.95,
                            last_seen=datetime.now(timezone.utc),
                        )
                    )
        return candidates


class RepositoryArtifactHarvester:
    """Harvest metadata candidates from repository-adjacent artifacts."""

    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path).resolve()

    def harvest(self) -> list[FieldCandidate]:
        """Extract owner/domain/lifecycle and compliance hints from repo files."""
        now = datetime.now(timezone.utc)
        candidates: list[FieldCandidate] = []

        codeowners_files = [
            self.repo_path / "CODEOWNERS",
            self.repo_path / ".github" / "CODEOWNERS",
        ]
        for file_path in codeowners_files:
            if not file_path.exists():
                continue
            content = file_path.read_text(encoding="utf-8")
            teams = re.findall(r"@([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)", content)
            if teams:
                candidates.append(
                    FieldCandidate(
                        field_name="owner",
                        value=teams[0],
                        source_type="codeowners",
                        source_path=str(file_path.relative_to(self.repo_path)),
                        source_hash=_safe_hash(content),
                        artifact_version="",
                        extraction_rule="codeowners:first_team",
                        confidence=0.9,
                        last_seen=now,
                    )
                )

        readme = self.repo_path / "README.md"
        if readme.exists():
            content = readme.read_text(encoding="utf-8")
            domain_match = re.search(r"domain:\s*([^\n]+)", content, flags=re.IGNORECASE)
            lifecycle_match = re.search(r"(active|maintenance|deprecated|archived)", content, flags=re.IGNORECASE)
            if domain_match:
                candidates.append(
                    FieldCandidate(
                        field_name="domain",
                        value=domain_match.group(1).strip(),
                        source_type="repo_metadata",
                        source_path=str(readme.relative_to(self.repo_path)),
                        source_hash=_safe_hash(content),
                        artifact_version="",
                        extraction_rule="readme:domain_pattern",
                        confidence=0.65,
                        last_seen=now,
                    )
                )
            if lifecycle_match:
                candidates.append(
                    FieldCandidate(
                        field_name="lifecycle",
                        value=lifecycle_match.group(1).strip().upper(),
                        source_type="repo_metadata",
                        source_path=str(readme.relative_to(self.repo_path)),
                        source_hash=_safe_hash(content),
                        artifact_version="",
                        extraction_rule="readme:lifecycle_pattern",
                        confidence=0.6,
                        last_seen=now,
                    )
                )

        for config_name in ("package.json", "pyproject.toml"):
            file_path = self.repo_path / config_name
            if not file_path.exists():
                continue
            content = file_path.read_text(encoding="utf-8")
            tier = "Tier 1" if "production" in content.lower() else "Tier 2"
            candidates.append(
                FieldCandidate(
                    field_name="tier",
                    value=tier,
                    source_type="repo_metadata",
                    source_path=str(file_path.relative_to(self.repo_path)),
                    source_hash=_safe_hash(content),
                    artifact_version="",
                    extraction_rule=f"{config_name}:tier_heuristic",
                    confidence=0.55,
                    last_seen=now,
                )
            )

        compliance_file = self.repo_path / "compliance.json"
        if compliance_file.exists():
            try:
                content = compliance_file.read_text(encoding="utf-8")
                payload = json.loads(content)
                flags = payload.get("flags", [])
                candidates.append(
                    FieldCandidate(
                        field_name="compliance_flags",
                        value=flags,
                        source_type="compliance_artifact",
                        source_path=str(compliance_file.relative_to(self.repo_path)),
                        source_hash=_safe_hash(content),
                        artifact_version=str(payload.get("version", "")),
                        extraction_rule="compliance_file:flags",
                        confidence=0.95,
                        last_seen=now,
                    )
                )
            except (OSError, ValueError, TypeError):
                pass

        return candidates

