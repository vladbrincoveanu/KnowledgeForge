"""Unit tests for JavaVisitor."""

from __future__ import annotations

import pytest
from tree_sitter_language_pack import get_parser

from app.services.c4.components.models import ArchitecturalLayer, CodeElementKind
from app.services.c4.components.parsing.visitors.java_visitor import JavaVisitor

_parser = get_parser("java")


def _visit(source: bytes, file_path: str = "src/main/java/com/example/App.java"):
    tree = _parser.parse(source)
    return JavaVisitor().visit(tree, file_path, source)


MULTI_SOURCE = b"""
package com.example.app;

import org.springframework.web.bind.annotation.RestController;
import org.springframework.stereotype.Service;
import org.springframework.stereotype.Repository;
import javax.persistence.Entity;

@RestController
public class UserController {
    public String getUser() { return "user"; }
    private String helper() { return ""; }
}

@Service
public class UserService { }

@Repository
public interface UserRepository { }

@Entity
public class User { }
"""

CONFIG_SOURCE = b"""
package com.example.app;

import org.springframework.context.annotation.Configuration;

@Configuration
public class AppConfig { }
"""


def test_supported_languages():
    assert JavaVisitor().supported_languages == ["java"]


def test_rest_controller_is_presentation():
    elements = _visit(MULTI_SOURCE)
    el = next(e for e in elements if "UserController" in e.qualified_name and e.kind == CodeElementKind.CLASS)
    assert el.layer == ArchitecturalLayer.PRESENTATION


def test_service_is_business():
    elements = _visit(MULTI_SOURCE)
    el = next(e for e in elements if "UserService" in e.qualified_name)
    assert el.layer == ArchitecturalLayer.BUSINESS


def test_repository_interface_is_data_access():
    elements = _visit(MULTI_SOURCE)
    el = next(e for e in elements if "UserRepository" in e.qualified_name)
    assert el.layer == ArchitecturalLayer.DATA_ACCESS
    assert el.kind == CodeElementKind.INTERFACE


def test_entity_is_skipped():
    elements = _visit(MULTI_SOURCE)
    names = [e.qualified_name for e in elements]
    assert not any("User" == n.split(".")[-1] for n in names)


def test_qualified_name_uses_package():
    elements = _visit(MULTI_SOURCE)
    el = next(e for e in elements if "UserController" in e.qualified_name and e.kind == CodeElementKind.CLASS)
    assert el.qualified_name == "com.example.app.UserController"


def test_imports_captured():
    elements = _visit(MULTI_SOURCE)
    el = next(e for e in elements if "UserController" in e.qualified_name and e.kind == CodeElementKind.CLASS)
    assert any("springframework" in imp for imp in el.imports)


def test_public_method_extracted():
    elements = _visit(MULTI_SOURCE)
    names = [e.qualified_name.split(".")[-1] for e in elements if e.kind == CodeElementKind.FUNCTION]
    assert "getUser" in names


def test_private_method_not_extracted():
    elements = _visit(MULTI_SOURCE)
    names = [e.qualified_name.split(".")[-1] for e in elements if e.kind == CodeElementKind.FUNCTION]
    assert "helper" not in names


def test_empty_file_returns_empty_list():
    elements = _visit(b"")
    assert elements == []


def test_configuration_class_is_infrastructure():
    elements = _visit(CONFIG_SOURCE)
    el = next(e for e in elements if "AppConfig" in e.qualified_name)
    assert el.layer == ArchitecturalLayer.INFRASTRUCTURE
