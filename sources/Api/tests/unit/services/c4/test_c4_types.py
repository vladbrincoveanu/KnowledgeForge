"""Tests for C4ContainerType classifier."""
from app.services.c4.containers.c4_types import C4ContainerType, classify_c4_container_type


class TestC4ContainerType:
    def test_has_canonical_types(self):
        assert C4ContainerType.DATABASE == "Database"
        assert C4ContainerType.SERVER_SIDE_WEB_APP == "ServerSideWebApp"
        assert C4ContainerType.BLOB_STORE == "BlobStore"
        assert C4ContainerType.MESSAGE_BROKER == "MessageBroker"
        assert C4ContainerType.SERVERLESS_FUNCTION == "ServerlessFunction"

    def test_classifies_postgres_as_database(self):
        result = classify_c4_container_type({"technology": "PostgreSQL", "name": "db"})
        assert result == C4ContainerType.DATABASE

    def test_classifies_redis_as_database(self):
        result = classify_c4_container_type({"technology": "Redis", "name": "cache"})
        assert result == C4ContainerType.DATABASE

    def test_classifies_s3_as_blob_store(self):
        result = classify_c4_container_type({"technology": "AWS S3", "name": "statement-store"})
        assert result == C4ContainerType.BLOB_STORE

    def test_classifies_kafka_as_message_broker(self):
        result = classify_c4_container_type({"technology": "Kafka", "name": "events"})
        assert result == C4ContainerType.MESSAGE_BROKER

    def test_classifies_lambda_as_serverless(self):
        result = classify_c4_container_type({"technology": "AWS Lambda", "name": "processor"})
        assert result == C4ContainerType.SERVERLESS_FUNCTION

    def test_classifies_spring_boot_as_server_side_web_app(self):
        result = classify_c4_container_type({"technology": "Spring Boot", "name": "backend"})
        assert result == C4ContainerType.SERVER_SIDE_WEB_APP

    def test_classifies_react_spa_as_client_side_web_app(self):
        result = classify_c4_container_type({
            "technology": "React",
            "name": "frontend",
            "container_type": "frontend",
        })
        assert result == C4ContainerType.CLIENT_SIDE_WEB_APP

    def test_unknown_falls_back_to_unknown(self):
        result = classify_c4_container_type({"technology": "COBOL", "name": "legacy"})
        assert result == C4ContainerType.UNKNOWN