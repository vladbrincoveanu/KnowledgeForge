"""Deployment Target Detection.

Detects deployment targets:
- Container, Kubernetes, Serverless, VM, PaaS, Bare-Metal
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_deployment_targets(repo_path: Path) -> list[str]:
    """Detect deployment targets for the service.

    Args:
        repo_path: Path to the repository

    Returns:
        List of detected deployment targets (e.g., ["Container", "Kubernetes"])
    """
    repo_path = Path(repo_path)
    if not repo_path.exists():
        return []

    targets = set()

    # Check for Container
    if _detect_container(repo_path):
        targets.add("Container")

    # Check for Kubernetes
    if _detect_kubernetes(repo_path):
        targets.add("Kubernetes")

    # Check for Serverless
    if _detect_serverless(repo_path):
        targets.add("Serverless")

    # Check for VM
    if _detect_vm(repo_path):
        targets.add("VM")

    # Check for PaaS
    if _detect_paas(repo_path):
        targets.add("PaaS")

    # Check for Bare-Metal
    if _detect_bare_metal(repo_path):
        targets.add("Bare-Metal")

    return sorted(targets)


def _detect_container(repo_path: Path) -> bool:
    """Detect Docker container usage."""
    dockerfiles = list(repo_path.rglob("Dockerfile*"))
    if dockerfiles:
        return True

    # Check for docker-compose files
    compose_files = list(repo_path.rglob("docker-compose*.yml")) + list(repo_path.rglob("docker-compose*.yaml"))
    if compose_files:
        return True

    # Check for .dockerignore
    if (repo_path / ".dockerignore").exists():
        return True

    return False


def _detect_kubernetes(repo_path: Path) -> bool:
    """Detect Kubernetes deployment."""
    # Check for Kubernetes manifests
    k8s_dirs = ["k8s", "kubernetes", "manifests", "deploy"]
    for d in k8s_dirs:
        k8s_path = repo_path / d
        if k8s_path.exists() and k8s_path.is_dir():
            # Check for yaml files in the directory
            yaml_files = list(k8s_path.rglob("*.yaml")) + list(k8s_path.rglob("*.yml"))
            if yaml_files:
                return True

    # Check for Helm charts
    helm_dirs = list(repo_path.rglob("Chart.yaml")) + list(repo_path.rglob("helm/**"))
    if helm_dirs:
        return True

    # Check for Kustomize
    if (repo_path / "kustomization.yaml").exists():
        return True

    # Check for Kubernetes-specific files
    k8s_files = [
        "deployment.yaml",
        "service.yaml",
        "ingress.yaml",
        "statefulset.yaml",
        "daemonset.yaml",
    ]
    for kf in k8s_files:
        if list(repo_path.rglob(kf)):
            return True

    return False


def _detect_serverless(repo_path: Path) -> bool:
    """Detect serverless deployment."""
    # Check for serverless.yml
    if (repo_path / "serverless.yml").exists() or (repo_path / "serverless.yaml").exists():
        return True

    # Check for AWS SAM
    if (repo_path / "template.yaml").exists() and _has_aws_sam_content(repo_path):
        return True

    # Check for Terraform with serverless provider
    tf_files = list(repo_path.rglob("*.tf"))
    for tf in tf_files:
        try:
            content = tf.read_text(errors="ignore").lower()
            if "aws_lambda" in content or "google_cloudfunctions" in content or "azurerm_function_app" in content:
                return True
        except Exception:
            continue

    # Check for package.json with serverless framework
    package_json = repo_path / "package.json"
    if package_json.exists():
        try:
            import json
            content = json.loads(package_json.read_text())
            deps = {**content.get("dependencies", {}), **content.get("devDependencies", {})}
            if "serverless" in deps:
                return True
        except Exception:
            pass

    # Check for requirements.txt with lambda
    req = repo_path / "requirements.txt"
    if req.exists():
        content = req.read_text(errors="ignore").lower()
        if "awslambdacore" in content or "chalice" in content:
            return True

    return False


def _has_aws_sam_content(repo_path: Path) -> bool:
    """Check if template.yaml contains AWS SAM resources."""
    tmpl = repo_path / "template.yaml"
    if tmpl.exists():
        try:
            content = tmpl.read_text(errors="ignore")
            if "AWS::Serverless::" in content:
                return True
        except Exception:
            pass
    return False


def _detect_vm(repo_path: Path) -> bool:
    """Detect VM-based deployment."""
    # Check for VM provisioning files
    vm_indicators = [
        "Vagrantfile",
        "*.tf"  # Terraform VM resources
    ]

    for ind in vm_indicators:
        if ind == "Vagrantfile":
            if (repo_path / "Vagrantfile").exists():
                return True
        elif ind == "*.tf":
            tf_files = list(repo_path.rglob("*.tf"))
            for tf in tf_files:
                try:
                    content = tf.read_text(errors="ignore")
                    if "aws_instance" in content or "google_compute_instance" in content or "azurerm_virtual_machine" in content:
                        return True
                except Exception:
                    continue

    return False


def _detect_paas(repo_path: Path) -> bool:
    """Detect Platform-as-a-Service deployment."""
    # Check for Procfile (Heroku, Render, etc.)
    if (repo_path / "Procfile").exists():
        return True

    # Check for app.json (Heroku)
    if (repo_path / "app.json").exists():
        return True

    # Check for render.yaml
    if (repo_path / "render.yaml").exists():
        return True

    # Check for railway.json
    if (repo_path / "railway.json").exists():
        return True

    # Check for fly.toml
    if (repo_path / "fly.toml").exists():
        return True

    # Check for vercel.json
    if (repo_path / "vercel.json").exists():
        return True

    # Check for netlify.toml
    if (repo_path / "netlify.toml").exists():
        return True

    return False


def _detect_bare_metal(repo_path: Path) -> bool:
    """Detect bare-metal deployment (systemd, init scripts)."""
    # Check for systemd units
    systemd_files = list(repo_path.rglob("*.service"))
    if systemd_files:
        return True

    # Check for init scripts
    init_dirs = ["init.d", "systemd", "sysvinit"]
    for d in init_dirs:
        init_path = repo_path / d
        if init_path.exists() and init_path.is_dir():
            scripts = list(init_path.glob("*.sh"))
            if scripts:
                return True

    # Check for Makefile with install target
    makefile = repo_path / "Makefile"
    if makefile.exists():
        content = makefile.read_text(errors="ignore")
        if "install:" in content:
            # Check it's not just a dev install
            if "apt" in content or "yum" in content or "brew" in content:
                return True

    return False
