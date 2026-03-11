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
