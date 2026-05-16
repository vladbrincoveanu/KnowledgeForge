"""Test that owned TECHNICAL_INFRA deps are reclassified as Container."""
from pathlib import Path

from app.services.c4.context.dependency_classifier import DependencyClassifier, DependencyType


class TestOwnershipPromotion:
    def test_s3_with_terraform_resource_becomes_owned_container(self, tmp_path):
        tf = tmp_path / "infra.tf"
        tf.write_text('resource "aws_s3_bucket" "statements" {\n  bucket = "my-statements"\n}')

        classifier = DependencyClassifier(repo_path=tmp_path)
        result = classifier.classify_dependency(name="S3", dep_type="storage")

        assert result.type == DependencyType.OWNED_CONTAINER

    def test_external_stripe_stays_business_system(self, tmp_path):
        classifier = DependencyClassifier(repo_path=tmp_path)
        result = classifier.classify_dependency(name="Stripe", dep_type="payment")

        assert result.type == DependencyType.BUSINESS_SYSTEM

    def test_postgres_with_migrations_becomes_owned_container(self, tmp_path):
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        (migrations / "0001_initial.sql").write_text("CREATE TABLE orders (id SERIAL);")

        classifier = DependencyClassifier(repo_path=tmp_path)
        result = classifier.classify_dependency(name="PostgreSQL", dep_type="database")

        assert result.type == DependencyType.OWNED_CONTAINER
        assert result.confidence >= 0.85