"""Unit tests for relationship_extractor.py."""

import json
import textwrap
from pathlib import Path

import pytest
import yaml

from app.services.c4.containers.relationship_extractor import (
    ConfigRelationshipExtractor,
    EnvVarRelationshipExtractor,
)
from app.services.c4.containers.utils import (
    infer_direction_from_env_name,
    parse_connection_string,
)


# ---------------------------------------------------------------------------
# parse_connection_string
# ---------------------------------------------------------------------------

class TestParseConnectionString:
    def test_postgresql_url(self):
        result = parse_connection_string("postgresql://db:5432/myapp")
        assert result["protocol"] == "PostgreSQL"
        assert result["host"] == "db"
        assert result["port"] == "5432"
        assert result["database"] == "myapp"

    def test_postgres_alias(self):
        result = parse_connection_string("postgres://user:pass@postgres-host:5432/orders")
        assert result["protocol"] == "PostgreSQL"
        assert result["host"] == "postgres-host"

    def test_mongodb_url(self):
        result = parse_connection_string("mongodb://mongo:27017/catalog")
        assert result["protocol"] == "MongoDB"
        assert result["host"] == "mongo"
        assert result["port"] == "27017"

    def test_redis_url(self):
        result = parse_connection_string("redis://redis-service:6379")
        assert result["protocol"] == "Redis"
        assert result["host"] == "redis-service"
        assert result["port"] == "6379"

    def test_amqp_url(self):
        result = parse_connection_string("amqp://guest:guest@rabbitmq:5672/")
        assert result["protocol"] == "AMQP"
        assert result["host"] == "rabbitmq"

    def test_kafka_url(self):
        result = parse_connection_string("kafka://kafka-broker:9092")
        assert result["protocol"] == "Kafka"
        assert result["host"] == "kafka-broker"

    def test_http_url(self):
        result = parse_connection_string("http://payment-service:8080/api")
        assert result["protocol"] == "HTTP"
        assert result["host"] == "payment-service"

    def test_grpc_url(self):
        result = parse_connection_string("grpc://grpc-server:50051")
        assert result["protocol"] == "gRPC"
        assert result["host"] == "grpc-server"
        assert result["port"] == "50051"

    def test_sqlserver_connection_string(self):
        result = parse_connection_string("Server=tcp:sql-server,1433;Database=Orders;")
        assert result["protocol"] == "SQLServer"
        assert result["host"] == "sql-server"
        assert result["port"] == "1433"

    def test_sqlserver_no_port(self):
        result = parse_connection_string("Server=tcp:sql-host;Initial Catalog=DB;")
        assert result["protocol"] == "SQLServer"
        assert result["host"] == "sql-host"

    def test_jdbc_postgresql(self):
        result = parse_connection_string("jdbc:postgresql://pg-host:5432/inventory")
        assert result["protocol"] == "PostgreSQL"
        assert result["host"] == "pg-host"
        assert result["database"] == "inventory"

    def test_jdbc_mysql(self):
        result = parse_connection_string("jdbc:mysql://mysql-host:3306/users")
        assert result["protocol"] == "MySQL"
        assert result["host"] == "mysql-host"

    def test_none_input(self):
        assert parse_connection_string(None) is None

    def test_empty_string(self):
        assert parse_connection_string("") is None

    def test_plain_value_no_scheme(self):
        assert parse_connection_string("/var/run/app.sock") is None

    def test_non_connection_string(self):
        assert parse_connection_string("some-random-config-value") is None


# ---------------------------------------------------------------------------
# infer_direction_from_env_name
# ---------------------------------------------------------------------------

class TestInferDirectionFromEnvName:
    def test_output_topic_publishes_to(self):
        assert infer_direction_from_env_name("OUTPUT_TOPIC") == "publishes-to"

    def test_producer_publishes_to(self):
        assert infer_direction_from_env_name("KAFKA_PRODUCER_TOPIC") == "publishes-to"

    def test_publisher_publishes_to(self):
        assert infer_direction_from_env_name("PUBLISHER_URL") == "publishes-to"

    def test_input_topic_subscribes_to(self):
        assert infer_direction_from_env_name("INPUT_TOPIC") == "subscribes-to"

    def test_consumer_group_subscribes_to(self):
        assert infer_direction_from_env_name("CONSUMER_GROUP") == "subscribes-to"

    def test_subscriber_subscribes_to(self):
        assert infer_direction_from_env_name("SUBSCRIBER_URL") == "subscribes-to"

    def test_listener_subscribes_to(self):
        assert infer_direction_from_env_name("EVENT_LISTENER_ADDR") == "subscribes-to"

    def test_receiver_subscribes_to(self):
        assert infer_direction_from_env_name("INBOX_RECEIVER") == "subscribes-to"

    def test_generic_url_uses(self):
        assert infer_direction_from_env_name("DATABASE_URL") == "uses"

    def test_empty_string_uses(self):
        assert infer_direction_from_env_name("") == "uses"

    def test_none_uses(self):
        assert infer_direction_from_env_name(None) == "uses"


