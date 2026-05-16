"""Integration smoke test: verify C4 element type labels flow through all three levels."""
from pathlib import Path

from app.services.c4.context.context_manager import ContextManager
from app.services.c4.containers.container_manager import ContainerManager
from app.services.c4.components.models import ComponentObject, ComponentType


class TestC4ElementTypePipeline:
    def test_context_actor_carries_person_label(self, tmp_path):
        manager = ContextManager(tmp_path)
        actors = [{"name": "Admin", "description": "manages system"}]
        enriched = manager._enrich_actors_with_element_type(actors)
        assert enriched[0]["c4_element_type"] == "Person"

    def test_context_business_dep_carries_software_system_label(self, tmp_path):
        manager = ContextManager(tmp_path)
        deps = [{"name": "Stripe", "dependency_type": "BUSINESS_SYSTEM"}]
        enriched = manager._enrich_deps_with_element_type(deps)
        assert enriched[0]["c4_element_type"] == "SoftwareSystem"

    def test_container_carries_container_label(self, tmp_path):
        manager = ContainerManager(tmp_path)
        manager.containers["backend"] = {"name": "backend", "technology": "FastAPI"}
        enriched = manager._enrich_containers_with_c4_metadata(manager.containers)
        assert enriched["backend"]["c4_element_type"] == "Container"

    def test_container_relationship_has_technology(self, tmp_path):
        manager = ContainerManager(tmp_path)
        rels = [{"from": "backend", "to": "postgres-db", "type": "reads", "protocol": "PostgreSQL"}]
        enriched = manager._enrich_relationships_with_protocol(rels)
        assert "technology" in enriched[0]
        assert enriched[0]["technology"]  # non-empty

    def test_component_carries_component_label(self):
        comp = ComponentObject(
            component_id="order-service",
            name="OrderService",
            component_type=ComponentType.SERVICE,
            description="Manages orders",
            confidence=0.9,
        )
        assert comp.c4_element_type == "Component"