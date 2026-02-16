"""Central registry of supported languages and frameworks.

This module provides a single source of truth for:
- Programming language detection by file extension
- Framework detection patterns
- Helper functions for technology detection
"""

from typing import Optional

# Programming language detection by file extension
LANGUAGE_EXTENSIONS: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".swift": "Swift",
    ".scala": "Scala",
    ".ex": "Elixir",
    ".exs": "Elixir",
}

# Framework indicators: indicator -> (language, framework_name)
FRAMEWORK_INDICATORS: dict[str, tuple[str, str]] = {
    # Python frameworks
    "fastapi": ("Python", "FastAPI"),
    "flask": ("Python", "Flask"),
    "django": ("Python", "Django"),
    "starlette": ("Python", "Starlette"),
    # JavaScript/TypeScript frameworks
    "express": ("JavaScript", "Express"),
    "next": ("TypeScript", "Next.js"),
    "react": ("TypeScript", "React"),
    "vue": ("JavaScript", "Vue.js"),
    "nestjs": ("TypeScript", "NestJS"),
    "@nestjs": ("TypeScript", "NestJS"),
    # Go frameworks
    "gin-gonic": ("Go", "Gin"),
    "echo": ("Go", "Echo"),
    # Rust frameworks
    "actix-web": ("Rust", "Actix"),
    "axum": ("Rust", "Axum"),
    # Java frameworks
    "spring": ("Java", "Spring"),
    # .NET/C# frameworks (detected from <PackageReference> in .csproj)
    "microsoft.aspnetcore": ("C#", "ASP.NET Core"),
    "microsoft.aspnetcore.signalr": ("C#", "SignalR"),
    "grpc.aspnetcore": ("C#", "gRPC"),
    "microsoft.extensions.hosting": ("C#", "Worker Service"),
    "microsoft.servicebus": ("C#", "Azure Service Bus"),
    "blazor": ("C#", "Blazor"),
    "system.servicemodel": ("C#", "WCF"),
}


def get_language_by_extension(extension: str) -> Optional[str]:
    """Get programming language name from file extension.

    Args:
        extension: File extension (e.g., ".py", ".js")

    Returns:
        Language name if recognized, None otherwise

    Example:
        >>> get_language_by_extension(".py")
        'Python'
        >>> get_language_by_extension(".unknown")
        None
    """
    return LANGUAGE_EXTENSIONS.get(extension.lower())


def detect_frameworks_in_content(content: str) -> list[tuple[str, str]]:
    """Detect frameworks mentioned in file content.

    Args:
        content: File content to scan (e.g., package.json, requirements.txt)

    Returns:
        List of (language, framework) tuples found in content

    Example:
        >>> detect_frameworks_in_content('{"dependencies": {"fastapi": "0.100.0"}}')
        [('Python', 'FastAPI')]
    """
    found: list[tuple[str, str]] = []
    content_lower = content.lower()

    for indicator, (lang, framework) in FRAMEWORK_INDICATORS.items():
        if indicator in content_lower:
            found.append((lang, framework))

    return found


def get_all_supported_languages() -> list[str]:
    """Get list of all supported programming languages.

    Returns:
        Sorted list of unique language names
    """
    return sorted(set(LANGUAGE_EXTENSIONS.values()))


def get_all_supported_frameworks() -> list[tuple[str, str]]:
    """Get list of all supported frameworks.

    Returns:
        List of (language, framework) tuples, sorted by framework name
    """
    return sorted(set(FRAMEWORK_INDICATORS.values()), key=lambda x: x[1])


def get_extensions_for_language(language: str) -> list[str]:
    """Get all file extensions associated with a language.

    Args:
        language: Programming language name (e.g., "Python", "JavaScript")

    Returns:
        List of file extensions for that language

    Example:
        >>> get_extensions_for_language("Python")
        ['.py']
        >>> get_extensions_for_language("TypeScript")
        ['.ts', '.tsx']
    """
    return [ext for ext, lang in LANGUAGE_EXTENSIONS.items() if lang == language]