# ---------------------------------------------------------------------------
# EnvVarRelationshipExtractor — K8s list form
# ---------------------------------------------------------------------------

class TestEnvVarRelationshipExtractorList:
    def _extractor(self):
        return EnvVarRelationshipExtractor("order-service")

    def test_postgres_url_detected(self):
        env = [{"name": "DB_URL", "value": "postgresql://postgres:5432/orders"}]
        rels = self._extractor().extract(env)
        assert len(rels) == 1
        r = rels[0]
        assert r["from"] == "order-service"
        assert r["to"] == "postgres"
        assert r["protocol"] == "PostgreSQL"
        assert r["type"] == "uses"
        assert r["_unresolved"] is True

    def test_kafka_producer_topic(self):
        env = [{"name": "OUTPUT_TOPIC_URL", "value": "kafka://kafka:9092"}]
        rels = self._extractor().extract(env)
        assert len(rels) == 1
        assert rels[0]["type"] == "publishes-to"
        assert rels[0]["protocol"] == "Kafka"

    def test_topic_metadata_captured(self):
        env = [{"name": "ORDER_CREATED_TOPIC", "value": "kafka://kafka:9092"}]
        rels = self._extractor().extract(env)
        assert len(rels) == 1
        assert "topic" in rels[0]["metadata"]

    def test_queue_metadata_captured(self):
        env = [{"name": "PAYMENT_QUEUE_URL", "value": "amqp://rabbitmq:5672/"}]
        rels = self._extractor().extract(env)
        assert len(rels) == 1
        assert "queue" in rels[0]["metadata"]

    def test_noise_var_skipped(self):
        env = [{"name": "HOME", "value": "/root"}]
        rels = self._extractor().extract(env)
        assert rels == []

    def test_empty_value_skipped(self):
        env = [{"name": "DB_URL", "value": ""}]
        rels = self._extractor().extract(env)
        assert rels == []

    def test_none_env_list(self):
        rels = self._extractor().extract(None)
        assert rels == []

    def test_malformed_item_skipped(self):
        env = ["not-a-dict", None, {"name": "DB_URL", "value": "redis://cache:6379"}]
        rels = self._extractor().extract(env)
        assert len(rels) == 1
        assert rels[0]["protocol"] == "Redis"

    def test_grpc_address_detected(self):
        env = [{"name": "GRPC_SERVER_ADDR", "value": "grpc://ml-service:50051"}]
        rels = self._extractor().extract(env)
        assert len(rels) == 1
        assert rels[0]["protocol"] == "gRPC"

    def test_sqlserver_connection_string(self):
        env = [{"name": "MSSQL_CONNECTION", "value": "Server=tcp:sql-host,1433;Database=Sales;"}]
        rels = self._extractor().extract(env)
        assert len(rels) == 1
        assert rels[0]["protocol"] == "SQLServer"
        assert rels[0]["to"] == "sql-host"


# ---------------------------------------------------------------------------
# EnvVarRelationshipExtractor — compose dict form
# ---------------------------------------------------------------------------

class TestEnvVarRelationshipExtractorDict:
    def _extractor(self):
        return EnvVarRelationshipExtractor("cart-service")

    def test_basic_url_from_dict(self):
        env = {"REDIS_URL": "redis://session-store:6379"}
        rels = self._extractor().extract_from_dict(env)
        assert len(rels) == 1
        assert rels[0]["to"] == "session-store"

    def test_consumer_direction_from_dict(self):
        env = {"CONSUMER_BOOTSTRAP_SERVERS": "kafka://kafka:9092"}
        rels = self._extractor().extract_from_dict(env)
        assert len(rels) == 1
        assert rels[0]["type"] == "subscribes-to"

    def test_empty_dict(self):
        rels = self._extractor().extract_from_dict({})
        assert rels == []

    def test_none_dict(self):
        rels = self._extractor().extract_from_dict(None)
        assert rels == []


