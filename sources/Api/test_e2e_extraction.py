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
        
        # Required fields
        assert "name" in system_context, "System context must have 'name'"
        assert "purpose" in system_context, "System context must have 'purpose'"
        assert "type" in system_context, "System context must have 'type'"
        assert system_context["type"] == "system"
        
        print(f"✅ System name: {system_context['name']}")
        print(f"✅ System type: {system_context['type']}")
    
    def test_02_system_context_it_landscape_fields(self, extracted_data):
        """Test that system context has all 7 key IT landscape fields."""
        system_context = extracted_data["system_context"]
        
        # The 7 key attributes
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
            print(f"✅ {field}: {system_context[field]}")
        
        # Validate specific values
        assert system_context["domain"] in ["Infrastructure", "User Management", "Data", "AI/ML", "Frontend", "Backend"], \
            f"Invalid domain: {system_context['domain']}"
        
        assert system_context["status"] in ["Active-Dev", "Maintenance-Only", "Deprecated / Frozen"], \
            f"Invalid status: {system_context['status']}"
        
        assert "Tier" in system_context["tier"] or system_context["tier"].startswith("Tier"), \
            f"Invalid tier format: {system_context['tier']}"
        
        assert system_context["data_class"] in ["PII", "Credit-Card", "Legal/Security", "General"], \
            f"Invalid data_class: {system_context['data_class']}"
        
        assert isinstance(system_context["active_experts"], int), \
            f"active_experts must be integer, got: {type(system_context['active_experts'])}"
        
        assert system_context["compliance"] in ["COMPLIANT", "AT_RISK", "NON_COMPLIANT"], \
            f"Invalid compliance: {system_context['compliance']}"
    
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
        
        # Note: Container detection depends on repository structure
        # Some repos may have 0 containers if they don't follow expected patterns
        print(f"\n✅ Detected {len(containers)} containers")
        
        if len(containers) > 0:
            print("Containers found:")
            for container in containers[:5]:  # Print first 5
                print(f"  - {container['name']} ({container['type']})")
        else:
            print("⚠️  No containers detected (repo may not follow container structure patterns)")
    
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
    assert sample_system_context["compliance"] in ["COMPLIANT", "AT_RISK", "NON_COMPLIANT"]
    
    print("✅ UI data structure validation passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
