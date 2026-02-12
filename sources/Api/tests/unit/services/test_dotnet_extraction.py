"""Unit tests for .NET / C# service extraction capabilities."""

import textwrap
from pathlib import Path

import pytest

from app.services.code_extraction.language_detectors import DotNetLanguageDetector
from app.services.service_extraction.source_extractors import (
    extract_from_csproj,
    extract_from_sln,
    extract_from_top_level_directories,
)
from app.services.c4.context.dependency_detector import (
    DependencyDetector,
    NUGET_DEPENDENCY_MAP,
)
from app.services.c4.context.system_detector import SystemDetector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_csproj(directory: Path, name: str, content: str) -> Path:
    """Write a minimal .csproj file into *directory* and return its path."""
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


ASPNETCORE_CSPROJ = textwrap.dedent("""\
    <Project Sdk="Microsoft.NET.Sdk.Web">
      <PropertyGroup>
        <TargetFramework>net8.0</TargetFramework>
        <AssemblyName>wps.pages</AssemblyName>
      </PropertyGroup>
      <ItemGroup>
        <PackageReference Include="Microsoft.AspNetCore.App" />
        <PackageReference Include="StackExchange.Redis" Version="2.7.4" />
        <PackageReference Include="Confluent.Kafka" Version="2.3.0" />
      </ItemGroup>
    </Project>
""")

WORKER_CSPROJ = textwrap.dedent("""\
    <Project Sdk="Microsoft.NET.Sdk.Worker">
      <PropertyGroup>
        <TargetFramework>net8.0</TargetFramework>
      </PropertyGroup>
      <ItemGroup>
        <PackageReference Include="Microsoft.Extensions.Hosting" Version="8.0.0" />
      </ItemGroup>
    </Project>
""")

SLN_CONTENT = textwrap.dedent("""\

    Microsoft Visual Studio Solution File, Format Version 12.00
    # Visual Studio Version 17
    Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "wps.pages", "wps.pages\\wps.pages.csproj", "{11111111-1111-1111-1111-111111111111}"
    EndProject
    Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "wps.core", "wps.core\\wps.core.csproj", "{22222222-2222-2222-2222-222222222222}"
    EndProject
    Global
    EndGlobal
""")


# ---------------------------------------------------------------------------
# Test 1: service discovery finds .csproj directory
# ---------------------------------------------------------------------------


def test_discover_csproj_as_service(tmp_path):
    """A directory containing a .csproj file should be discovered as a C# service."""
    service_dir = tmp_path / "wps.pages"
    service_dir.mkdir()
    _write_csproj(service_dir, "wps.pages.csproj", ASPNETCORE_CSPROJ)

    services = extract_from_top_level_directories(
        repo_root=tmp_path,
        existing_services=[],
        errors=[],
        warnings=[],
    )

    assert len(services) == 1
    svc = services[0]
    assert svc.name == "wps.pages"
    assert svc.language == "C#"


# ---------------------------------------------------------------------------
# Test 2: DotNetLanguageDetector detects ASP.NET Core
# ---------------------------------------------------------------------------


def test_dotnet_language_detector_aspnetcore(tmp_path):
    """A .csproj with Microsoft.AspNetCore.App should resolve to ASP.NET Core."""
    _write_csproj(tmp_path, "wps.pages.csproj", ASPNETCORE_CSPROJ)

    detector = DotNetLanguageDetector()
    language, framework, version = detector.detect_language_and_framework(tmp_path)

    assert language == "C#"
    assert framework == "ASP.NET Core"
    assert version == ".NET 8"


# ---------------------------------------------------------------------------
# Test 3: DotNetLanguageDetector detects Worker Service
# ---------------------------------------------------------------------------


def test_dotnet_language_detector_worker_service(tmp_path):
    """A .csproj with Microsoft.Extensions.Hosting should resolve to Worker Service."""
    _write_csproj(tmp_path, "worker.csproj", WORKER_CSPROJ)

    detector = DotNetLanguageDetector()
    language, framework, version = detector.detect_language_and_framework(tmp_path)

    assert language == "C#"
    assert framework == "Worker Service"
    assert version == ".NET 8"


# ---------------------------------------------------------------------------
# Test 4: extract_dotnet_dependencies maps NuGet packages → ExternalDependency
# ---------------------------------------------------------------------------


def test_extract_nuget_external_deps(tmp_path):
    """A .csproj with Kafka + Redis packages should yield 2 external dependency dicts."""
    _write_csproj(tmp_path, "wps.pages.csproj", ASPNETCORE_CSPROJ)

    detector = DependencyDetector(repo_path=tmp_path, enable_classification=False)
    deps = detector._parse_nuget_dependencies()

    names = {d["name"] for d in deps}
    assert "Kafka" in names
    assert "Redis" in names


# ---------------------------------------------------------------------------
# Test 5: extract_from_sln returns correct .csproj paths
# ---------------------------------------------------------------------------


def test_sln_project_enumeration(tmp_path):
    """extract_from_sln() should return the correct list of .csproj absolute paths."""
    sln_path = tmp_path / "wps.core.sln"
    sln_path.write_text(SLN_CONTENT, encoding="utf-8")

    # Create the referenced .csproj stubs so resolve() works predictably
    (tmp_path / "wps.pages").mkdir()
    (tmp_path / "wps.pages" / "wps.pages.csproj").touch()
    (tmp_path / "wps.core").mkdir()
    (tmp_path / "wps.core" / "wps.core.csproj").touch()

    result = extract_from_sln(sln_path)

    assert len(result) == 2
    assert any("wps.pages.csproj" in p for p in result)
    assert any("wps.core.csproj" in p for p in result)


# ---------------------------------------------------------------------------
# Test 6: system name is extracted from .sln filename
# ---------------------------------------------------------------------------


def test_system_name_from_sln(tmp_path):
    """SystemDetector.detect_system_name() should return the .sln stem."""
    sln_path = tmp_path / "wps.core.sln"
    sln_path.write_text(SLN_CONTENT, encoding="utf-8")

    detector = SystemDetector(repo_path=tmp_path, llm_manager=None)
    name = detector.detect_system_name()

    assert name == "wps.core"
