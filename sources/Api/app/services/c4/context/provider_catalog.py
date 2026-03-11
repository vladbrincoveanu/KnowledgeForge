"""Provider catalog matching utilities for deterministic dependency resolution."""

from dataclasses import dataclass
from urllib.parse import urlparse

from .provider_catalog_data import RAW_PROVIDER_CATALOG


@dataclass(frozen=True, slots=True)
class ProviderCatalogEntry:
    """Normalized provider metadata and its detection aliases."""

    provider: str
    company: str
    category: str
    default_boundary: str
    package_aliases: tuple[str, ...] = ()
    env_aliases: tuple[str, ...] = ()
    url_aliases: tuple[str, ...] = ()
    image_aliases: tuple[str, ...] = ()
    scheme_aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProviderMatchResult:
    """Explainable provider catalog match result."""

    entry: ProviderCatalogEntry
    alias_field: str
    matched_alias: str
    input_value: str
    normalized_value: str
    match_strategy: str

    def to_metadata(self) -> dict[str, str]:
        """Return compact metadata for downstream decision payloads."""
        return {
            "provider": self.entry.provider,
            "company": self.entry.company,
            "category": self.entry.category,
            "alias_field": self.alias_field,
            "matched_alias": self.matched_alias,
            "input_value": self.input_value,
            "normalized_value": self.normalized_value,
            "match_strategy": self.match_strategy,
        }


ALIAS_FIELDS = (
    "package_aliases",
    "env_aliases",
    "url_aliases",
    "image_aliases",
    "scheme_aliases",
)
VALID_BOUNDARIES = {"BUSINESS_SYSTEM", "TECHNICAL_INFRA", "UNKNOWN"}


def _build_catalog() -> tuple[ProviderCatalogEntry, ...]:
    """Materialize raw provider definitions into typed catalog entries."""
    catalog = tuple(ProviderCatalogEntry(**entry) for entry in RAW_PROVIDER_CATALOG)
    errors = validate_provider_catalog(catalog)
    if errors:
        formatted_errors = "\n".join(f"- {error}" for error in errors)
        raise ValueError(f"Invalid provider catalog:\n{formatted_errors}")
    return catalog

def _normalize(value: str) -> str:
    return value.strip().lower()


def _matches(alias: str, value: str) -> bool:
    normalized_alias = _normalize(alias)
    normalized_value = _normalize(value)
    return normalized_alias in normalized_value or normalized_value == normalized_alias


def _exact_match(alias: str, value: str) -> bool:
    return _normalize(alias) == _normalize(value)


def _select_best_match(
    value: str,
    *,
    alias_getter: str,
    matcher,
    transform=None,
) -> ProviderMatchResult | None:
    """Return the strongest catalog match for a signal."""
    transformed_value = transform(value) if transform else value
    normalized_value = _normalize(transformed_value)
    best_result: ProviderMatchResult | None = None
    best_score = -1

    for entry in PROVIDER_CATALOG:
        for alias in getattr(entry, alias_getter):
            if matcher(alias, transformed_value):
                score = len(_normalize(alias))
                if score > best_score:
                    best_result = ProviderMatchResult(
                        entry=entry,
                        alias_field=alias_getter,
                        matched_alias=alias,
                        input_value=value,
                        normalized_value=normalized_value,
                        match_strategy="exact" if matcher is _exact_match else "contains",
                    )
                    best_score = score

    return best_result


def _host_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc or parsed.path
    return host.lower()


def _scheme_from_url(url: str) -> str:
    return urlparse(url).scheme.lower()


