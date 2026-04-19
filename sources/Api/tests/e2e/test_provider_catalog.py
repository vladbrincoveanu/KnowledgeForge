"""Tests for provider catalog dictionary matching."""

import pytest


class TestProviderCatalogMatching:
    """Test package name and env var matching against provider catalog."""

    def test_provider_catalog_importable(self):
        """Provider catalog should be importable."""
        try:
            from app.services.c4.context.provider_catalog import (
                PROVIDER_CATALOG,
                match_provider_from_package,
                match_provider_from_env_var,
            )
        except ImportError as e:
            pytest.skip(f"Provider catalog not available: {e}")
        assert len(PROVIDER_CATALOG) > 0

    def test_stripe_package_match(self):
        """stripe package matches Stripe."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("stripe")
        assert result is not None, "Should match Stripe from stripe package"
        assert result.provider == "Stripe"

    def test_mixpanel_package_match(self):
        """mixpanel package matches Mixpanel."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("mixpanel")
        assert result is not None
        assert result.provider == "Mixpanel"

    def test_auth0_package_match(self):
        """@auth0/auth0-spa-js matches Auth0."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("@auth0/auth0-spa-js")
        assert result is not None
        assert result.provider == "Auth0"

    def test_postgres_package_match(self):
        """psycopg2 matches PostgreSQL."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("psycopg2")
        assert result is not None
        assert result.provider == "PostgreSQL"

    def test_redis_package_match(self):
        """redis package matches Redis."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("redis")
        assert result is not None
        assert result.provider == "Redis"

    def test_mongodb_package_match(self):
        """MongoDB.Driver matches MongoDB."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("MongoDB.Driver")
        assert result is not None
        assert result.provider == "MongoDB"

    def test_kafka_package_match(self):
        """Confluent.Kafka matches Kafka."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("Confluent.Kafka")
        assert result is not None
        assert result.provider == "Kafka"

    def test_rabbitmq_package_match(self):
        """RabbitMQ.Client matches RabbitMQ."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("RabbitMQ.Client")
        assert result is not None
        assert result.provider == "RabbitMQ"

    def test_sqlserver_package_match(self):
        """Microsoft.Data.SqlClient matches SQL Server."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("Microsoft.Data.SqlClient")
        assert result is not None
        assert result.provider == "SQL Server"

    def test_stripe_env_var_match(self):
        """STRIPE_API_KEY matches Stripe."""
        from app.services.c4.context.provider_catalog import match_provider_from_env_var
        result = match_provider_from_env_var("STRIPE_API_KEY")
        assert result is not None
        assert result.provider == "Stripe"

    def test_postgres_env_var_match(self):
        """POSTGRES_HOST matches PostgreSQL."""
        from app.services.c4.context.provider_catalog import match_provider_from_env_var
        result = match_provider_from_env_var("POSTGRES_HOST")
        assert result is not None
        assert result.provider == "PostgreSQL"

    def test_kafka_env_var_match(self):
        """KAFKA_BOOTSTRAP_SERVERS matches Kafka."""
        from app.services.c4.context.provider_catalog import match_provider_from_env_var
        result = match_provider_from_env_var("KAFKA_BOOTSTRAP_SERVERS")
        assert result is not None
        assert result.provider == "Kafka"

    def test_mongodb_env_var_match(self):
        """MONGODB_URI matches MongoDB."""
        from app.services.c4.context.provider_catalog import match_provider_from_env_var
        result = match_provider_from_env_var("MONGODB_URI")
        assert result is not None
        assert result.provider == "MongoDB"
