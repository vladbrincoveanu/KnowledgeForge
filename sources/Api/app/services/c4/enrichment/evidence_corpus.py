from pathlib import Path
from pydantic import BaseModel, Field


class DepEvidence(BaseModel):
    name: str
    type: str
    confidence: float = Field(ge=0.0, le=1.0)
    files_found_in: list[Path] = Field(default_factory=list)


class EvidenceCorpus(BaseModel):
    repo_path: Path
    task_id: str
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    deterministic_deps: list[DepEvidence] = Field(default_factory=list)
    entrypoints: list[Path] = Field(default_factory=list)
    detected_urls: list[str] = Field(default_factory=list)
    env_vars: list[str] = Field(default_factory=list)
    docker_images: list[str] = Field(default_factory=list)
    package_files: list[Path] = Field(default_factory=list)