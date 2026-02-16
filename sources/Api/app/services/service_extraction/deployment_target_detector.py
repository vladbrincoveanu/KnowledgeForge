"""Deployment target detector for services.

Scans a service directory for signals indicating where/how it is deployed:

  Container      – Dockerfile present
  Kubernetes     – k8s/*.yaml with kind: Deployment/StatefulSet/etc, or Helm chart
  Serverless     – serverless.yml, SAM template, functions.yaml, *.tf with lambda/function
  VM             – Vagrantfile, Ansible playbooks, cloud-init user-data.yml
  Bare-Metal     – Makefile with systemd/sysctl targets, supervisord.conf
  PaaS           – Procfile (Heroku), app.yaml (Google App Engine), manifest.yml (Cloud Foundry)

Returns a list of matched DeploymentTarget string values (may be multi-valued).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Signal matchers ────────────────────────────────────────────────────────────

# Kubernetes resource kinds that indicate deployment
_K8S_KINDS = re.compile(
    r"^kind:\s*(Deployment|StatefulSet|DaemonSet|Job|CronJob|Pod|ReplicaSet)",
    re.MULTILINE | re.IGNORECASE,
)

# Serverless framework / AWS SAM
_SERVERLESS_KEYS = re.compile(
    r"(^service:|^functions:|^provider:\s*\n\s+name:\s*(aws|gcp|azure))",
    re.MULTILINE | re.IGNORECASE,
)
_SAM_KEYS = re.compile(
    r"AWSTemplateFormatVersion|Transform:\s*AWS::Serverless",
    re.IGNORECASE,
)

# Terraform lambda / cloud function
_TF_LAMBDA = re.compile(
    r'resource\s+"aws_lambda_function"|resource\s+"google_cloudfunctions_function"'
    r'|resource\s+"azurerm_function_app"',
    re.IGNORECASE,
)

# Ansible playbook indicator
_ANSIBLE_KEYS = re.compile(
    r"^\s*-\s+hosts:|^\s*become:",
    re.MULTILINE,
)

# Systemd / supervisord in Makefile
_MAKEFILE_SYSTEMD = re.compile(
    r"systemctl|supervisor|supervisorctl",
    re.IGNORECASE,
)


class DeploymentTargetDetector:
    """Detect deployment targets from service files."""

    def __init__(self, service_path: Path):
        self.root = Path(service_path).resolve()

    def detect(self) -> list[str]:
        """Return a list of detected DeploymentTarget values."""
        targets: list[str] = []

        if self._has_container():
            targets.append("Container")

        if self._has_kubernetes():
            targets.append("Kubernetes")

        if self._has_serverless():
            targets.append("Serverless")

        if self._has_vm():
            targets.append("VM")

        if self._has_bare_metal():
            targets.append("Bare-Metal")

        if self._has_paas():
            targets.append("PaaS")

        return targets

    # ─────────────────────────────────────────────────────────────────────────
    # Individual detectors
    # ─────────────────────────────────────────────────────────────────────────

    def _has_container(self) -> bool:
        # Dockerfile in root or one level deep
        if (self.root / "Dockerfile").exists():
            return True
        for child in self.root.iterdir():
            if child.is_dir() and (child / "Dockerfile").exists():
                return True
        # docker-compose also implies containerized deployment
        for name in ("docker-compose.yml", "docker-compose.yaml"):
            if (self.root / name).exists():
                return True
        return False

    def _has_kubernetes(self) -> bool:
        # Helm chart indicator
        if (self.root / "Chart.yaml").exists() or (self.root / "helm").is_dir():
            return True

        # Look for k8s manifest directories
        k8s_dirs = ["k8s", "kubernetes", "manifests", "deploy", "deployments", "infra"]
        for d in k8s_dirs:
            candidate = self.root / d
            if candidate.is_dir():
                for yaml_file in list(candidate.glob("*.yaml")) + list(candidate.glob("*.yml")):
                    try:
                        content = yaml_file.read_text(encoding="utf-8", errors="ignore")
                        if _K8S_KINDS.search(content):
                            return True
                    except OSError:
                        pass

        # Check root-level YAML files for k8s kind
        for yaml_file in list(self.root.glob("*.yaml")) + list(self.root.glob("*.yml")):
            try:
                content = yaml_file.read_text(encoding="utf-8", errors="ignore")
                if _K8S_KINDS.search(content) and "apiVersion:" in content:
                    return True
            except OSError:
                pass

        return False

    def _has_serverless(self) -> bool:
        # Serverless Framework
        for name in ("serverless.yml", "serverless.yaml", "serverless.json"):
            p = self.root / name
            if p.exists():
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    if _SERVERLESS_KEYS.search(content) or "functions:" in content:
                        return True
                except OSError:
                    return True  # file exists, give credit

        # AWS SAM
        for name in ("template.yaml", "template.yml", "sam-template.yaml"):
            p = self.root / name
            if p.exists():
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    if _SAM_KEYS.search(content):
                        return True
                except OSError:
                    pass

        # AWS Lambda in Terraform files
        tf_dir = self.root / "terraform"
        scan_dirs = [self.root, tf_dir] if tf_dir.is_dir() else [self.root]
        for d in scan_dirs:
            for tf_file in d.glob("*.tf"):
                try:
                    content = tf_file.read_text(encoding="utf-8", errors="ignore")
                    if _TF_LAMBDA.search(content):
                        return True
                except OSError:
                    pass

        # Google Cloud Functions / Azure Functions
        if (self.root / "functions.yaml").exists() or (self.root / "function.json").exists():
            return True

        return False

    def _has_vm(self) -> bool:
        # Vagrant
        if (self.root / "Vagrantfile").exists():
            return True

        # Ansible playbook in root or ansible/
        ansible_dirs = [self.root, self.root / "ansible", self.root / "provisioning"]
        for d in ansible_dirs:
            if not d.is_dir():
                continue
            for yaml_file in list(d.glob("*.yaml")) + list(d.glob("*.yml")):
                try:
                    content = yaml_file.read_text(encoding="utf-8", errors="ignore")
                    if _ANSIBLE_KEYS.search(content):
                        return True
                except OSError:
                    pass

        # cloud-init
        for name in ("user-data.yml", "cloud-init.yaml", "cloud-init.yml"):
            if (self.root / name).exists():
                return True

        return False

    def _has_bare_metal(self) -> bool:
        # supervisord
        for name in ("supervisord.conf", "supervisor.conf", "supervisord.ini"):
            if (self.root / name).exists():
                return True
        conf_dir = self.root / "conf"
        if conf_dir.is_dir():
            for name in ("supervisord.conf", "supervisor.conf"):
                if (conf_dir / name).exists():
                    return True

        # systemd unit file
        for unit in self.root.glob("*.service"):
            return True

        # Makefile with systemd keywords
        makefile = self.root / "Makefile"
        if makefile.exists():
            try:
                content = makefile.read_text(encoding="utf-8", errors="ignore")
                if _MAKEFILE_SYSTEMD.search(content):
                    return True
            except OSError:
                pass

        return False

    def _has_paas(self) -> bool:
        # Heroku
        if (self.root / "Procfile").exists():
            return True

        # Google App Engine
        if (self.root / "app.yaml").exists():
            try:
                content = (self.root / "app.yaml").read_text(encoding="utf-8", errors="ignore")
                if "runtime:" in content:
                    return True
            except OSError:
                return True

        # Cloud Foundry
        if (self.root / "manifest.yml").exists() or (self.root / "manifest.yaml").exists():
            return True

        # Render / Railway / Fly.io
        for name in ("render.yaml", "railway.json", "fly.toml"):
            if (self.root / name).exists():
                return True

        return False


def detect_deployment_targets(service_path: Path) -> list[str]:
    """Convenience function — returns list of detected deployment target strings."""
    try:
        return DeploymentTargetDetector(service_path).detect()
    except Exception as e:
        logger.warning(f"Deployment target detection failed for {service_path}: {e}")
        return []
