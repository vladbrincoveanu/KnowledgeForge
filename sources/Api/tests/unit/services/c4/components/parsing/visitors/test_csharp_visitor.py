"""Unit tests for CSharpVisitor."""

from __future__ import annotations

import pytest
from tree_sitter_language_pack import get_parser

from app.services.c4.components.models import ArchitecturalLayer, CodeElementKind
from app.services.c4.components.parsing.visitors.csharp_visitor import CSharpVisitor

_parser = get_parser("csharp")


def _visit(source: bytes, file_path: str = "src/Controllers/UserController.cs"):
    tree = _parser.parse(source)
    return CSharpVisitor().visit(tree, file_path, source)


# ---------------------------------------------------------------------------
# Source fixtures
# ---------------------------------------------------------------------------

CONTROLLER_SOURCE = b"""
using Microsoft.AspNetCore.Mvc;
using System;

namespace MyApp.Controllers;

[ApiController]
public class UsersController : ControllerBase
{
    [HttpGet]
    public string GetUser() { return "user"; }

    [HttpPost]
    public string CreateUser() { return "ok"; }

    private string Helper() { return ""; }
}
"""

DBCONTEXT_SOURCE = b"""
using Microsoft.EntityFrameworkCore;

namespace MyApp.Data;

public class AppDbContext : DbContext
{
    public string GetUsers() { return ""; }
}
"""

RECORD_SOURCE = b"""
namespace MyApp.Models;

public record UserDto(int Id, string Name);
"""

INTERFACE_SOURCE = b"""
namespace MyApp.Services;

public interface IUserService
{
}
"""

MULTI_SOURCE = b"""
using System;

namespace MyApp.Web
{
    [ApiController]
    public class OrderController
    {
        [HttpDelete]
        public void Delete() { }
    }

    public interface IOrderRepo { }
}
"""

AUTHORIZE_SOURCE = b"""
namespace MyApp.Controllers;

[Authorize]
public class SecureController
{
    public string Secret() { return ""; }
}
"""

FILE_SCOPED_NS_SOURCE = b"""
namespace MyApp.Payments;

[ApiController]
public class PaymentsController
{
    [HttpPut]
    public string Update() { return "ok"; }
}
"""

EMPTY_SOURCE = b""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_supported_languages():
    assert CSharpVisitor().supported_languages == ["csharp"]


# --- Controller detection ---

def test_api_controller_is_presentation():
    elements = _visit(CONTROLLER_SOURCE)
    el = next(e for e in elements if "UsersController" in e.qualified_name and e.kind == CodeElementKind.CLASS)
    assert el.layer == ArchitecturalLayer.PRESENTATION


def test_api_controller_annotations_captured():
    elements = _visit(CONTROLLER_SOURCE)
    el = next(e for e in elements if "UsersController" in e.qualified_name and e.kind == CodeElementKind.CLASS)
    assert "ApiController" in el.annotations


# --- HTTP verb attributes on methods ---

def test_http_get_method_extracted():
    elements = _visit(CONTROLLER_SOURCE)
    method = next(
        (e for e in elements if e.kind == CodeElementKind.FUNCTION and "GetUser" in e.qualified_name),
        None,
    )
    assert method is not None
    assert "HttpGet" in method.annotations


def test_http_post_method_extracted():
    elements = _visit(CONTROLLER_SOURCE)
    method = next(
        (e for e in elements if e.kind == CodeElementKind.FUNCTION and "CreateUser" in e.qualified_name),
        None,
    )
    assert method is not None
    assert "HttpPost" in method.annotations


def test_http_delete_method_extracted():
    elements = _visit(MULTI_SOURCE)
    method = next(
        (e for e in elements if e.kind == CodeElementKind.FUNCTION and "Delete" in e.qualified_name),
        None,
    )
    assert method is not None
    assert "HttpDelete" in method.annotations


# --- Private method not extracted ---

def test_private_method_not_extracted():
    elements = _visit(CONTROLLER_SOURCE)
    names = [e.qualified_name.split(".")[-1] for e in elements if e.kind == CodeElementKind.FUNCTION]
    assert "Helper" not in names


# --- DbContext → DATA_ACCESS ---

def test_dbcontext_is_data_access():
    elements = _visit(DBCONTEXT_SOURCE)
    el = next(e for e in elements if "AppDbContext" in e.qualified_name and e.kind == CodeElementKind.CLASS)
    assert el.layer == ArchitecturalLayer.DATA_ACCESS


def test_dbcontext_base_class_captured():
    elements = _visit(DBCONTEXT_SOURCE)
    el = next(e for e in elements if "AppDbContext" in e.qualified_name and e.kind == CodeElementKind.CLASS)
    assert any("DbContext" in bc for bc in el.base_classes)


# --- Record filtering ---

def test_record_is_filtered():
    elements = _visit(RECORD_SOURCE)
    el = next(e for e in elements if "UserDto" in e.qualified_name)
    assert el.filtered is True
    assert el.filter_reason == "record"


# --- Namespace extraction ---

def test_qualified_name_uses_namespace_file_scoped():
    elements = _visit(FILE_SCOPED_NS_SOURCE, file_path="src/Payments/PaymentsController.cs")
    el = next(e for e in elements if "PaymentsController" in e.qualified_name and e.kind == CodeElementKind.CLASS)
    assert el.qualified_name == "MyApp.Payments.PaymentsController"


def test_qualified_name_uses_namespace_block():
    elements = _visit(MULTI_SOURCE, file_path="src/Web/OrderController.cs")
    el = next(e for e in elements if "OrderController" in e.qualified_name and e.kind == CodeElementKind.CLASS)
    assert el.qualified_name == "MyApp.Web.OrderController"


# --- Interface ---

def test_interface_kind():
    elements = _visit(INTERFACE_SOURCE)
    el = next(e for e in elements if "IUserService" in e.qualified_name)
    assert el.kind == CodeElementKind.INTERFACE


# --- Authorize → middleware ---

def test_authorize_annotation_captured():
    elements = _visit(AUTHORIZE_SOURCE)
    el = next(e for e in elements if "SecureController" in e.qualified_name and e.kind == CodeElementKind.CLASS)
    assert "Authorize" in el.annotations


# --- Using directives as imports ---

def test_usings_captured_as_imports():
    elements = _visit(CONTROLLER_SOURCE)
    el = next(e for e in elements if "UsersController" in e.qualified_name and e.kind == CodeElementKind.CLASS)
    assert any("Microsoft.AspNetCore.Mvc" in imp for imp in el.imports)


# --- HttpPut method ---

def test_http_put_method_extracted():
    elements = _visit(FILE_SCOPED_NS_SOURCE)
    method = next(
        (e for e in elements if e.kind == CodeElementKind.FUNCTION and "Update" in e.qualified_name),
        None,
    )
    assert method is not None
    assert "HttpPut" in method.annotations


# --- Empty file ---

def test_empty_file_returns_empty_list():
    elements = _visit(EMPTY_SOURCE)
    assert elements == []
