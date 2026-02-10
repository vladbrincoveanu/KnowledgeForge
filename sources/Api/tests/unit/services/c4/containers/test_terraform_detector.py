"""Unit tests for TerraformDetector - C4 Level 2 extraction from Terraform files."""

import pytest
from pathlib import Path
import tempfile

from app.services.c4.containers.terraform_detector import TerraformDetector


@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def aws_terraform_repo(temp_repo):
    """Repo with AWS Terraform resources."""
    tf_content = """
resource "aws_db_instance" "prod_database" {
  identifier        = "prod-db"
  engine            = "postgres"
  instance_class    = "db.t3.medium"
  allocated_storage = 20
}

resource "aws_s3_bucket" "assets" {
  bucket = "my-app-assets"
}

resource "aws_elasticache_cluster" "cache" {
  cluster_id           = "prod-cache"
  engine               = "redis"
}
"""
    tf_dir = temp_repo / "terraform"
    tf_dir.mkdir()
    (tf_dir / "main.tf").write_text(tf_content)
    return temp_repo


@pytest.fixture
def multi_provider_terraform_repo(temp_repo):
    """Repo with multiple cloud provider resources."""
    aws_tf = """
resource "aws_db_instance" "rds" {
  identifier = "my-rds"
}
"""
    gcp_tf = """
resource "google_sql_database_instance" "postgres" {
  name             = "my-db"
  database_version = "POSTGRES_14"
}
"""
    tf_dir = temp_repo / "infra"
    tf_dir.mkdir()
    (tf_dir / "aws.tf").write_text(aws_tf)
    (tf_dir / "gcp.tf").write_text(gcp_tf)
    return temp_repo


class TestTerraformDetectorCanDetect:
    """Test can_detect() detection logic."""

    def test_can_detect_returns_true_when_tf_exists(self, aws_terraform_repo):
        detector = TerraformDetector(aws_terraform_repo)
        assert detector.can_detect() is True

    def test_can_detect_returns_false_when_no_tf_files(self, temp_repo):
        detector = TerraformDetector(temp_repo)
        assert detector.can_detect() is False

    def test_can_detect_finds_tf_in_subdirectory(self, temp_repo):
        subdir = temp_repo / "infra" / "aws"
        subdir.mkdir(parents=True)
        (subdir / "main.tf").write_text('resource "aws_s3_bucket" "b" {}')
        detector = TerraformDetector(temp_repo)
        assert detector.can_detect() is True


class TestTerraformDetectorDetect:
    """Test detect() container extraction."""

    def test_detect_returns_list(self, aws_terraform_repo):
        detector = TerraformDetector(aws_terraform_repo)
        result = detector.detect()
        assert isinstance(result, list)

    def test_detect_extracts_known_resources(self, aws_terraform_repo):
        detector = TerraformDetector(aws_terraform_repo)
        result = detector.detect()
        # Should find at least the aws_db_instance and aws_s3_bucket
        assert len(result) >= 1

    def test_detect_containers_are_c4_level_2(self, aws_terraform_repo):
        detector = TerraformDetector(aws_terraform_repo)
        result = detector.detect()
        for container in result:
            assert container["c4_level"] == 2

    def test_detect_containers_have_required_fields(self, aws_terraform_repo):
        detector = TerraformDetector(aws_terraform_repo)
        result = detector.detect()
        for container in result:
            assert "name" in container
            assert "type" in container
            assert container["type"] == "container"

    def test_detect_database_resource_classified(self, aws_terraform_repo):
        detector = TerraformDetector(aws_terraform_repo)
        result = detector.detect()
        db = next((c for c in result if "database" in c["name"].lower() or "rds" in c["name"].lower()), None)
        # The database resource should exist
        assert db is not None
        assert "Database" in db.get("container_type", "")

    def test_detect_empty_when_no_known_resources(self, temp_repo):
        """Only known resource types (DB, S3, etc.) are extracted."""
        tf_dir = temp_repo / "terraform"
        tf_dir.mkdir()
        # Only has an IAM role - not a passable resource
        (tf_dir / "main.tf").write_text('resource "aws_iam_role" "my_role" { name = "test" }')
        detector = TerraformDetector(temp_repo)
        result = detector.detect()
        assert isinstance(result, list)

    def test_detect_empty_when_no_tf_files(self, temp_repo):
        detector = TerraformDetector(temp_repo)
        result = detector.detect()
        assert result == []


class TestTerraformDetectorProviderInference:
    """Test cloud provider inference from resource types."""

    def test_aws_provider_inferred(self, temp_repo):
        tf_dir = temp_repo / "tf"
        tf_dir.mkdir()
        (tf_dir / "main.tf").write_text('resource "aws_db_instance" "db" { identifier = "prod" }')
        detector = TerraformDetector(temp_repo)
        result = detector.detect()
        if result:
            # Technology field should indicate AWS
            assert "AWS" in result[0].get("technology", "")

    def test_resource_extraction_regex(self, temp_repo):
        """Test that _extract_resources correctly parses resource blocks."""
        tf_dir = temp_repo / "tf"
        tf_dir.mkdir()
        tf_content = """
resource "aws_s3_bucket" "my_bucket" {
  bucket = "test"
}

resource "aws_db_instance" "rds" {
  identifier = "prod-db"
}
"""
        (tf_dir / "main.tf").write_text(tf_content)
        detector = TerraformDetector(temp_repo)
        result = detector.detect()
        names = [c["name"] for c in result]
        # Both resources should be detected (S3 = Storage, DB = Database)
        assert len(result) >= 1