# ---------------------------------------------------------------------------
# ConfigRelationshipExtractor — file parsing
# ---------------------------------------------------------------------------

class TestConfigRelationshipExtractorAppsettings:
    def test_appsettings_json(self, tmp_path):
        config = {
            "ConnectionStrings": {
                "DefaultConnection": "Server=tcp:mssql-host,1433;Database=App;"
            }
        }
        (tmp_path / "appsettings.json").write_text(json.dumps(config))
        rels = ConfigRelationshipExtractor("api-service").extract_from_directory(tmp_path)
        assert any(r["protocol"] == "SQLServer" for r in rels)

    def test_appsettings_env_specific(self, tmp_path):
        config = {"Redis": {"Connection": "redis://redis-prod:6379"}}
        (tmp_path / "appsettings.Production.json").write_text(json.dumps(config))
        rels = ConfigRelationshipExtractor("worker").extract_from_directory(tmp_path)
        assert any(r["protocol"] == "Redis" for r in rels)


class TestConfigRelationshipExtractorSpringBoot:
    def test_application_properties(self, tmp_path):
        props = textwrap.dedent("""\
            spring.datasource.url=jdbc:postgresql://pg-host:5432/shop
            spring.redis.host=redis-host
        """)
        (tmp_path / "application.properties").write_text(props)
        rels = ConfigRelationshipExtractor("shop-service").extract_from_directory(tmp_path)
        assert any(r["protocol"] == "PostgreSQL" for r in rels)

    def test_application_yml(self, tmp_path):
        data = {"spring": {"datasource": {"url": "jdbc:mysql://mysql-host:3306/catalog"}}}
        (tmp_path / "application.yml").write_text(yaml.dump(data))
        rels = ConfigRelationshipExtractor("catalog-service").extract_from_directory(tmp_path)
        assert any(r["protocol"] == "MySQL" for r in rels)

    def test_application_profile_yml(self, tmp_path):
        data = {"kafka": {"bootstrap": {"servers": "kafka://kafka-broker:9092"}}}
        (tmp_path / "application-prod.yml").write_text(yaml.dump(data))
        rels = ConfigRelationshipExtractor("event-service").extract_from_directory(tmp_path)
        assert any(r["protocol"] == "Kafka" for r in rels)


class TestConfigRelationshipExtractorDotEnv:
    def test_dotenv_file(self, tmp_path):
        dotenv = textwrap.dedent("""\
            DATABASE_URL=postgresql://db:5432/mydb
            REDIS_URL=redis://cache:6379
            SECRET_KEY=supersecret
        """)
        (tmp_path / ".env").write_text(dotenv)
        rels = ConfigRelationshipExtractor("app").extract_from_directory(tmp_path)
        protocols = {r["protocol"] for r in rels}
        assert "PostgreSQL" in protocols
        assert "Redis" in protocols

    def test_dotenv_quoted_values(self, tmp_path):
        dotenv = 'AMQP_URL="amqp://rabbit:5672/"\n'
        (tmp_path / ".env").write_text(dotenv)
        rels = ConfigRelationshipExtractor("worker").extract_from_directory(tmp_path)
        assert any(r["protocol"] == "AMQP" for r in rels)

    def test_dotenv_single_quoted_values(self, tmp_path):
        dotenv = "MONGO_URL='mongodb://mongo:27017/data'\n"
        (tmp_path / ".env").write_text(dotenv)
        rels = ConfigRelationshipExtractor("svc").extract_from_directory(tmp_path)
        assert any(r["protocol"] == "MongoDB" for r in rels)

    def test_dotenv_comments_skipped(self, tmp_path):
        dotenv = "# comment line\nDB_URL=postgresql://db:5432/app\n"
        (tmp_path / ".env").write_text(dotenv)
        rels = ConfigRelationshipExtractor("svc").extract_from_directory(tmp_path)
        assert len(rels) == 1

    def test_empty_directory(self, tmp_path):
        rels = ConfigRelationshipExtractor("svc").extract_from_directory(tmp_path)
        assert rels == []

    def test_noise_values_filtered(self, tmp_path):
        dotenv = "HOME=/root\nPATH=/usr/bin\n"
        (tmp_path / ".env").write_text(dotenv)
        rels = ConfigRelationshipExtractor("svc").extract_from_directory(tmp_path)
        assert rels == []
