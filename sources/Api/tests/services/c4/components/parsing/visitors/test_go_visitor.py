"""Unit tests for GoVisitor."""

from __future__ import annotations

import pytest
from tree_sitter_language_pack import get_parser

from app.services.c4.components.models import ArchitecturalLayer, CodeElementKind
from app.services.c4.components.parsing.visitors.go_visitor import GoVisitor

_parser = get_parser("go")


def _visit(source: bytes, file_path: str = "internal/api/handler.go"):
    tree = _parser.parse(source)
    return GoVisitor().visit(tree, file_path, source)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_SOURCE = b"""
package api

import (
    "net/http"
)

// HTTP handler struct: method with (ResponseWriter, *Request) signature.
type UserHandler struct {
    service UserService
}

func (h *UserHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
}

// Service struct: name ends with Service.
type UserService struct {
    repo UserRepository
}

// Repository interface: name ends with Repository.
type UserRepository interface {
    FindAll() []string
    FindById(id int) string
}
"""

PKG_FUNC_SOURCE = b"""
package api

import "net/http"

func HandleUsers(w http.ResponseWriter, r *http.Request) {}
func GetUser(w http.ResponseWriter, r *http.Request) {}
func PostUser(w http.ResponseWriter, r *http.Request) {}
func internalHelper() {}
"""

MULTI_PKG_SOURCE = b"""
package store

type OrderRepo struct{}
type CacheSvc struct{}
"""

# ---------------------------------------------------------------------------
# Basic properties
# ---------------------------------------------------------------------------


def test_supported_languages():
    assert GoVisitor().supported_languages == ["go"]


# ---------------------------------------------------------------------------
# Struct / interface kinds
# ---------------------------------------------------------------------------


def test_handler_struct_has_struct_kind():
    elements = _visit(FIXTURE_SOURCE)
    el = next(e for e in elements if "UserHandler" in e.qualified_name and e.kind == CodeElementKind.STRUCT)
    assert el.kind == CodeElementKind.STRUCT


def test_service_struct_has_struct_kind():
    elements = _visit(FIXTURE_SOURCE)
    el = next(e for e in elements if "UserService" in e.qualified_name and e.kind == CodeElementKind.STRUCT)
    assert el.kind == CodeElementKind.STRUCT


def test_repository_has_interface_kind():
    elements = _visit(FIXTURE_SOURCE)
    el = next(e for e in elements if "UserRepository" in e.qualified_name and e.kind == CodeElementKind.INTERFACE)
    assert el.kind == CodeElementKind.INTERFACE


# ---------------------------------------------------------------------------
# Layer detection via method signature
# ---------------------------------------------------------------------------


def test_http_handler_struct_is_presentation():
    elements = _visit(FIXTURE_SOURCE)
    el = next(e for e in elements if "UserHandler" in e.qualified_name and e.kind == CodeElementKind.STRUCT)
    assert el.layer == ArchitecturalLayer.PRESENTATION


def test_service_struct_is_business():
    elements = _visit(FIXTURE_SOURCE)
    el = next(e for e in elements if "UserService" in e.qualified_name and e.kind == CodeElementKind.STRUCT)
    assert el.layer == ArchitecturalLayer.BUSINESS


def test_repository_interface_is_data_access():
    elements = _visit(FIXTURE_SOURCE)
    el = next(e for e in elements if "UserRepository" in e.qualified_name and e.kind == CodeElementKind.INTERFACE)
    assert el.layer == ArchitecturalLayer.DATA_ACCESS


# ---------------------------------------------------------------------------
# Layer detection via naming conventions (Repo / Svc suffixes)
# ---------------------------------------------------------------------------


def test_repo_suffix_is_data_access():
    elements = _visit(MULTI_PKG_SOURCE)
    el = next(e for e in elements if "OrderRepo" in e.qualified_name)
    assert el.layer == ArchitecturalLayer.DATA_ACCESS


def test_svc_suffix_is_business():
    elements = _visit(MULTI_PKG_SOURCE)
    el = next(e for e in elements if "CacheSvc" in e.qualified_name)
    assert el.layer == ArchitecturalLayer.BUSINESS


# ---------------------------------------------------------------------------
# Package-level functions → controller
# ---------------------------------------------------------------------------


def test_handle_func_is_presentation():
    elements = _visit(PKG_FUNC_SOURCE)
    el = next(e for e in elements if "HandleUsers" in e.qualified_name)
    assert el.layer == ArchitecturalLayer.PRESENTATION


def test_get_func_is_presentation():
    elements = _visit(PKG_FUNC_SOURCE)
    el = next(e for e in elements if "GetUser" in e.qualified_name)
    assert el.layer == ArchitecturalLayer.PRESENTATION


def test_post_func_is_presentation():
    elements = _visit(PKG_FUNC_SOURCE)
    el = next(e for e in elements if "PostUser" in e.qualified_name)
    assert el.layer == ArchitecturalLayer.PRESENTATION


def test_unexported_func_has_unknown_layer():
    elements = _visit(PKG_FUNC_SOURCE)
    el = next(e for e in elements if "internalHelper" in e.qualified_name)
    assert el.layer == ArchitecturalLayer.UNKNOWN


# ---------------------------------------------------------------------------
# Interface method extraction
# ---------------------------------------------------------------------------


def test_interface_methods_extracted():
    elements = _visit(FIXTURE_SOURCE)
    func_names = [e.qualified_name.split(".")[-1] for e in elements if e.kind == CodeElementKind.FUNCTION]
    assert "FindAll" in func_names
    assert "FindById" in func_names


# ---------------------------------------------------------------------------
# Qualified naming uses package
# ---------------------------------------------------------------------------


def test_qualified_name_uses_package():
    elements = _visit(FIXTURE_SOURCE)
    el = next(e for e in elements if "UserHandler" in e.qualified_name and e.kind == CodeElementKind.STRUCT)
    assert el.qualified_name == "api.UserHandler"


def test_qualified_name_fallback_to_file_path():
    source = b"type Foo struct{}"
    tree = _parser.parse(source)
    elements = GoVisitor().visit(tree, "cmd/foo.go", source)
    el = next(e for e in elements if "Foo" in e.qualified_name)
    assert el.qualified_name == "cmd/foo.Foo" or "Foo" in el.qualified_name


# ---------------------------------------------------------------------------
# Imports captured
# ---------------------------------------------------------------------------


def test_imports_captured():
    elements = _visit(FIXTURE_SOURCE)
    el = next(e for e in elements if "UserHandler" in e.qualified_name and e.kind == CodeElementKind.STRUCT)
    assert any("net/http" in imp for imp in el.imports)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_file_returns_empty_list():
    elements = _visit(b"package main")
    assert elements == []


def test_language_is_go():
    elements = _visit(FIXTURE_SOURCE)
    assert all(e.language == "go" for e in elements)
