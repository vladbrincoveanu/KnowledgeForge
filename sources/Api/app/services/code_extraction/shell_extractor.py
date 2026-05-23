"""Shell script component extractor for C4 Level 3.

Handles containers implemented entirely in shell scripts — e.g. Alpine-based
SSH gateways, Docker entrypoints, init containers, CI runners — where the
standard tree-sitter pipeline produces nothing because there are no Python,
Go, or Java source files.

One ComponentObject is produced per shell script.  Each ComponentObject
carries a CodeElement that summarises the script's functions and the external
tools it invokes, giving the LLM rename pass enough context to produce a
business-intent name like "HPC Tunnel Route Provisioner" rather than just
"tunnel-handler".
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# External programs whose presence indicates a meaningful responsibility.
# We surface these as "imports" so the LLM rename pass can read them.
_NOTABLE_TOOLS = frozenset({
    "kubectl", "helm", "docker", "podman",
    "sshd", "ssh", "ssh-keygen", "ssh-agent",
    "curl", "wget",
    "systemctl", "supervisord",
    "python", "python3", "pip", "uvicorn", "gunicorn",
    "node", "npm", "yarn", "pnpm",
    "go", "cargo", "java",
    "psql", "mysql", "redis-cli", "mongod",
    "nginx", "apache2", "caddy",
    "aws", "gcloud", "az",
    "openssl", "gpg",
    "jq", "yq",
})

# Shell function declaration patterns (POSIX and bash styles)
_FUNC_RE = re.compile(
    r"^\s*(?:function\s+)?([A-Za-z_][A-Za-z0-9_.-]*)\s*\(\s*\)\s*\{",
    re.MULTILINE,
)

_TOOL_PREFIXES = re.compile(r"[A-Za-z][A-Za-z0-9_-]+")
_PATH_BASENAME = re.compile(r"/(?:[A-Za-z0-9_.-]+/)*([A-Za-z][A-Za-z0-9_-]+)")


def _parse_shell_script(path: Path) -> dict:
    """Extract structural information from one shell script.

    Returns a dict with keys:
    - functions: list of function names declared in the script
    - tools: sorted list of notable external tools invoked
    - shebang: the shebang line if present, else ""
    - env_vars: environment variable names used ($VAR style), up to 20
    """
    try:
        text = path.read_text(errors="replace")
    except OSError as exc:
        logger.debug("Cannot read %s: %s", path, exc)
        return {"functions": [], "tools": [], "shebang": "", "env_vars": []}

    shebang = ""
    if text.startswith("#!"):
        shebang = text.splitlines()[0]

    # Remove comments to avoid false-positive matches inside comment lines
    text_no_comments = re.sub(r"#[^\n]*", "", text)

    functions = _FUNC_RE.findall(text_no_comments)
    # Filter out single-char artefacts and common noise
    functions = [f for f in functions if len(f) > 1 and f not in {"do", "fi", "in"}]

    # Extract tool names from both bare words and full paths like /usr/sbin/sshd
    words = _TOOL_PREFIXES.findall(text_no_comments)
    path_basenames = _PATH_BASENAME.findall(text_no_comments)
    tools = sorted({t for t in words + path_basenames if t in _NOTABLE_TOOLS})

    env_vars = sorted(set(re.findall(r"\$\{?([A-Z][A-Z0-9_]{2,})\}?", text)))[:20]

    return {
        "functions": functions,
        "tools": tools,
        "shebang": shebang,
        "env_vars": env_vars,
    }


def _infer_component_type(info: dict) -> "ComponentType":
    """Guess a ComponentType from the script's tool usage."""
    from app.services.c4.components.models import ComponentType

    tools = set(info["tools"])
    functions = [f.lower() for f in info["functions"]]

    if "kubectl" in tools or "helm" in tools:
        return ComponentType.HANDLER
    if "sshd" in tools:
        return ComponentType.SERVICE
    if any(k in tools for k in ("nginx", "apache2", "caddy")):
        return ComponentType.GATEWAY
    if any("init" in f or "setup" in f or "start" in f for f in functions):
        return ComponentType.SERVICE
    return ComponentType.COMPONENT


def extract_shell_components(container_abs_path: str) -> list:
    """Return one ComponentObject per shell script found in *container_abs_path*.

    Only files with a `.sh` extension (or a `#!/bin/sh` / `#!/bin/bash`
    shebang and no extension) are processed.  Directories named `.git`,
    `vendor`, `node_modules`, and `.venv` are skipped.

    Returns an empty list when no shell scripts are found, so callers can
    fall through to the generic fallback without any special-casing.
    """
    from app.services.c4.components.models import (
        ArchitecturalLayer,
        CodeElement,
        CodeElementKind,
        ComponentObject,
        ExtractionMethod,
    )

    root = Path(container_abs_path)
    if not root.is_dir():
        logger.info("Shell extractor: path does not exist: %s", container_abs_path)
        return []
    logger.info("Shell extractor: scanning %s", root)

    _SKIP_DIRS = {".git", "vendor", "node_modules", ".venv", "__pycache__"}

    shell_files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            if path.suffix == ".sh":
                shell_files.append(path)
            elif not path.suffix:
                # Check for shell shebang in extension-less files
                try:
                    first = path.read_bytes()[:30].decode(errors="replace")
                    if first.startswith(("#!/bin/sh", "#!/bin/bash", "#!/usr/bin/env sh", "#!/usr/bin/env bash")):
                        shell_files.append(path)
                except OSError:
                    pass

    if not shell_files:
        logger.info(
            "Shell extractor: no shell scripts found in %s (searched %s)",
            root.name, root,
        )
        return []

    components: list[ComponentObject] = []
    for script_path in sorted(shell_files):
        info = _parse_shell_script(script_path)

        stem = script_path.stem or script_path.name
        label = stem.replace("-", " ").replace("_", " ").title()

        # Build a representative CodeElement so _llm_rename_components has
        # real signal (function names, tool calls as "imports").
        qualified = label  # best human name we have pre-LLM
        element = CodeElement(
            qualified_name=qualified,
            kind=CodeElementKind.MODULE,
            file_path=str(script_path),
            language="shell",
            annotations=[info["shebang"]] if info["shebang"] else [],
            imports=info["tools"],          # external tool calls → "imports"
            method_calls=info["functions"], # shell functions → "method_calls"
            layer=ArchitecturalLayer.INFRASTRUCTURE,
            metadata={
                "env_vars": info["env_vars"],
                "functions": info["functions"],
            },
        )

        comp_type = _infer_component_type(info)
        script_rel = str(script_path.relative_to(root))
        comp_id = f"shell_{stem.lower().replace('-', '_').replace(' ', '_')}"

        comp = ComponentObject(
            component_id=comp_id,
            name=label,
            technology="Shell Script",
            component_type=comp_type,
            extraction_method=ExtractionMethod.COMMUNITY_DETECTION,
            confidence=0.6,
            code_elements=[element],
            metadata={"shell_script": script_rel, "tools": info["tools"]},
        )
        components.append(comp)
        logger.debug(
            "Shell extractor: found component '%s' from %s (tools: %s)",
            label, script_rel, info["tools"],
        )

    logger.info(
        "Shell extractor: %d component(s) from %d script(s) in %s",
        len(components), len(shell_files), root.name,
    )
    return components
