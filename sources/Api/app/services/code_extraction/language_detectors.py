"""Language-specific entry point detection strategy pattern.

Each detector handles one programming language ecosystem and can
identify API endpoints, route handlers, and controller classes.
"""

import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from app.domain.constants.technologies import detect_frameworks_in_content


class LanguageDetector(ABC):
    """Base class for language-specific entry point detection."""

    @abstractmethod
    def get_file_extensions(self) -> list[str]:
        """Return list of file extensions this detector handles."""
        pass

    @abstractmethod
    def get_entry_point_patterns(self) -> list[str]:
        """Return regex patterns for detecting entry points."""
        pass

    @abstractmethod
    def extract_entry_points(self, file_path: Path, content: str) -> list[dict[str, Any]]:
        """Extract entry points from file content.

        Returns:
            List of entry point dicts with keys: method, path, name, line_number
        """
        pass

    def get_framework_manifests(self) -> list[str]:
        """Return list of framework manifest files that indicate this language."""
        return []


class PythonLanguageDetector(LanguageDetector):
    """Detector for Python frameworks (FastAPI, Flask, Django)."""

    def get_file_extensions(self) -> list[str]:
        return ['.py']

    def get_entry_point_patterns(self) -> list[str]:
        return [
            r'@app\.(get|post|put|delete|patch)',
            r'@router\.(get|post|put|delete|patch)',
            r'@api\.(get|post|put|delete|patch)',
            r'class\s+\w+Controller',
            r'@Controller',
            r'@RestController',
        ]

    def extract_entry_points(self, file_path: Path, content: str) -> list[dict[str, Any]]:
        """Extract Python API endpoints."""
        entry_points = []

        route_pattern = r'@(?:app|router|api)\.(get|post|put|delete|patch)\s*\(["\']([^"\']+)'
        matches = re.finditer(route_pattern, content)

        for match in matches:
            method = match.group(1).upper()
            path = match.group(2)

            func_pattern = r'def\s+(\w+)\s*\('
            remaining = content[match.end():]
            func_match = re.search(func_pattern, remaining[:200])

            if func_match:
                func_name = func_match.group(1)
                entry_points.append({
                    'method': method,
                    'path': path,
                    'name': func_name,
                    'line_number': content[:match.start()].count('\n') + 1,
                })

        return entry_points

    def get_framework_manifests(self) -> list[str]:
        return ['pyproject.toml', 'requirements.txt', 'setup.py', 'Pipfile']


class JavaScriptLanguageDetector(LanguageDetector):
    """Detector for JavaScript/TypeScript frameworks (Express, Next.js, etc.)."""

    def get_file_extensions(self) -> list[str]:
        return ['.js', '.jsx', '.ts', '.tsx']

    def get_entry_point_patterns(self) -> list[str]:
        return [
            r'app\.(get|post|put|delete|patch)\(',
            r'router\.(get|post|put|delete|patch)\(',
            r'export\s+(async\s+)?function\s+handle',
            r'export\s+default\s+function',
        ]

    def extract_entry_points(self, file_path: Path, content: str) -> list[dict[str, Any]]:
        """Extract JavaScript/TypeScript API endpoints."""
        entry_points = []

        route_pattern = r'(?:app|router)\.(get|post|put|delete|patch)\s*\(["\']([^"\']+)'
        matches = re.finditer(route_pattern, content)

        for match in matches:
            method = match.group(1).upper()
            path = match.group(2)

            func_pattern = r'(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s+)?\(|(\w+)\s*:\s*(?:async\s+)?\('
            remaining = content[match.end():match.end()+300]
            func_match = re.search(func_pattern, remaining)

            func_name = None
            if func_match:
                func_name = func_match.group(1) or func_match.group(2) or func_match.group(3)

            entry_points.append({
                'method': method,
                'path': path,
                'name': func_name or 'anonymous',
                'line_number': content[:match.start()].count('\n') + 1,
            })

        return entry_points

    def get_framework_manifests(self) -> list[str]:
        return ['package.json', 'yarn.lock', 'package-lock.json']


