"""Unit tests for TypeScriptVisitor."""

from __future__ import annotations

from tree_sitter_language_pack import get_parser

from app.services.c4.components.models import ArchitecturalLayer, CodeElementKind
from app.services.c4.components.parsing.visitors.typescript_visitor import TypeScriptVisitor

_ts_parser = get_parser("typescript")
_js_parser = get_parser("javascript")


def _visit(source: bytes, file_path: str = "src/users/user.controller.ts", parser=None):
    p = parser if parser is not None else _ts_parser
    tree = p.parse(source)
    return TypeScriptVisitor().visit(tree, file_path, source)


NESTJS_SOURCE = b"""
import { Controller, Get } from '@nestjs/common';
import { Injectable } from '@nestjs/common';
import { Module } from '@nestjs/common';

@Controller('users')
export class UserController { }

@Injectable()
export class UserService {}

@Injectable()
export class UserRepository {}

@Module({})
export class AppModule {}
"""

EXPRESS_SOURCE = b"""
const express = require('express');
const router = express.Router();

async function getUser(req, res) { res.json({}); }
async function createUser(req, res) { res.json({}); }

router.get('/users', getUser);
router.post('/users', createUser);

module.exports = router;
"""


def test_supported_languages():
    v = TypeScriptVisitor()
    assert "typescript" in v.supported_languages
    assert "javascript" in v.supported_languages


def test_nestjs_controller_is_presentation():
    elements = _visit(NESTJS_SOURCE)
    el = next(e for e in elements if "UserController" in e.qualified_name)
    assert el.layer == ArchitecturalLayer.PRESENTATION


def test_nestjs_service_is_business():
    elements = _visit(NESTJS_SOURCE)
    el = next(e for e in elements if "UserService" in e.qualified_name)
    assert el.layer == ArchitecturalLayer.BUSINESS


def test_nestjs_repository_is_data_access():
    elements = _visit(NESTJS_SOURCE)
    el = next(e for e in elements if "UserRepository" in e.qualified_name)
    assert el.layer == ArchitecturalLayer.DATA_ACCESS


def test_module_class_is_skipped():
    elements = _visit(NESTJS_SOURCE)
    names = [e.qualified_name for e in elements]
    assert not any("AppModule" in n for n in names)


def test_qualified_name_format():
    elements = _visit(NESTJS_SOURCE)
    el = next(e for e in elements if "UserController" in e.qualified_name)
    assert "UserController" in el.qualified_name
    assert "." in el.qualified_name


def test_imports_captured():
    elements = _visit(NESTJS_SOURCE)
    el = next(e for e in elements if "UserController" in e.qualified_name)
    assert any("nestjs" in imp for imp in el.imports)


def test_express_handler_is_presentation():
    elements = _visit(
        EXPRESS_SOURCE,
        file_path="src/routes/users.js",
        parser=_js_parser,
    )
    el = next(e for e in elements if "getUser" in e.qualified_name)
    assert el.layer == ArchitecturalLayer.PRESENTATION


def test_empty_file_returns_empty_list():
    assert _visit(b"") == []
