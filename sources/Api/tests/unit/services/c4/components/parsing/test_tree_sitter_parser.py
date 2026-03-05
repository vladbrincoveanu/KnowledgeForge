"""Tests for TreeSitterParser."""

import pytest

from app.services.c4.components.parsing import ParsedFile, TreeSitterParser


@pytest.fixture
def parser() -> TreeSitterParser:
    return TreeSitterParser()


def test_parse_file_python(parser: TreeSitterParser, tmp_path):
    f = tmp_path / "hello.py"
    f.write_text("def hello(): pass\n")
    result = parser.parse_file(str(f))
    assert result is not None
    assert result.language == "python"
    assert result.tree.root_node is not None


def test_parse_file_java(parser: TreeSitterParser, tmp_path):
    f = tmp_path / "Hello.java"
    f.write_text("public class Hello {}\n")
    result = parser.parse_file(str(f))
    assert result is not None
    assert result.language == "java"
    assert result.tree.root_node is not None


def test_parse_file_unsupported(parser: TreeSitterParser, tmp_path):
    f = tmp_path / "readme.txt"
    f.write_text("just text\n")
    result = parser.parse_file(str(f))
    assert result is None


def test_parse_directory_finds_supported_files(parser: TreeSitterParser, tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    (tmp_path / "Main.java").write_text("public class Main {}\n")
    (tmp_path / "notes.txt").write_text("ignore me\n")
    results = parser.parse_directory(str(tmp_path))
    languages = {r.language for r in results}
    assert "python" in languages
    assert "java" in languages
    assert len(results) == 2


def test_parse_directory_skips_skip_dirs(parser: TreeSitterParser, tmp_path):
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / "lib.py").write_text("x = 1\n")
    (tmp_path / "app.py").write_text("y = 2\n")
    results = parser.parse_directory(str(tmp_path))
    paths = [r.file_path for r in results]
    assert not any("node_modules" in p for p in paths)
    assert len(results) == 1


def test_parse_directory_skips_test_files(parser: TreeSitterParser, tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    (tmp_path / "test_app.py").write_text("def test_x(): pass\n")
    results = parser.parse_directory(str(tmp_path), skip_tests=True)
    filenames = [r.file_path for r in results]
    assert not any("test_app" in p for p in filenames)
    assert len(results) == 1


def test_parse_directory_no_skip_tests(parser: TreeSitterParser, tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    (tmp_path / "test_app.py").write_text("def test_x(): pass\n")
    results = parser.parse_directory(str(tmp_path), skip_tests=False)
    assert len(results) == 2
