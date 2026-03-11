"""Unit tests for the deterministic provider catalog."""

from app.services.c4.context.provider_catalog import (
    ProviderCatalogEntry,
    count_provider_entries,
    count_provider_mappings,
    explain_provider_match_from_env_var,
    explain_provider_match_from_url,
    match_provider_from_env_var,
    match_provider_from_package,
    match_provider_from_url,
    validate_provider_catalog,
)


class TestProviderCatalogCoverage:
    """Catalog should maintain broad deterministic coverage."""

    def test_has_at_least_50_provider_entries(self):
        assert count_provider_entries() >= 50

    def test_has_at_least_250_total_mappings(self):
        assert count_provider_mappings() >= 250

    def test_current_catalog_has_no_validation_errors(self):
        assert validate_provider_catalog() == []


class TestProviderCatalogMatching:
    """Representative package, env, and URL matches should resolve deterministically."""

    def test_matches_openai_from_package(self):
        entry = match_provider_from_package("openai")
        assert entry is not None
        assert entry.provider == "OpenAI"

    def test_matches_clerk_from_package(self):
        entry = match_provider_from_package("@clerk/nextjs")
        assert entry is not None
        assert entry.provider == "Clerk"

    def test_matches_supabase_from_env_var(self):
        entry = match_provider_from_env_var("SUPABASE_SERVICE_ROLE_KEY")
        assert entry is not None
        assert entry.provider == "Supabase"

    def test_matches_github_from_env_var(self):
        entry = match_provider_from_env_var("GITHUB_TOKEN")
        assert entry is not None
        assert entry.provider == "GitHub"

    def test_env_var_matching_is_exact(self):
        entry = match_provider_from_env_var("MY_GITHUB_TOKEN_BACKUP")
        assert entry is None

    def test_matches_snowflake_from_url(self):
        entry = match_provider_from_url("https://acme.snowflakecomputing.com")
        assert entry is not None
        assert entry.provider == "Snowflake"

    def test_matches_vercel_from_url(self):
        entry = match_provider_from_url("https://my-app.vercel.app")
        assert entry is not None
        assert entry.provider == "Vercel"

    def test_package_matching_prefers_longest_alias(self):
        entry = match_provider_from_package("@google-cloud/storage")
        assert entry is not None
        assert entry.provider == "Google Cloud"

    def test_explains_env_var_match(self):
        match = explain_provider_match_from_env_var("SUPABASE_SERVICE_ROLE_KEY")
        assert match is not None
        assert match.entry.provider == "Supabase"
        assert match.alias_field == "env_aliases"
        assert match.matched_alias == "SUPABASE_SERVICE_ROLE_KEY"
        assert match.match_strategy == "exact"

    def test_explains_url_match(self):
        match = explain_provider_match_from_url("https://api.stripe.com/v1/charges")
        assert match is not None
        assert match.entry.provider == "Stripe"
        assert match.alias_field == "url_aliases"
        assert match.matched_alias == "api.stripe.com"

    def test_explains_scheme_based_url_match(self):
        match = explain_provider_match_from_url("postgresql://user:pass@db.internal:5432/app")
        assert match is not None
        assert match.entry.provider == "PostgreSQL"
        assert match.alias_field == "scheme_aliases"
        assert match.matched_alias == "postgresql"


class TestProviderCatalogValidation:
    """Validation should catch broken deterministic ownership rules."""

    def test_detects_duplicate_package_alias_across_providers(self):
        broken_catalog = (
            ProviderCatalogEntry(
                provider="Provider A",
                company="Company A",
                category="ai",
                default_boundary="BUSINESS_SYSTEM",
                package_aliases=("shared-sdk",),
            ),
            ProviderCatalogEntry(
                provider="Provider B",
                company="Company B",
                category="ai",
                default_boundary="BUSINESS_SYSTEM",
                package_aliases=("shared-sdk",),
            ),
        )

        errors = validate_provider_catalog(broken_catalog)
        assert any("shared-sdk" in error for error in errors)

    def test_detects_duplicate_provider_name(self):
        broken_catalog = (
            ProviderCatalogEntry(
                provider="Provider A",
                company="Company A",
                category="ai",
                default_boundary="BUSINESS_SYSTEM",
                package_aliases=("sdk-a",),
            ),
            ProviderCatalogEntry(
                provider="Provider A",
                company="Company B",
                category="ai",
                default_boundary="BUSINESS_SYSTEM",
                package_aliases=("sdk-b",),
            ),
        )

        errors = validate_provider_catalog(broken_catalog)
        assert any("Duplicate provider entry" in error for error in errors)
