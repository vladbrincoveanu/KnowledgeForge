"""Business domain classification into a fixed taxonomy.

Replaces free-text keyword matching with a two-step approach:
  1. Fast keyword matching (no LLM cost, covers 80%+ of cases)
  2. Optional LLM classification for ambiguous cases

Fixed taxonomy (extensible via extra_domains parameter):
  Payments | Identity | Logistics | Commerce | Analytics |
  Infrastructure | Communication | Data | Security | Other

Usage:
    classifier = BusinessDomainClassifier(llm_manager=llm)
    domain = classifier.classify(service_name="payment-service", readme_text="...")
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Fixed taxonomy ────────────────────────────────────────────────────────────
BASE_TAXONOMY: list[str] = [
    "Payments",
    "Identity",
    "Logistics",
    "Commerce",
    "Analytics",
    "Infrastructure",
    "Communication",
    "Data",
    "Security",
    "Other",
]

# ── Keyword → domain mapping (case-insensitive substring match) ───────────────
_KEYWORD_MAP: dict[str, list[str]] = {
    "Payments": [
        "payment", "billing", "invoice", "checkout", "stripe", "paypal",
        "pci", "credit.card", "transaction", "refund", "subscription",
        "pricing", "discount", "coupon",
    ],
    "Identity": [
        "auth", "login", "oauth", "sso", "saml", "jwt", "token",
        "user", "account", "profile", "registration", "password",
        "permission", "rbac", "iam", "identity",
    ],
    "Logistics": [
        "shipping", "delivery", "fulfillment", "warehouse", "inventory",
        "tracking", "courier", "logistics", "dispatch", "supply.chain",
        "order.management",
    ],
    "Commerce": [
        "product", "catalog", "cart", "basket", "storefront", "shop",
        "ecommerce", "marketplace", "merchant", "listing", "pricing",
    ],
    "Analytics": [
        "analytics", "metrics", "reporting", "dashboard", "telemetry",
        "tracking", "events", "clickstream", "data.pipeline", "etl",
        "warehouse", "bi", "insights",
    ],
    "Infrastructure": [
        "infra", "platform", "gateway", "proxy", "load.balancer",
        "k8s", "kubernetes", "deploy", "ci.cd", "devops", "monitoring",
        "logging", "tracing", "alerting", "health", "cluster",
    ],
    "Communication": [
        "email", "notification", "sms", "push", "messaging", "chat",
        "webhook", "event", "pubsub", "broadcast", "alert",
        "slack", "twilio", "sendgrid",
    ],
    "Data": [
        "data", "database", "storage", "cache", "redis", "postgres",
        "mongo", "elasticsearch", "search", "indexing", "etl",
        "migration", "backup",
    ],
    "Security": [
        "security", "firewall", "waf", "rate.limit", "fraud",
        "compliance", "audit", "encryption", "vault", "secret",
        "scan", "vulnerability",
    ],
}


class BusinessDomainClassifier:
    """Classify a service into a fixed business domain taxonomy."""

    def __init__(
        self,
        llm_manager: Optional[Any] = None,
        extra_domains: Optional[list[str]] = None,
    ):
        self.llm_manager = llm_manager
        self.taxonomy = BASE_TAXONOMY + (extra_domains or [])

    # ─────────────────────────────────────────────────────────────────────────

    def classify(
        self,
        service_name: str = "",
        readme_text: str = "",
        existing_domain: Optional[str] = None,
    ) -> Optional[str]:
        """Return a domain from the fixed taxonomy, or None if truly unknown.

        Args:
            service_name:    The service name (used for keyword matching).
            readme_text:     README/description text for richer matching.
            existing_domain: If already set and within taxonomy, return as-is.
        """
        # If already a valid taxonomy entry, keep it
        if existing_domain and self._in_taxonomy(existing_domain):
            return existing_domain

        # Step 1: keyword matching (fast, no LLM)
        text = f"{service_name} {existing_domain or ''} {readme_text[:2000]}".lower()
        keyword_result = self._keyword_match(text)
        if keyword_result:
            return keyword_result

        # Step 2: LLM classification (only for ambiguous cases)
        if self.llm_manager and (service_name or readme_text):
            llm_result = self._llm_classify(service_name, readme_text)
            if llm_result:
                return llm_result

        return None

    # ─────────────────────────────────────────────────────────────────────────

    def _keyword_match(self, text: str) -> Optional[str]:
        scores: dict[str, int] = {}
        for domain, keywords in _KEYWORD_MAP.items():
            hits = sum(1 for kw in keywords if kw in text)
            if hits > 0:
                scores[domain] = hits
        if not scores:
            return None
        # Return domain with most keyword hits
        winner = max(scores, key=lambda d: scores[d])
        # Require at least 1 hit (already guaranteed by the hits > 0 check)
        return winner

    def _llm_classify(self, service_name: str, readme_text: str) -> Optional[str]:
        taxonomy_list = ", ".join(self.taxonomy)
        prompt = (
            f"Classify this software service into exactly one business domain.\n\n"
            f"Service name: {service_name}\n"
            f"Description: {readme_text[:800]}\n\n"
            f"Available domains: {taxonomy_list}\n\n"
            f"Reply with ONLY the domain name, nothing else."
        )
        try:
            response = self.llm_manager.generate_text(
                prompt, max_tokens=20, temperature=0.1, use_cache=True
            )
            if response:
                candidate = response.strip().strip(".,;\"'")
                if self._in_taxonomy(candidate):
                    return candidate
                # Fuzzy match: check if the response contains a taxonomy keyword
                for domain in self.taxonomy:
                    if domain.lower() in candidate.lower():
                        return domain
        except Exception as exc:
            logger.debug(f"LLM domain classification failed: {exc}")
        return None

    def _in_taxonomy(self, value: str) -> bool:
        return any(t.lower() == value.lower().strip() for t in self.taxonomy)


def classify_business_domain(
    service_name: str = "",
    readme_text: str = "",
    existing_domain: Optional[str] = None,
    llm_manager: Optional[Any] = None,
    extra_domains: Optional[list[str]] = None,
) -> Optional[str]:
    """Convenience wrapper."""
    return BusinessDomainClassifier(
        llm_manager=llm_manager,
        extra_domains=extra_domains,
    ).classify(service_name=service_name, readme_text=readme_text, existing_domain=existing_domain)
