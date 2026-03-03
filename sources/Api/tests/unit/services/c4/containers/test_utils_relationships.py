"""Unit tests for relationship utility functions in utils.py."""

import pytest

from app.services.c4.containers.utils import (
    infer_protocol_from_port,
    normalize_depends_on,
    extract_named_volume,
    infer_relationship_type_from_image,
    flatten_dict,
)


class TestInferProtocolFromPort:
    def test_known_postgres_port(self):
        assert infer_protocol_from_port("5432") == "PostgreSQL"

    def test_known_redis_port(self):
        assert infer_protocol_from_port("6379") == "Redis"

    def test_known_kafka_port(self):
        assert infer_protocol_from_port("9092") == "Kafka"

    def test_known_grpc_port(self):
        assert infer_protocol_from_port("50051") == "gRPC"

    def test_known_http_port_80(self):
        assert infer_protocol_from_port("80") == "HTTP"

    def test_known_http_port_8080(self):
        assert infer_protocol_from_port("8080") == "HTTP"

    def test_unknown_port_returns_tcp(self):
        assert infer_protocol_from_port("12345") == "TCP"

    def test_strips_whitespace(self):
        assert infer_protocol_from_port("  5432  ") == "PostgreSQL"


class TestNormalizeDependsOn:
    def test_list_form(self):
        assert normalize_depends_on(["db", "redis"]) == ["db", "redis"]

    def test_dict_form(self):
        result = normalize_depends_on({"db": {"condition": "service_healthy"}, "redis": {}})
        assert sorted(result) == ["db", "redis"]

    def test_empty_list(self):
        assert normalize_depends_on([]) == []

    def test_empty_dict(self):
        assert normalize_depends_on({}) == []

    def test_none_returns_empty(self):
        assert normalize_depends_on(None) == []

    def test_non_standard_type_returns_empty(self):
        assert normalize_depends_on("db") == []

    def test_list_coerces_elements_to_str(self):
        result = normalize_depends_on([1, 2])
        assert result == ["1", "2"]


class TestExtractNamedVolume:
    def test_named_volume(self):
        assert extract_named_volume("pgdata:/var/lib/postgresql/data") == "pgdata"

    def test_named_volume_no_target(self):
        assert extract_named_volume("pgdata") == "pgdata"

    def test_bind_mount_absolute_path(self):
        assert extract_named_volume("/host/path:/container/path") is None

    def test_bind_mount_relative_path(self):
        assert extract_named_volume("./local:/container") is None

    def test_tilde_path(self):
        assert extract_named_volume("~/data:/data") is None

    def test_none_input(self):
        assert extract_named_volume(None) is None

    def test_empty_string(self):
        assert extract_named_volume("") is None


class TestInferRelationshipTypeFromImage:
    def test_kafka_image(self):
        protocol, rel_type = infer_relationship_type_from_image("confluentinc/cp-kafka:7.0")
        assert protocol == "Kafka"
        assert rel_type == "publishes-to"

    def test_rabbitmq_image(self):
        protocol, rel_type = infer_relationship_type_from_image("rabbitmq:3-management")
        assert protocol == "AMQP"
        assert rel_type == "publishes-to"

    def test_redis_image(self):
        protocol, rel_type = infer_relationship_type_from_image("redis:7-alpine")
        assert protocol == "Redis"
        assert rel_type == "uses"

    def test_nats_image(self):
        protocol, rel_type = infer_relationship_type_from_image("nats:2.9")
        assert protocol == "NATS"
        assert rel_type == "publishes-to"

    def test_generic_api_image(self):
        protocol, rel_type = infer_relationship_type_from_image("my-api:latest")
        assert protocol == "HTTP"
        assert rel_type == "uses"

    def test_none_image(self):
        protocol, rel_type = infer_relationship_type_from_image(None)
        assert protocol == "HTTP"
        assert rel_type == "uses"

    def test_empty_image(self):
        protocol, rel_type = infer_relationship_type_from_image("")
        assert protocol == "HTTP"
        assert rel_type == "uses"


class TestFlattenDict:
    def test_flat_dict(self):
        result = dict(flatten_dict({"a": 1, "b": 2}))
        assert result == {"a": 1, "b": 2}

    def test_nested_dict(self):
        result = dict(flatten_dict({"a": {"b": {"c": 42}}}))
        assert result == {"a.b.c": 42}

    def test_mixed_depth(self):
        result = dict(flatten_dict({"x": 1, "y": {"z": 2}}))
        assert result == {"x": 1, "y.z": 2}

    def test_empty_dict(self):
        assert flatten_dict({}) == []
