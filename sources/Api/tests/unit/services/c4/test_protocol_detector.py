"""Tests for source-code protocol fingerprinting."""
from pathlib import Path

from app.services.c4.containers.protocol_detector import ProtocolDetector


class TestProtocolDetector:
    def test_detects_kafka_producer_import(self, tmp_path):
        (tmp_path / "service.py").write_text("from kafka import KafkaProducer\nproducer = KafkaProducer()")
        result = ProtocolDetector(tmp_path).detect_protocols()
        assert any(m.protocol == "Kafka" for m in result)

    def test_detects_psycopg2_as_jdbc(self, tmp_path):
        (tmp_path / "db.py").write_text("import psycopg2\nconn = psycopg2.connect(DSN)")
        result = ProtocolDetector(tmp_path).detect_protocols()
        assert any(m.protocol == "JDBC" for m in result)

    def test_detects_requests_as_rest(self, tmp_path):
        (tmp_path / "client.py").write_text("import requests\nrequests.get('https://api.example.com')")
        result = ProtocolDetector(tmp_path).detect_protocols()
        assert any(m.protocol == "REST/HTTPS" for m in result)

    def test_detects_grpc_import(self, tmp_path):
        (tmp_path / "grpc_client.py").write_text("import grpc\nchannel = grpc.insecure_channel('localhost:50051')")
        result = ProtocolDetector(tmp_path).detect_protocols()
        assert any(m.protocol == "gRPC" for m in result)

    def test_returns_empty_for_empty_repo(self, tmp_path):
        result = ProtocolDetector(tmp_path).detect_protocols()
        assert result == []

    def test_relationship_hint_postgres_returns_jdbc(self, tmp_path):
        protocol = ProtocolDetector(tmp_path).detect_for_relationship("backend", "postgres")
        assert protocol == "JDBC"

    def test_relationship_hint_kafka_returns_kafka(self, tmp_path):
        protocol = ProtocolDetector(tmp_path).detect_for_relationship("backend", "kafka-broker")
        assert protocol == "Kafka"

    def test_skips_node_modules(self, tmp_path):
        nm = tmp_path / "node_modules" / "kafka-node"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("const KafkaProducer = require('kafka-node');")
        result = ProtocolDetector(tmp_path).detect_protocols()
        assert result == []