class JavaLanguageDetector(LanguageDetector):
    """Detector for Java frameworks (Spring Boot, etc.)."""

    def get_file_extensions(self) -> list[str]:
        return ['.java']

    def get_entry_point_patterns(self) -> list[str]:
        return [
            r'@RestController',
            r'@Controller',
            r'@RequestMapping',
            r'@GetMapping',
            r'@PostMapping',
        ]

    def extract_entry_points(self, file_path: Path, content: str) -> list[dict[str, Any]]:
        """Extract Java REST controllers."""
        entry_points = []

        if '@RestController' in content or '@Controller' in content:
            class_pattern = r'class\s+(\w+)'
            class_match = re.search(class_pattern, content)

            if class_match:
                class_name = class_match.group(1)

                mapping_pattern = r'@(?:Get|Post|Put|Delete|Patch)Mapping\s*\(["\']([^"\']+)'
                mappings = re.finditer(mapping_pattern, content)

                for mapping in mappings:
                    path = mapping.group(1)
                    method_pattern = r'public\s+\w+\s+(\w+)\s*\('
                    method_match = re.search(method_pattern, content[mapping.end():mapping.end()+200])
                    method_name = method_match.group(1) if method_match else 'unknown'

                    entry_points.append({
                        'method': 'GET',
                        'path': path,
                        'name': f"{class_name}.{method_name}",
                        'line_number': content[:mapping.start()].count('\n') + 1,
                    })

                if not entry_points:
                    entry_points.append({
                        'method': None,
                        'path': None,
                        'name': class_name,
                        'line_number': content[:class_match.start()].count('\n') + 1,
                    })

        return entry_points

    def get_framework_manifests(self) -> list[str]:
        return ['pom.xml', 'build.gradle', 'build.gradle.kts']


# Map TargetFramework monikers to human-readable version labels
_DOTNET_TFM_MAP: dict[str, str] = {
    "net10.0": ".NET 10",
    "net9.0": ".NET 9",
    "net8.0": ".NET 8",
    "net7.0": ".NET 7",
    "net6.0": ".NET 6",
    "net5.0": ".NET 5",
    "netcoreapp3.1": ".NET Core 3.1",
    "netcoreapp3.0": ".NET Core 3.0",
    "netcoreapp2.1": ".NET Core 2.1",
    "netstandard2.1": ".NET Standard 2.1",
    "netstandard2.0": ".NET Standard 2.0",
    "net48": ".NET Framework 4.8",
    "net472": ".NET Framework 4.7.2",
    "net471": ".NET Framework 4.7.1",
    "net47": ".NET Framework 4.7",
    "net462": ".NET Framework 4.6.2",
    "net461": ".NET Framework 4.6.1",
    "net46": ".NET Framework 4.6",
}


def _find_target_framework_from_props(start_dir: Path, max_depth: int = 5) -> Optional[str]:
    """Walk up the directory tree looking for Directory.Build.props with <TargetFramework>."""
    current = start_dir.resolve()
    for _ in range(max_depth):
        props_file = current / "Directory.Build.props"
        if props_file.is_file():
            try:
                tree = ET.parse(str(props_file))
                for tag in ("TargetFramework", "TargetFrameworks"):
                    elem = tree.getroot().find(f".//{tag}")
                    if elem is not None and elem.text:
                        return elem.text.strip().split(";")[0]
            except ET.ParseError:
                pass
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


