"""Unit tests for ContextManager context relationship generation."""

from app.services.c4.context.context_manager import ContextManager


class TestContextManagerRelationships:
    """Verify business descriptions for context-level relationships."""

    def test_actor_relationship_uses_actor_description(self, tmp_path):
        manager = ContextManager(tmp_path)

        relationships = manager.build_context_relationships(
            {
                "name": "KnowledgeForge",
                "actors": [
                    {
                        "name": "Analyst",
                        "description": "Reviews extracted architecture insights",
                    }
                ],
                "external_dependencies": [],
            }
        )

        assert relationships == [
            {
                "source": "Analyst",
                "destination": "KnowledgeForge",
                "description": "Reviews extracted architecture insights",
                "relationship_type": "uses",
            }
        ]

    def test_dependency_relationship_prefers_dependency_description(self, tmp_path):
        manager = ContextManager(tmp_path)

        relationships = manager.build_context_relationships(
            {
                "name": "KnowledgeForge",
                "actors": [],
                "external_dependencies": [
                    {
                        "name": "Stripe",
                        "description": "Processes subscription payments and billing events",
                        "dependency_type": "BUSINESS_SYSTEM",
                    }
                ],
            }
        )

        assert relationships == [
            {
                "source": "KnowledgeForge",
                "destination": "Stripe",
                "description": "Processes subscription payments and billing events",
                "relationship_type": "uses",
            }
        ]

    def test_dependency_relationship_uses_business_fallback_for_known_category(self, tmp_path):
        manager = ContextManager(tmp_path)

        relationships = manager.build_context_relationships(
            {
                "name": "KnowledgeForge",
                "actors": [],
                "external_dependencies": [
                    {
                        "name": "Stripe",
                        "category": "payment",
                        "dependency_type": "BUSINESS_SYSTEM",
                    }
                ],
            }
        )

        assert relationships == [
            {
                "source": "KnowledgeForge",
                "destination": "Stripe",
                "description": "Uses Stripe for payment processing",
                "relationship_type": "uses",
            }
        ]


class TestC4ElementTypeLabels:
    def test_actors_have_person_element_type(self, tmp_path):
        manager = ContextManager(tmp_path)
        ctx = {
            "name": "MySystem",
            "actors": [{"name": "Admin", "description": "manages the system"}],
            "external_dependencies": [],
        }
        rels = manager.build_context_relationships(ctx)
        # actor is the source of the relationship; check the raw context enrichment
        actor_types = manager._enrich_actors_with_element_type(ctx["actors"])
        assert all(a["c4_element_type"] == "Person" for a in actor_types)

    def test_business_system_deps_have_software_system_type(self, tmp_path):
        manager = ContextManager(tmp_path)
        deps = [{"name": "Stripe", "dependency_type": "BUSINESS_SYSTEM"}]
        enriched = manager._enrich_deps_with_element_type(deps)
        assert enriched[0]["c4_element_type"] == "SoftwareSystem"

    def test_owned_container_deps_have_container_type(self, tmp_path):
        manager = ContextManager(tmp_path)
        deps = [{"name": "PostgreSQL", "dependency_type": "OWNED_CONTAINER"}]
        enriched = manager._enrich_deps_with_element_type(deps)
        assert enriched[0]["c4_element_type"] == "Container"

    def test_technical_infra_deps_have_container_type(self, tmp_path):
        manager = ContextManager(tmp_path)
        deps = [{"name": "Redis", "dependency_type": "TECHNICAL_INFRA"}]
        enriched = manager._enrich_deps_with_element_type(deps)
        assert enriched[0]["c4_element_type"] == "Container"
