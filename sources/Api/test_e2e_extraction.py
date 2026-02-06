"""
End-to-End Comprehensive Test for GitHub Repository Extraction
Tests the entire flow: GitHub URL -> Extraction -> JSON -> UI Display
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from app.services.service_extraction.github_downloader import GitHubDownloader
from app.services.c4.context.context_manager import ContextManager
from app.services.c4.containers.structure_detector import StructureDetector


# Test configuration
GITHUB_URL = "https://github.com/venkataravuri/e-commerce-microservices-sample.git"
EXPECTED_SYSTEM_NAME = "Sample E-Commerce application using Microservices / Cloud Native Architecture (CNA)"


class TestE2EExtraction:
    """End-to-end tests for the complete extraction pipeline."""
    
    @pytest.fixture(scope="class")
    def extracted_data(self):
        """Extract repository and return the C4 architecture data."""
        temp_dir = Path(tempfile.mkdtemp(prefix="e2e_test_"))
        
        try:
            print(f"\n📥 Cloning: {GITHUB_URL}")
            repo_path = GitHubDownloader.download_repository(
                GITHUB_URL,
                output_dir=temp_dir,
                use_git=True,
                full_history=True,
            )
            print(f"✅ Cloned to: {repo_path}")
            
            # Extract C4 architecture
            print("\n🔍 Extracting C4 architecture...")
            context_manager = ContextManager(repo_path)
            system_context = context_manager.extract_context()
            
            structure_detector = StructureDetector(repo_path)
            containers = structure_detector.detect()
            
            c4_architecture = {
                "c4_model_version": "1.0",
                "system_context": system_context,
                "containers": containers,
                "relationships": {},
            }
            
            print(f"✅ Extracted {len(containers)} containers")
            
            return c4_architecture
            
        finally:
            # Cleanup
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_01_system_context_basic_fields(self, extracted_data):
        """Test that system context has all basic required fields."""
        system_context = extracted_data["system_context"]
        
        assert system_context.get("name") == EXPECTED_SYSTEM_NAME
        assert system_context.get("purpose")
        assert system_context.get("description")
        assert system_context.get("type") == "system"
        assert system_context.get("repository_url") == "https://github.com/venkataravuri/e-commerce-microservices-sample"
        
        print(f"✅ System name: {system_context['name']}")
    
    def test_02_system_context_it_landscape_fields(self, extracted_data):
        """Test that system context has all 7 key IT landscape fields."""
        system_context = extracted_data["system_context"]

        required_fields = [
            "domain",           # Business area
            "owner",            # Squad/team
            "status",           # Lifecycle stage
            "tier",             # Criticality
            "data_class",       # Data sensitivity
            "active_experts",   # Bus factor
            "compliance",       # Architectural risk
        ]

        for field in required_fields:
            assert field in system_context, f"System context must have '{field}'"
            assert system_context[field] not in [None, "", "Unknown", "unknown", "Unassigned"], (
                f"{field} must not be default/empty, got: {system_context[field]}"
            )
            print(f"✅ {field}: {system_context[field]}")

        assert system_context["domain"] == "Infrastructure"
        assert system_context["status"] == "Deprecated / Frozen"
        assert system_context["tier"] == "Tier 3 - Development/Internal"
        assert system_context["data_class"] == "General"
        assert isinstance(system_context["active_experts"], int)

        # === NEW: 7-Check Compliance Validation ===
        compliance = system_context.get('compliance')
        compliance_factors = system_context.get('compliance_factors', [])
        compliance_confidence = system_context.get('compliance_confidence')

        # Assert compliance is not default/unknown
        assert compliance is not None, "compliance field must be present"
        assert compliance != "UNKNOWN", "compliance should be determined for real repos"
        assert compliance in ["EXCELLENT", "COMPLIANT", "AT_RISK", "NON_COMPLIANT"], \
            f"Invalid compliance value: {compliance}"

        # Assert compliance factors are populated with checks
        assert len(compliance_factors) > 0, "compliance_factors should contain check results"

        # Assert first factor is the score summary
        assert compliance_factors[0].startswith("Score:"), \
            f"First factor should be score summary, got: {compliance_factors[0]}"

        # Validate score format: "Score: X/7 checks passed"
        score_line = compliance_factors[0]
        import re
        match = re.search(r'Score: (\d+)/7', score_line)
        assert match, f"Invalid score format: {score_line}"
        score = int(match.group(1))
        assert 0 <= score <= 7, f"Score must be 0-7, got {score}"

        # Assert factors contain check results (✅ or ❌)
        check_factors = [f for f in compliance_factors[1:] if f.startswith(('✅', '❌', '🚨'))]
        assert len(check_factors) == 7, \
            f"Should have exactly 7 check results, got {len(check_factors)}: {check_factors}"

        # Validate specific checks are present (at least as pass or fail)
        expected_checks = [
            "README", "tests", "CI/CD", "Security", "secrets", "structure", "Dependency"
        ]
        factors_text = ' '.join(compliance_factors).lower()
        for check in expected_checks:
            assert check.lower() in factors_text, \
                f"Check '{check}' not found in compliance factors: {compliance_factors}"

        # Assert confidence is 1.0 (deterministic)
        assert compliance_confidence == 1.0, \
            f"Compliance confidence should be 1.0 for deterministic checks, got {compliance_confidence}"

        # Validate compliance level matches score
        if score == 7:
            assert compliance == "EXCELLENT", f"7/7 should be EXCELLENT, got {compliance}"
        elif score >= 5:
            assert compliance in ["COMPLIANT", "EXCELLENT"], \
                f"5-6/7 should be COMPLIANT or EXCELLENT, got {compliance}"
        elif score >= 3:
            assert compliance in ["AT_RISK", "COMPLIANT"], \
                f"3-4/7 should be AT_RISK, got {compliance}"
        else:
            assert compliance == "NON_COMPLIANT", \
                f"0-2/7 should be NON_COMPLIANT, got {compliance}"

        # Check for critical security override
        critical_security = any('🚨' in f and 'CRITICAL' in f for f in compliance_factors)
        if critical_security:
            assert compliance == "NON_COMPLIANT", \
                "Critical security issue should force NON_COMPLIANT status"

        print(f"\n✅ Compliance validation passed:")
        print(f"   Status: {compliance} ({score}/7)")
        print(f"   Confidence: {compliance_confidence}")
        print(f"   Factors ({len(compliance_factors)}):")
        for factor in compliance_factors[:5]:  # Print first 5
            print(f"     {factor}")

    def test_02b_compliance_edge_cases(self, extracted_data):
        """Test compliance rubric handles edge cases correctly."""

        # Test that real e-commerce repo has non-default compliance
        system_context = extracted_data["system_context"]
        compliance = system_context.get('compliance')
        compliance_factors = system_context.get('compliance_factors', [])

        # Should detect at least some checks
        passed_checks = [f for f in compliance_factors if f.startswith('✅')]
        failed_checks = [f for f in compliance_factors if f.startswith(('❌', '🚨'))]

        assert len(passed_checks) > 0, "Real repo should pass at least some checks"

        # Validate no empty/placeholder factors
        for factor in compliance_factors:
            assert len(factor.strip()) > 0, "No empty compliance factors allowed"
            assert factor not in ["UNKNOWN", "N/A", "TODO"], \
                f"Placeholder factor detected: {factor}"

        print(f"\n✅ Edge case validation passed:")
        print(f"   Passed: {len(passed_checks)} checks")
        print(f"   Failed: {len(failed_checks)} checks")

    def test_03_owner_detection(self, extracted_data):
        """Test that owner is properly detected from Git history."""
        system_context = extracted_data["system_context"]
        
        owner = system_context["owner"]
        
        # Owner should NOT be "Unassigned" if git history is available
        assert owner != "Unassigned", "Owner should be detected from git history with full clone"
        
        # Should have owner contributors
        assert "owner_contributors" in system_context
        contributors = system_context.get("owner_contributors", [])
        
        if contributors:
            assert len(contributors) > 0, "Should have at least one contributor"
            print(f"✅ Owner: {owner}")
            print(f"✅ Contributors: {contributors[:3]}")
        else:
            print(f"⚠️  Owner detected: {owner}, but no contributors list")
    
    def test_04_containers_detection(self, extracted_data):
        """Test that containers are properly detected."""
        containers = extracted_data["containers"]
        
        assert len(containers) >= 5
        container_names = {c.get("name") for c in containers}
        expected = {
            "products-cna-microservice",
            "search-cna-microservice",
            "store-ui",
            "users-cna-microservice",
            "cart-cna-microservice",
        }
        assert expected.issubset(container_names)
        
        print(f"\n✅ Detected {len(containers)} containers")

    def test_05_container_fields(self, extracted_data):
        """Test that containers have all required fields."""
        containers = extracted_data["containers"]
        
        required_fields = [
            "name",
            "type",
            "technology",
            "description",
        ]
        
        for container in containers:
            for field in required_fields:
                assert field in container, f"Container '{container.get('name', '?')}' must have '{field}'"
    
    def test_06_container_endpoints(self, extracted_data):
        """Test that containers have endpoint information when available."""
        containers = extracted_data["containers"]
        
        containers_with_endpoints = [c for c in containers if c.get("endpoint")]
        
        print(f"\n✅ Containers with endpoints: {len(containers_with_endpoints)}/{len(containers)}")
        for container in containers_with_endpoints:
            print(f"  - {container['name']}: {container['endpoint']}")
    
    def test_07_json_serializable(self, extracted_data):
        """Test that the extracted data is JSON serializable."""
        try:
            json_str = json.dumps(extracted_data, indent=2)
            assert len(json_str) > 0
            print(f"✅ JSON size: {len(json_str)} bytes")
            
            # Test deserialization
            reloaded = json.loads(json_str)
            assert reloaded["c4_model_version"] == extracted_data["c4_model_version"]
            print("✅ JSON is properly serializable and deserializable")
            
        except Exception as e:
            pytest.fail(f"JSON serialization failed: {e}")
    
    def test_08_relationships_structure(self, extracted_data):
        """Test that relationships are properly structured."""
        relationships = extracted_data.get("relationships", {})
        
        # Should have relationship types
        assert isinstance(relationships, dict), "Relationships should be a dictionary"
        print(f"✅ Relationships structure: {list(relationships.keys())}")
    
    def test_09_git_metadata(self, extracted_data):
        """Test that git metadata is extracted."""
        system_context = extracted_data["system_context"]
        
        if "git" in system_context:
            git = system_context["git"]
            assert "branch" in git or "commit" in git or "remote_url" in git
            print(f"✅ Git metadata present: {list(git.keys())}")
        else:
            print("⚠️  No git metadata found")
    
    def test_10_repository_url(self, extracted_data):
        """Test that repository URL is captured."""
        system_context = extracted_data["system_context"]
        
        assert "repository_url" in system_context, "System context should have repository_url"
        
        repo_url = system_context["repository_url"]
        if repo_url:
            assert "github.com" in repo_url.lower() or "gitlab" in repo_url.lower() or "git" in repo_url
            print(f"✅ Repository URL: {repo_url}")
        else:
            print("⚠️  Repository URL is empty")


def test_ui_data_display():
    """Test that UI can properly display the extracted data.
    
    This is a simulation test that checks the UI would receive proper data structure.
    """
    # Simulate UI data transformation
    sample_system_context = {
        "name": "Test System",
        "domain": "Infrastructure",
        "owner": "Test Team",
        "owner_contributors": ["user1@example.com", "user2@example.com"],
        "status": "Active-Dev",
        "tier": "Tier 2 - Standard",
        "data_class": "PII",
        "active_experts": 3,
        "compliance": "COMPLIANT",
        "purpose": "Test system purpose",
    }
    
    # Test that all fields are displayable
    assert sample_system_context["domain"] is not None
    assert sample_system_context["owner"] != "Unassigned"
    assert len(sample_system_context["owner_contributors"]) > 0
    assert sample_system_context["status"] in ["Active-Dev", "Maintenance-Only", "Deprecated / Frozen"]
    assert "Tier" in sample_system_context["tier"]
    assert sample_system_context["data_class"] in ["PII", "Credit-Card", "Legal/Security", "General"]
    assert sample_system_context["active_experts"] >= 0
    assert sample_system_context["compliance"] in ["EXCELLENT", "COMPLIANT", "AT_RISK", "NON_COMPLIANT"]
    
    print("✅ UI data structure validation passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
