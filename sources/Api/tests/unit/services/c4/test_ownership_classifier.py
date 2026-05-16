"""Tests for OwnershipSignalDetector."""
from pathlib import Path

import pytest

from app.services.c4.context.ownership_classifier import OwnershipSignalDetector


class TestOwnershipSignalDetector:
    def test_detects_migration_files_as_owned(self, tmp_path):
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        (migrations / "0001_initial.sql").write_text("CREATE TABLE users (id SERIAL);")

        detector = OwnershipSignalDetector(tmp_path)
        is_owned, confidence, reason = detector.is_owned("PostgreSQL", "database")

        assert is_owned is True
        assert confidence >= 0.85
        assert "migration" in reason.lower()

    def test_detects_terraform_s3_bucket_as_owned(self, tmp_path):
        tf = tmp_path / "main.tf"
        tf.write_text('resource "aws_s3_bucket" "statements" {\n  bucket = "my-statements"\n}')

        detector = OwnershipSignalDetector(tmp_path)
        is_owned, confidence, reason = detector.is_owned("S3", "storage")

        assert is_owned is True
        assert confidence >= 0.9
        assert "terraform" in reason.lower()

    def test_returns_not_owned_when_no_signals(self, tmp_path):
        detector = OwnershipSignalDetector(tmp_path)
        is_owned, confidence, reason = detector.is_owned("Stripe", "payment")

        assert is_owned is False
        assert confidence <= 0.6

    def test_detects_alembic_as_migration(self, tmp_path):
        alembic = tmp_path / "alembic" / "versions"
        alembic.mkdir(parents=True)
        (alembic / "abc123_create_orders.py").write_text("def upgrade(): pass")

        detector = OwnershipSignalDetector(tmp_path)
        is_owned, confidence, reason = detector.is_owned("PostgreSQL", "database")

        assert is_owned is True

    def test_detects_dockerfile_reference_as_owned(self, tmp_path):
        (tmp_path / "Dockerfile").write_text(
            "FROM postgres:15\nCOPY init.sql /docker-entrypoint-initdb.d/"
        )

        detector = OwnershipSignalDetector(tmp_path)
        is_owned, confidence, reason = detector.is_owned("postgres", "database")

        assert is_owned is True
        assert confidence >= 0.75