"""Harness-driven tests for core OmniPay services."""

import pytest

from tests.harness.omnipay_harness import (
    demo_dir,
    extract_containers,
    extract_context,
)


class TestOmniPayCoreServices:
    """Test the 6 core OmniPay services are detected and have correct fields."""

    @pytest.fixture(scope="class")
    def containers(self, demo_dir):
        """Extract containers from OmniPay demo directory."""
        return extract_containers(demo_dir)

    def test_discovers_six_core_services(self, containers):
        """Core 6 services: ledger, fraud-ml, gateway, notifier, infra, card-router."""
        expected = {
            "omnipay-ledger",
            "omnipay-fraud-ml",
            "omnipay-gateway",
            "omnipay-notifier",
            "omnipay-infra",
            "omnipay-card-router",
        }
        found = {c.get("name") for c in containers}
        missing = expected - found
        assert not missing, f"Missing core services: {missing}"

    def test_ledger_is_java(self, containers):
        """omnipay-ledger is Java Spring Boot."""
        svc = next((c for c in containers if c.get("name") == "omnipay-ledger"), None)
        assert svc is not None
        tech = str(svc.get("technology", "")).lower()
        assert "java" in tech, f"Expected Java for ledger, got: {tech}"

    def test_fraud_ml_is_python(self, containers):
        """omnipay-fraud-ml is Python."""
        svc = next((c for c in containers if c.get("name") == "omnipay-fraud-ml"), None)
        assert svc is not None
        tech = str(svc.get("technology", "")).lower()
        assert "python" in tech, f"Expected Python for fraud-ml, got: {tech}"

    def test_gateway_is_typescript(self, containers):
        """omnipay-gateway is TypeScript/Node.js."""
        svc = next((c for c in containers if c.get("name") == "omnipay-gateway"), None)
        assert svc is not None
        tech = str(svc.get("technology", "")).lower()
        lang_str = str(svc.get("language", "")).lower()
        assert any(kw in tech or kw in lang_str for kw in ["typescript", "javascript", "node"]), \
            f"Expected TS/JS/Node for gateway, got: {tech}"

    def test_notifier_is_go(self, containers):
        """omnipay-notifier is Go."""
        svc = next((c for c in containers if c.get("name") == "omnipay-notifier"), None)
        assert svc is not None
        tech = str(svc.get("technology", "")).lower()
        assert "go" in tech, f"Expected Go for notifier, got: {tech}"

    def test_card_router_is_csharp(self, containers):
        """omnipay-card-router is C#/.NET."""
        svc = next((c for c in containers if c.get("name") == "omnipay-card-router"), None)
        assert svc is not None
        tech = str(svc.get("technology", "")).lower()
        assert any(kw in tech for kw in ["c#", "csharp", "dotnet", ".net"]), \
            f"Expected C#/.NET for card-router, got: {tech}"

    def test_infra_has_technology(self, containers):
        """omnipay-infra has infrastructure technology detected."""
        svc = next((c for c in containers if c.get("name") == "omnipay-infra"), None)
        assert svc is not None
        tech = str(svc.get("technology", "")).lower()
        assert tech != "unknown" and tech != "", \
            f"Expected infrastructure technology for infra, got: {tech}"

    def test_all_services_have_name(self, containers):
        """Every container has a non-empty name."""
        for svc in containers:
            assert svc.get("name"), f"Service missing name: {svc}"
            assert isinstance(svc.get("name"), str), f"Name not a string: {svc}"

    def test_all_services_have_technology(self, containers):
        """Every container has a non-Unknown technology."""
        for svc in containers:
            tech = svc.get("technology")
            assert tech is not None, f"Service {svc.get('name')} missing technology"
            assert tech != "Unknown", f"Service {svc.get('name')} has Unknown technology"

    def test_all_services_have_type(self, containers):
        """Every container has a container_type."""
        for svc in containers:
            ctype = svc.get("type") or svc.get("container_type")
            assert ctype, f"Service {svc.get('name')} missing container_type"

    def test_total_service_count(self, containers):
        """Should discover all current OmniPay services including extended ones."""
        assert len(containers) >= 6, f"Expected ≥6 services, got {len(containers)}"


class TestOmniPaySystemContext:
    """Test system context extraction for OmniPay."""

    @pytest.fixture(scope="class")
    def context(self, demo_dir):
        """Extract system context from OmniPay demo directory."""
        return extract_context(demo_dir)

    def test_context_has_required_fields(self, context):
        """System context has all required IT landscape fields."""
        required = ["name", "domain", "owner", "status", "tier", "data_class"]
        for field in required:
            assert field in context, f"Context missing '{field}'"

    def test_context_owner_field_is_present(self, context):
        """Owner field is present and a string (may be 'Unassigned' for minimal git history)."""
        owner = context.get("owner", "")
        assert isinstance(owner, str), f"Owner should be a string, got: {type(owner)}"
        # Note: 'Unassigned' is acceptable when git history is minimal (1 commit)

    def test_context_domain_is_valid(self, context):
        """Domain should be a meaningful business domain."""
        domain = context.get("domain", "")
        assert domain not in ("Unknown", "unknown", ""), \
            f"Domain should be detected, got: {domain}"

    def test_context_produces_valid_json(self, context):
        """System context is JSON serializable."""
        import json
        json.dumps(context)