class DotNetLanguageDetector(LanguageDetector):
    """Detector for .NET/C# frameworks (ASP.NET Core, Worker Service, gRPC, Blazor, etc.)."""

    def get_file_extensions(self) -> list[str]:
        return ['.cs']

    def get_entry_point_patterns(self) -> list[str]:
        return [
            r'\[ApiController\]',
            r'\[Route\(',
            r'MapControllers\(',
            r'MapGet\(',
            r'MapPost\(',
            r'WebApplication\.Create',
            r'Host\.CreateDefaultBuilder',
        ]

    def extract_entry_points(self, file_path: Path, content: str) -> list[dict[str, Any]]:
        """Extract ASP.NET Core controller actions and minimal API endpoints."""
        entry_points = []

        # Minimal API endpoints (MapGet/MapPost/etc.)
        minimal_pattern = r'\.Map(Get|Post|Put|Delete|Patch)\s*\(\s*["\']([^"\']+)'
        for match in re.finditer(minimal_pattern, content):
            entry_points.append({
                'method': match.group(1).upper(),
                'path': match.group(2),
                'name': match.group(2),
                'line_number': content[:match.start()].count('\n') + 1,
            })

        # Controller action methods
        # Step 1: find [HttpVerb] or [HttpVerb("route")] attributes
        verb_re = re.compile(
            r'\[(Http(Get|Post|Put|Delete|Patch))(?:\s*\([^\)]*\))?\]',
            re.IGNORECASE,
        )
        for verb_match in verb_re.finditer(content):
            http_verb = verb_match.group(2).upper()
            line_num = content[:verb_match.start()].count('\n') + 1

            # Extract explicit route from [HttpGet("route")] if present
            route_match = re.search(
                r'\[Http\w+\s*\(\s*["\']([^"\']+)', verb_match.group(0), re.IGNORECASE
            )
            path = route_match.group(1) if route_match else None

            # Step 2: scan forward up to 800 chars for 'public' keyword
            window_start = verb_match.start()
            window = content[window_start: window_start + 800]
            pub_match = re.search(r'\bpublic\b', window)
            if not pub_match:
                continue

            from_public = window[pub_match.start():]

            # Step 3: track angle-bracket depth to find the '(' that opens
            # the parameter list (not generic type parameters like '<T>')
            method_name = self._find_method_name(from_public)
            if method_name:
                entry_points.append({
                    'method': http_verb,
                    'path': path,
                    'name': method_name,
                    'line_number': line_num,
                })

        return entry_points

    @staticmethod
    def _find_method_name(from_public: str) -> Optional[str]:
        """Extract the method name from a 'public [modifiers] [return_type] name(' fragment.

        Handles generic return types like Task<ActionResult<T>> by tracking
        angle-bracket depth so we find the parameter-list '(' correctly.
        """
        angle_depth = 0
        for i, ch in enumerate(from_public):
            if ch == '<':
                angle_depth += 1
            elif ch == '>':
                angle_depth = max(0, angle_depth - 1)
            elif ch == '(' and angle_depth == 0:
                # This '(' opens the parameter list
                before_paren = from_public[:i].rstrip()
                name_match = re.search(r'(\w+)\s*$', before_paren)
                if name_match:
                    candidate = name_match.group(1)
                    # Skip language keywords that can't be method names
                    _CSHARP_KEYWORDS = {
                        'public', 'private', 'protected', 'internal', 'static',
                        'async', 'virtual', 'override', 'abstract', 'sealed',
                        'new', 'partial', 'void', 'return', 'class', 'interface',
                    }
                    if candidate not in _CSHARP_KEYWORDS:
                        return candidate
                break
        return None

    def get_framework_manifests(self) -> list[str]:
        return ['*.csproj', '*.sln']

    def detect_language_and_framework(self, service_path: Path) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Detect C# language, framework, and .NET version from .csproj files.

        Args:
            service_path: Path to service directory

        Returns:
            Tuple of (language, framework, dotnet_version) where each may be None
        """
        csproj_files = list(service_path.glob("*.csproj"))
        # Also check one level deep
        if not csproj_files:
            for subdir in service_path.iterdir() if service_path.is_dir() else []:
                if subdir.is_dir():
                    csproj_files.extend(subdir.glob("*.csproj"))
                if csproj_files:
                    break

        if not csproj_files:
            # Check if there are any .cs files at all
            cs_files = list(service_path.glob("**/*.cs"))
            if cs_files:
                return "C#", None, None
            return None, None, None

        csproj = csproj_files[0]
        dotnet_version = None
        packages: list[str] = []

        try:
            tree = ET.parse(str(csproj))
            root = tree.getroot()

            # TargetFramework (handles both <TargetFramework> and <TargetFrameworks>)
            tfm_raw = None
            for tag in ("TargetFramework", "TargetFrameworks"):
                elem = root.find(f".//{tag}")
                if elem is not None and elem.text:
                    tfm_raw = elem.text.strip().split(";")[0].lower()
                    break

            # Fallback: look for Directory.Build.props up the tree
            if tfm_raw is None:
                inherited = _find_target_framework_from_props(csproj.parent)
                if inherited:
                    tfm_raw = inherited.lower()

            if tfm_raw:
                dotnet_version = _DOTNET_TFM_MAP.get(tfm_raw, tfm_raw)

            # PackageReference names
            for ref in root.findall(".//PackageReference"):
                include = ref.get("Include", "")
                if include:
                    packages.append(include)

        except ET.ParseError:
            pass

        # Run packages through framework detection
        packages_text = " ".join(packages).lower()
        detected = detect_frameworks_in_content(packages_text)

        # Priority: more specific frameworks first
        framework_priority = ["SignalR", "gRPC", "Blazor", "WCF", "Worker Service", "ASP.NET Core"]
        framework = None
        for priority_fw in framework_priority:
            for _, fw in detected:
                if fw == priority_fw:
                    framework = fw
                    break
            if framework:
                break

        # Fallback: if any ASP.NET Core package found, default to ASP.NET Core
        if framework is None and packages:
            aspnet_indicators = ["microsoft.aspnetcore", "microsoft.aspnet"]
            if any(any(ind in pkg.lower() for ind in aspnet_indicators) for pkg in packages):
                framework = "ASP.NET Core"

        # If TargetFramework says it's .NET but we still don't know framework,
        # check for Program.cs or Startup.cs as ASP.NET Core signal
        if framework is None and dotnet_version:
            if (service_path / "Program.cs").exists() or (service_path / "Startup.cs").exists():
                framework = "ASP.NET Core"

        return "C#", framework, dotnet_version