def validate_provider_catalog(
    catalog: tuple[ProviderCatalogEntry, ...] | None = None,
) -> list[str]:
    """Validate provider uniqueness and alias ownership across the catalog."""
    entries = catalog or PROVIDER_CATALOG
    errors: list[str] = []
    provider_names: set[str] = set()
    alias_owners: dict[str, dict[str, str]] = {
        field: {} for field in ALIAS_FIELDS
    }

    for entry in entries:
        provider_name = entry.provider.strip()
        if not provider_name:
            errors.append("Provider entry is missing a provider name")
            continue
        normalized_provider = _normalize(provider_name)
        if normalized_provider in provider_names:
            errors.append(f"Duplicate provider entry '{entry.provider}'")
        provider_names.add(normalized_provider)

        if not entry.company.strip():
            errors.append(f"Provider '{entry.provider}' is missing a company name")
        if not entry.category.strip():
            errors.append(f"Provider '{entry.provider}' is missing a category")
        if entry.default_boundary not in VALID_BOUNDARIES:
            errors.append(
                f"Provider '{entry.provider}' has invalid boundary '{entry.default_boundary}'"
            )

        total_aliases = 0
        for field in ALIAS_FIELDS:
            seen_local: set[str] = set()
            for alias in getattr(entry, field):
                total_aliases += 1
                normalized_alias = _normalize(alias)
                if not normalized_alias:
                    errors.append(f"Provider '{entry.provider}' has an empty alias in {field}")
                    continue
                if normalized_alias in seen_local:
                    errors.append(
                        f"Provider '{entry.provider}' repeats alias '{alias}' in {field}"
                    )
                    continue
                seen_local.add(normalized_alias)

                owner = alias_owners[field].get(normalized_alias)
                if owner and owner != entry.provider:
                    errors.append(
                        f"Alias '{alias}' in {field} is owned by both '{owner}' and '{entry.provider}'"
                    )
                    continue
                alias_owners[field][normalized_alias] = entry.provider

        if total_aliases == 0:
            errors.append(f"Provider '{entry.provider}' has no aliases")

    return errors


PROVIDER_CATALOG: tuple[ProviderCatalogEntry, ...] = _build_catalog()


def match_provider_from_package(package_name: str) -> ProviderCatalogEntry | None:
    """Resolve a provider from a package name or library reference."""
    result = _select_best_match(
        package_name,
        alias_getter="package_aliases",
        matcher=_matches,
    )
    return result.entry if result else None


def match_provider_from_env_var(env_var_name: str) -> ProviderCatalogEntry | None:
    """Resolve a provider from an environment variable name."""
    result = _select_best_match(
        env_var_name,
        alias_getter="env_aliases",
        matcher=_exact_match,
    )
    return result.entry if result else None


def match_provider_from_url(url: str) -> ProviderCatalogEntry | None:
    """Resolve a provider from a URL or domain."""
    scheme_result = _select_best_match(
        url,
        alias_getter="scheme_aliases",
        matcher=_exact_match,
        transform=_scheme_from_url,
    )
    host_result = _select_best_match(
        url,
        alias_getter="url_aliases",
        matcher=lambda alias, host: alias in host,
        transform=_host_from_url,
    )
    result = host_result or scheme_result
    return result.entry if result else None


def match_provider_from_image(image_name: str) -> ProviderCatalogEntry | None:
    """Resolve a provider from a Docker image name."""
    result = _select_best_match(
        image_name,
        alias_getter="image_aliases",
        matcher=_matches,
    )
    return result.entry if result else None


def explain_provider_match_from_package(package_name: str) -> ProviderMatchResult | None:
    """Explain package-based provider matching."""
    return _select_best_match(
        package_name,
        alias_getter="package_aliases",
        matcher=_matches,
    )


def explain_provider_match_from_env_var(env_var_name: str) -> ProviderMatchResult | None:
    """Explain environment-variable-based provider matching."""
    return _select_best_match(
        env_var_name,
        alias_getter="env_aliases",
        matcher=_exact_match,
    )


def explain_provider_match_from_url(url: str) -> ProviderMatchResult | None:
    """Explain URL-based provider matching."""
    host_result = _select_best_match(
        url,
        alias_getter="url_aliases",
        matcher=lambda alias, host: alias in host,
        transform=_host_from_url,
    )
    if host_result:
        return host_result
    return _select_best_match(
        url,
        alias_getter="scheme_aliases",
        matcher=_exact_match,
        transform=_scheme_from_url,
    )


def explain_provider_match_from_image(image_name: str) -> ProviderMatchResult | None:
    """Explain Docker-image-based provider matching."""
    return _select_best_match(
        image_name,
        alias_getter="image_aliases",
        matcher=_matches,
    )


def count_provider_entries() -> int:
    """Return the number of distinct provider entries."""
    return len(PROVIDER_CATALOG)


def count_provider_mappings() -> int:
    """Return the total number of deterministic alias mappings in the catalog."""
    total = 0
    for entry in PROVIDER_CATALOG:
        for field in ALIAS_FIELDS:
            total += len(getattr(entry, field))
    return total
