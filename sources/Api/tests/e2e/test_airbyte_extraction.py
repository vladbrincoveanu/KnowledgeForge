# sources/Api/tests/e2e/test_airbyte_extraction.py
"""Integration test for Airbyte monorepo C4 extraction."""

import time
from pathlib import Path

import requests

BASE_URL = "http://localhost:8000"
DEMO_AIRBYTE_PATH = "/app/sources/demo/airbyte"


class TestAirbyteExtraction:
    """Run C4 extraction against the Airbyte monorepo and validate results."""

    def test_airbyte_fixture_exists(self):
        """Smoke check: fixture is present."""
        assert Path(DEMO_AIRBYTE_PATH).exists(), f"Airbyte fixture missing at {DEMO_AIRBYTE_PATH}"

    def test_airbyte_scans_and_produces_architecture(self):
        """Full extraction: scan Airbyte and verify meaningful output."""
        start = time.monotonic()
        scan_payload = {
            "repo_path": DEMO_AIRBYTE_PATH,
            "use_c4_model": True,
            "max_components_per_domain": 10,
        }
        resp = requests.post(f"{BASE_URL}/api/v1/code/scan", json=scan_payload)
        assert resp.status_code == 200, f"Scan failed: {resp.text}"
        task_id = resp.json()["task_id"]

        max_wait = 120
        deadline = time.monotonic() + max_wait
        status = "pending"
        while status not in ("completed", "failed") and time.monotonic() < deadline:
            time.sleep(2)
            status_resp = requests.get(f"{BASE_URL}/api/v1/code/scan/{task_id}")
            assert status_resp.status_code == 200
            status_data = status_resp.json()
            status = status_data.get("status", "pending")

        assert status == "completed", f"Extraction did not complete within {max_wait}s"

        elapsed = time.monotonic() - start
        print(f"\nAirbyte extraction completed in {elapsed:.1f}s")

        containers = int(status_data.get("containers_count", 0))
        components = int(status_data.get("components_count", 0))
        deps = int(status_data.get("external_deps_count", 0))

        assert containers >= 2, f"Expected >= 2 containers, got {containers}"
        assert components >= 3, f"Expected >= 3 components, got {components}"
        assert deps >= 1, f"Expected >= 1 external dependency, got {deps}"

        results_resp = requests.get(f"{BASE_URL}/api/v1/code/scan/{task_id}/results")
        assert results_resp.status_code == 200
        results = results_resp.json()

        containers_list = results.get("containers", [])
        tech_containers = [
            c for c in containers_list
            if c.get("technology") and c.get("technology") != "Unknown"
        ]
        assert len(tech_containers) >= 1, (
            f"Expected >= 1 container with detected technology, got {len(tech_containers)}"
        )

        deps_list = results.get("system_context", {}).get("external_dependencies", [])
        assert len(deps_list) >= 1, (
            f"Expected >= 1 mapped external dependency, got {len(deps_list)}"
        )

        components_list = results.get("components", [])
        named_components = [c for c in components_list if c.get("name")]
        assert len(named_components) >= 3, (
            f"Expected >= 3 named components, got {len(named_components)}"
        )

        print(f"Airbyte extraction: {containers} containers, {components} components, {deps} deps")
