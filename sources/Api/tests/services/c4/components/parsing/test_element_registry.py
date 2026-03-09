"""Unit tests for ElementRegistry."""

from __future__ import annotations

import pytest

from app.services.c4.components.models import ArchitecturalLayer, CodeElement, CodeElementKind
from app.services.c4.components.parsing.element_registry import ElementRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _elem(
    qualified_name: str = "pkg.Foo",
    kind: CodeElementKind = CodeElementKind.CLASS,
    file_path: str = "pkg/foo.py",
    language: str = "python",
    annotations: list[str] | None = None,
    imports: list[str] | None = None,
    base_classes: list[str] | None = None,
    method_calls: list[str] | None = None,
    layer: ArchitecturalLayer = ArchitecturalLayer.UNKNOWN,
    role: str = "",
    metadata: dict | None = None,
) -> CodeElement:
    return CodeElement(
        qualified_name=qualified_name,
        kind=kind,
        file_path=file_path,
        language=language,
        annotations=annotations or [],
        imports=imports or [],
        base_classes=base_classes or [],
        method_calls=method_calls or [],
        layer=layer,
        role=role,
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# Basic collection
# ---------------------------------------------------------------------------


def test_add_and_retrieve_elements():
    reg = ElementRegistry()
    a = _elem("pkg.A")
    b = _elem("pkg.B")
    reg.add_elements([a, b])
    names = {e.qualified_name for e in reg.get_all()}
    assert names == {"pkg.A", "pkg.B"}


def test_empty_registry_returns_empty():
    assert ElementRegistry().get_all() == []


def test_multiple_add_calls_accumulate():
    reg = ElementRegistry()
    reg.add_elements([_elem("pkg.A")])
    reg.add_elements([_elem("pkg.B")])
    assert len(reg.get_all()) == 2


# ---------------------------------------------------------------------------
# Deduplication – keep richest metadata
# ---------------------------------------------------------------------------


def test_dedup_keeps_only_one_per_qualified_name():
    reg = ElementRegistry()
    reg.add_elements([_elem("pkg.A"), _elem("pkg.A")])
    assert len(reg.get_all()) == 1


def test_dedup_richer_annotations_wins():
    reg = ElementRegistry()
    sparse = _elem("pkg.A")
    rich = _elem("pkg.A", annotations=["@Service", "@Transactional"])
    reg.add_elements([sparse, rich])
    result = reg.get_all()
    assert result[0].annotations == ["@Service", "@Transactional"]


def test_dedup_richer_imports_wins():
    reg = ElementRegistry()
    sparse = _elem("pkg.A")
    rich = _elem("pkg.A", imports=["os", "sys", "typing"])
    reg.add_elements([rich, sparse])
    result = reg.get_all()
    assert len(result[0].imports) == 3


def test_dedup_known_layer_beats_unknown():
    reg = ElementRegistry()
    unknown = _elem("pkg.A", layer=ArchitecturalLayer.UNKNOWN)
    known = _elem("pkg.A", layer=ArchitecturalLayer.BUSINESS)
    reg.add_elements([unknown, known])
    result = reg.get_all()
    assert result[0].layer == ArchitecturalLayer.BUSINESS


def test_dedup_non_empty_role_beats_empty():
    reg = ElementRegistry()
    no_role = _elem("pkg.A")
    with_role = _elem("pkg.A", role="user-service")
    reg.add_elements([no_role, with_role])
    result = reg.get_all()
    assert result[0].role == "user-service"


def test_dedup_equal_richness_keeps_first():
    reg = ElementRegistry()
    first = _elem("pkg.A", annotations=["@X"])
    second = _elem("pkg.A", annotations=["@Y"])
    reg.add_elements([first, second])
    result = reg.get_all()
    assert result[0].annotations == ["@X"]


# ---------------------------------------------------------------------------
# Filtering – generated code
# ---------------------------------------------------------------------------


def test_protobuf_generated_file_is_flagged():
    reg = ElementRegistry()
    el = _elem("proto.FooMessage", file_path="proto/foo_pb2.py")
    reg.add_elements([el])
    result = reg.get_all()
    assert result[0].filtered is True
    assert result[0].filter_reason != ""


def test_generated_dotted_extension_is_flagged():
    reg = ElementRegistry()
    el = _elem("gen.Model", file_path="src/models.generated.ts")
    reg.add_elements([el])
    assert reg.get_all()[0].filtered is True


def test_generated_file_excluded_from_architectural():
    reg = ElementRegistry()
    reg.add_elements([_elem("proto.Msg", file_path="proto/foo_pb2.py")])
    assert reg.get_architectural_elements() == []


def test_normal_file_not_flagged_as_generated():
    reg = ElementRegistry()
    el = _elem("pkg.Foo", file_path="pkg/foo.py")
    reg.add_elements([el])
    assert reg.get_all()[0].filtered is False


# ---------------------------------------------------------------------------
# Filtering – data-only classes
# ---------------------------------------------------------------------------


def test_data_only_class_flagged_when_metadata_present():
    reg = ElementRegistry()
    el = _elem("pkg.Dto", metadata={"field_count": 8, "method_count": 1})
    reg.add_elements([el])
    result = reg.get_all()
    assert result[0].filtered is True
    assert "data" in result[0].filter_reason.lower()


def test_data_only_boundary_70_percent_fields():
    # Exactly 70%: 7 fields out of 10 total, 3 methods → not filtered (>70% required)
    reg = ElementRegistry()
    el = _elem("pkg.Dto", metadata={"field_count": 7, "method_count": 3})
    reg.add_elements([el])
    assert reg.get_all()[0].filtered is False


def test_data_only_71_percent_fields_2_methods_flagged():
    reg = ElementRegistry()
    el = _elem("pkg.Dto", metadata={"field_count": 5, "method_count": 2})
    reg.add_elements([el])
    # 5/(5+2) ≈ 71.4% and method_count < 3 → flagged
    assert reg.get_all()[0].filtered is True


def test_class_with_3_methods_not_flagged_even_if_high_field_ratio():
    reg = ElementRegistry()
    el = _elem("pkg.Dto", metadata={"field_count": 9, "method_count": 3})
    reg.add_elements([el])
    # field_ratio > 70% but method_count == 3 (not < 3) → not flagged
    assert reg.get_all()[0].filtered is False


def test_no_metadata_field_counts_not_flagged():
    reg = ElementRegistry()
    el = _elem("pkg.Foo")
    reg.add_elements([el])
    assert reg.get_all()[0].filtered is False


# ---------------------------------------------------------------------------
# Filtering – all-static utility classes
# ---------------------------------------------------------------------------


def test_all_static_class_flagged_via_metadata():
    reg = ElementRegistry()
    el = _elem("pkg.Utils", metadata={"all_static": True})
    reg.add_elements([el])
    result = reg.get_all()
    assert result[0].filtered is True
    assert "static" in result[0].filter_reason.lower()


def test_non_static_class_not_flagged():
    reg = ElementRegistry()
    el = _elem("pkg.Utils", metadata={"all_static": False})
    reg.add_elements([el])
    assert reg.get_all()[0].filtered is False


# ---------------------------------------------------------------------------
# get_architectural_elements
# ---------------------------------------------------------------------------


def test_get_architectural_elements_excludes_filtered():
    reg = ElementRegistry()
    reg.add_elements([
        _elem("pkg.Service", layer=ArchitecturalLayer.BUSINESS),
        _elem("proto.Msg", file_path="proto/foo_pb2.py"),
        _elem("pkg.Utils", metadata={"all_static": True}),
    ])
    arch = reg.get_architectural_elements()
    names = {e.qualified_name for e in arch}
    assert names == {"pkg.Service"}


def test_get_architectural_elements_includes_non_filtered():
    reg = ElementRegistry()
    reg.add_elements([
        _elem("pkg.A"),
        _elem("pkg.B"),
    ])
    assert len(reg.get_architectural_elements()) == 2


# ---------------------------------------------------------------------------
# Idempotency – calling get_all twice doesn't double-flag
# ---------------------------------------------------------------------------


def test_repeated_get_all_does_not_alter_filter_reason():
    reg = ElementRegistry()
    el = _elem("proto.Msg", file_path="proto/foo_pb2.py")
    reg.add_elements([el])
    first = reg.get_all()[0].filter_reason
    second = reg.get_all()[0].filter_reason
    assert first == second
