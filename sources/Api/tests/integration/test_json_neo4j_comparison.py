"""Integration test: verify Neo4j contents match the extracted JSON."""
import json
import pytest
from pathlib import Path

from app.infrastructure.graph.neo4j_client import Neo4jClient
from app.services.c4.graph_writer import GraphWriter


def load_extraction_result():
    result_path = Path(__file__).parent.parent.parent / "UI" / "e2e" / ".extraction-result.json"
    if not result_path.exists():
        pytest.skip(".extraction-result.json not found — run Playwright setup first")
    with open(result_path) as f:
        return json.load(f)


class TestJsonNeo4jComparison:
    @pytest.fixture(autouse=True)
    def setup_neo4j(self):
        client = Neo4jClient.from_config()
        yield client
        client.close()

    def test_container_count_matches(self, setup_neo4j):
        data = load_extraction_result()
        containers = [c for c in data.get("containers", []) if not c.get("is_infrastructure_only")]
        expected_count = len(containers)
        result = setup_neo4j.query("MATCH (n:Container) RETURN count(n) as count", {})
        actual_count = result[0]["count"]
        assert actual_count == expected_count, f"Neo4j {actual_count} vs JSON {expected_count}"

    def test_external_system_count_matches(self, setup_neo4j):
        data = load_extraction_result()
        ext_deps = data.get("system_context", {}).get("external_dependencies", []) or []
        expected_count = len(ext_deps)
        result = setup_neo4j.query("MATCH (n:ExternalSystem) RETURN count(n) as count", {})
        actual_count = result[0]["count"]
        assert actual_count == expected_count, f"Neo4j {actual_count} vs JSON {expected_count}"

    def test_system_count_is_one(self, setup_neo4j):
        data = load_extraction_result()
        sys_name = data.get("system_context", {}).get("name", "System")
        result = setup_neo4j.query("MATCH (n:System {id: $id}) RETURN count(n) as count", {"id": f"context:{sys_name}"})
        assert result[0]["count"] == 1, f"Expected 1 System node, got {result[0]['count']}"
        all_systems = setup_neo4j.query("MATCH (n:System) RETURN count(n) as count", {})
        assert all_systems[0]["count"] == 1, f"Expected exactly 1 System node in total, got {all_systems[0]['count']}"

    def test_component_count_matches(self, setup_neo4j):
        data = load_extraction_result()
        components = data.get("components") or []
        expected_count = len(components)
        result = setup_neo4j.query("MATCH (n:Component) RETURN count(n) as count", {})
        actual_count = result[0]["count"]
        assert actual_count == expected_count, f"Neo4j {actual_count} vs JSON {expected_count}"

    def test_evidence_nodes_created(self, setup_neo4j):
        data = load_extraction_result()
        ext_deps = data.get("system_context", {}).get("external_dependencies") or []
        expected_evidence = sum(len(dep.get("evidence") or []) for dep in ext_deps)
        result = setup_neo4j.query("MATCH (n:Evidence) RETURN count(n) as count", {})
        actual = result[0]["count"]
        assert actual == expected_evidence

    def test_provided_relationships_match_evidence(self, setup_neo4j):
        data = load_extraction_result()
        ext_deps = data.get("system_context", {}).get("external_dependencies") or []
        expected_evidence = sum(len(dep.get("evidence") or []) for dep in ext_deps)
        result = setup_neo4j.query("MATCH ()-[r:PROVIDED]->() RETURN count(r) as count", {})
        actual = result[0]["count"]
        assert actual == expected_evidence

    def test_container_relationships_match_json(self, setup_neo4j):
        data = load_extraction_result()
        json_rels = data.get("relationships", {}).get("containers") or []
        result = setup_neo4j.query("MATCH ()-[r:USES]->() RETURN r.id as rel_id", {})
        neo4j_ids = {r["rel_id"] for r in result}
        expected_ids = {
            f"container:{rel.get('source') or rel.get('from')}->container:{rel.get('destination') or rel.get('to')}"
            for rel in json_rels
            if (rel.get("source") or rel.get("from")) and (rel.get("destination") or rel.get("to"))
        }
        missing = expected_ids - neo4j_ids
        extra = neo4j_ids - expected_ids
        assert not missing, f"Missing in Neo4j: {missing}"
        assert not extra, f"Extra in Neo4j: {extra}"
