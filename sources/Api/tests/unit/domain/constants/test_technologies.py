"""Unit tests for technologies constants module."""

import pytest

from app.domain.constants.technologies import (
    LANGUAGE_EXTENSIONS,
    FRAMEWORK_INDICATORS,
    get_language_by_extension,
    detect_frameworks_in_content,
    get_all_supported_languages,
    get_all_supported_frameworks,
    get_extensions_for_language,
)


class TestLanguageExtensions:
    """Test language extension mapping."""

    def test_language_extensions_contains_common_languages(self):
        """Test that common language extensions are present."""
        assert LANGUAGE_EXTENSIONS[".py"] == "Python"
        assert LANGUAGE_EXTENSIONS[".js"] == "JavaScript"
        assert LANGUAGE_EXTENSIONS[".ts"] == "TypeScript"
        assert LANGUAGE_EXTENSIONS[".go"] == "Go"
        assert LANGUAGE_EXTENSIONS[".java"] == "Java"

    def test_language_extensions_completeness(self):
        """Test that all expected languages are covered."""
        expected_languages = {
            "Python", "JavaScript", "TypeScript", "Go", "Rust", "Java",
            "Kotlin", "Ruby", "PHP", "C#", "C++", "C", "Swift", "Scala", "Elixir"
        }
        actual_languages = set(LANGUAGE_EXTENSIONS.values())
        assert expected_languages.issubset(actual_languages)

    def test_get_language_by_extension_success(self):
        """Test successful language lookup."""
        assert get_language_by_extension(".py") == "Python"
        assert get_language_by_extension(".js") == "JavaScript"
        assert get_language_by_extension(".ts") == "TypeScript"

    def test_get_language_by_extension_case_insensitive(self):
        """Test case-insensitive extension lookup."""
        assert get_language_by_extension(".PY") == "Python"
        assert get_language_by_extension(".JS") == "JavaScript"
        assert get_language_by_extension(".Ts") == "TypeScript"

    def test_get_language_by_extension_not_found(self):
        """Test lookup for unknown extension."""
        assert get_language_by_extension(".unknown") is None
        assert get_language_by_extension(".xyz") is None

    def test_get_extensions_for_language(self):
        """Test getting extensions for a language."""
        python_exts = get_extensions_for_language("Python")
        assert ".py" in python_exts

        ts_exts = get_extensions_for_language("TypeScript")
        assert ".ts" in ts_exts
        assert ".tsx" in ts_exts

    def test_get_extensions_for_unknown_language(self):
        """Test getting extensions for unknown language."""
        assert get_extensions_for_language("UnknownLang") == []


class TestFrameworkIndicators:
    """Test framework detection patterns."""

    def test_framework_indicators_contains_common_frameworks(self):
        """Test that common frameworks are present."""
        assert FRAMEWORK_INDICATORS["fastapi"] == ("Python", "FastAPI")
        assert FRAMEWORK_INDICATORS["flask"] == ("Python", "Flask")
        assert FRAMEWORK_INDICATORS["express"] == ("JavaScript", "Express")
        assert FRAMEWORK_INDICATORS["react"] == ("TypeScript", "React")
        assert FRAMEWORK_INDICATORS["spring"] == ("Java", "Spring")

    def test_framework_indicators_completeness(self):
        """Test that major frameworks are covered."""
        expected_frameworks = {
            ("Python", "FastAPI"),
            ("Python", "Flask"),
            ("Python", "Django"),
            ("JavaScript", "Express"),
            ("TypeScript", "React"),
            ("TypeScript", "Next.js"),
            ("Java", "Spring"),
            ("Go", "Gin"),
            ("Rust", "Actix"),
        }
        actual_frameworks = set(FRAMEWORK_INDICATORS.values())
        assert expected_frameworks.issubset(actual_frameworks)

    def test_detect_frameworks_in_content_single_framework(self):
        """Test detecting single framework in content."""
        content = '{"dependencies": {"fastapi": "0.100.0"}}'
        frameworks = detect_frameworks_in_content(content)
        assert ("Python", "FastAPI") in frameworks

    def test_detect_frameworks_in_content_multiple_frameworks(self):
        """Test detecting multiple frameworks in content."""
        content = 'import fastapi\nimport flask\nimport react'
        frameworks = detect_frameworks_in_content(content)
        assert ("Python", "FastAPI") in frameworks
        assert ("Python", "Flask") in frameworks
        assert ("TypeScript", "React") in frameworks

    def test_detect_frameworks_in_content_case_insensitive(self):
        """Test case-insensitive framework detection."""
        content = "FASTAPI Flask DJANGO"
        frameworks = detect_frameworks_in_content(content)
        assert ("Python", "FastAPI") in frameworks
        assert ("Python", "Flask") in frameworks
        assert ("Python", "Django") in frameworks

    def test_detect_frameworks_in_content_no_frameworks(self):
        """Test content with no frameworks."""
        content = "some random text without frameworks"
        frameworks = detect_frameworks_in_content(content)
        # Should return empty list or only accidental matches
        # We don't expect any of the major frameworks to match random text
        assert len(frameworks) == 0 or all(fw[1] not in ["FastAPI", "Flask", "React"] for fw in frameworks)

    def test_detect_frameworks_real_package_json(self):
        """Test with realistic package.json content."""
        content = '''
        {
            "dependencies": {
                "express": "^4.18.0",
                "react": "^18.0.0",
                "next": "^13.0.0"
            }
        }
        '''
        frameworks = detect_frameworks_in_content(content)
        assert ("JavaScript", "Express") in frameworks
        assert ("TypeScript", "React") in frameworks
        assert ("TypeScript", "Next.js") in frameworks

    def test_detect_frameworks_real_requirements_txt(self):
        """Test with realistic requirements.txt content."""
        content = '''
        fastapi==0.100.0
        flask==2.3.0
        django==4.2.0
        starlette==0.27.0
        '''
        frameworks = detect_frameworks_in_content(content)
        assert ("Python", "FastAPI") in frameworks
        assert ("Python", "Flask") in frameworks
        assert ("Python", "Django") in frameworks
        assert ("Python", "Starlette") in frameworks


class TestHelperFunctions:
    """Test helper utility functions."""

    def test_get_all_supported_languages(self):
        """Test getting list of all supported languages."""
        languages = get_all_supported_languages()
        assert isinstance(languages, list)
        assert len(languages) > 0
        assert "Python" in languages
        assert "JavaScript" in languages
        assert "TypeScript" in languages
        # Should be sorted
        assert languages == sorted(languages)

    def test_get_all_supported_languages_unique(self):
        """Test that returned languages are unique."""
        languages = get_all_supported_languages()
        assert len(languages) == len(set(languages))

    def test_get_all_supported_frameworks(self):
        """Test getting list of all supported frameworks."""
        frameworks = get_all_supported_frameworks()
        assert isinstance(frameworks, list)
        assert len(frameworks) > 0
        assert ("Python", "FastAPI") in frameworks
        assert ("JavaScript", "Express") in frameworks
        assert ("TypeScript", "React") in frameworks

    def test_get_all_supported_frameworks_sorted(self):
        """Test that frameworks are sorted by framework name."""
        frameworks = get_all_supported_frameworks()
        framework_names = [fw[1] for fw in frameworks]
        assert framework_names == sorted(framework_names)

    def test_get_all_supported_frameworks_unique(self):
        """Test that returned frameworks are unique."""
        frameworks = get_all_supported_frameworks()
        assert len(frameworks) == len(set(frameworks))
