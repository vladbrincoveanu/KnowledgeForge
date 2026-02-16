"""LLM-powered dependency classification for C4 architecture levels.

Classifies external dependencies as:
- BUSINESS_SYSTEM: Should appear at System Context level (external business services)
- TECHNICAL_INFRA: Should appear at Container level (databases, caches, infrastructure)
- UNKNOWN: Cannot determine with confidence

Supports both OpenAI and local LLM (LM Studio).
"""

import logging
import os
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DependencyType(str, Enum):
    """Classification types for external dependencies."""
    
    BUSINESS_SYSTEM = "BUSINESS_SYSTEM"
    TECHNICAL_INFRA = "TECHNICAL_INFRA"
    UNKNOWN = "UNKNOWN"


class DependencyClassification(BaseModel):
    """Result of dependency classification."""
    
    type: DependencyType = Field(
        description="Classification type: BUSINESS_SYSTEM, TECHNICAL_INFRA, or UNKNOWN"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score from 0.0 to 1.0"
    )
    reasoning: str = Field(
        description="Brief explanation of the classification decision"
    )


class DependencyClassifier:
    """Classifies external dependencies for C4 architecture modeling."""
    
    # Classification prompt template
    CLASSIFICATION_PROMPT = """You are analyzing external dependencies in a software system for C4 architecture modeling.

Dependency: {dependency_name}
Type: {dependency_type}
Detected From: {detected_from}
Context: {context}

Classify this dependency according to C4 System Context level rules:

**BUSINESS_SYSTEM** - Should appear at System Context level if:
- External SaaS service with business logic/workflows
- Handles business domain operations (payments, CRM, communications, analytics)
- Provides business capability as a service
- Involves third-party business relationships
- Customer-facing or business-critical external service

Examples:
✅ Stripe (payment processing - core business function)
✅ Auth0 / Okta (user identity - business-critical SaaS)
✅ Twilio (customer communication - business capability)
✅ Salesforce (CRM - business system)
✅ SendGrid (email delivery to customers - business function)
✅ Mixpanel / Google Analytics (business insights)
✅ Slack API (business communication integration)

**TECHNICAL_INFRA** - Should NOT appear at Context level (goes to Container level) if:
- Database or cache (PostgreSQL, Redis, MongoDB, MySQL)
- Message queue (Kafka, RabbitMQ, ActiveMQ)
- Cloud storage (AWS S3, Azure Blob Storage, Google Cloud Storage)
- Infrastructure/deployment tool (Docker, Kubernetes)
- Self-hosted technical component
- Pure data storage without business logic
- Performance/scalability infrastructure

Examples:
❌ PostgreSQL (technical storage, no business logic)
❌ Redis (performance cache, infrastructure concern)
❌ RabbitMQ (message transport, technical detail)
❌ Docker (deployment infrastructure)
❌ AWS S3 (cloud storage - unless named "Customer Document Storage Service")
❌ Elasticsearch (search infrastructure - unless business search product)
❌ Datadog / Sentry (monitoring/observability - technical operations)

**Decision Rules:**
1. If it's a database, cache, or message queue → TECHNICAL_INFRA
2. If it's self-hosted infrastructure → TECHNICAL_INFRA
3. If it's external SaaS with business logic → BUSINESS_SYSTEM
4. If it handles customer interactions → BUSINESS_SYSTEM
5. If uncertain → UNKNOWN (set confidence < 0.7)

Return ONLY valid JSON:
{{"type": "BUSINESS_SYSTEM", "confidence": 0.95, "reasoning": "Brief explanation"}}"""
    
    def __init__(self, llm_manager: Optional[Any] = None):
        """Initialize dependency classifier with LLM manager.
        
        Args:
            llm_manager: Optional LLMManager instance. If None, uses fallback rules only.
        """
        self.llm_manager = llm_manager
        
        if not self.llm_manager:
            logger.info("Dependency classifier initialized with fallback rules only (no LLM)")
        else:
            logger.info("Dependency classifier initialized with LLM support")
    
    def classify_dependency(
        self,
        name: str,
        dep_type: str = "unknown",
        detected_from: str = "",
        context: str = ""
    ) -> DependencyClassification:
        """Classify a dependency as BUSINESS_SYSTEM or TECHNICAL_INFRA.
        
        Args:
            name: Dependency name (e.g., "PostgreSQL", "Stripe")
            dep_type: Type hint from detector (e.g., "database", "payment", "authentication")
            detected_from: Where dependency was found (e.g., "package.json", "docker-compose.yml")
            context: Additional context (import statements, README mentions, etc.)
        
        Returns:
            DependencyClassification with type, confidence, and reasoning
        """
        # Try LLM classification first
        if self.llm_manager:
            try:
                return self._classify_with_llm(name, dep_type, detected_from, context)
            except Exception as e:
                logger.warning(f"LLM classification failed for {name}: {e}, falling back to rules")
        
        # Fallback to rule-based classification
        return self._classify_with_rules(name, dep_type)
    
    def _classify_with_llm(
        self,
        name: str,
        dep_type: str,
        detected_from: str,
        context: str
    ) -> DependencyClassification:
        """Classify using LLM (OpenAI or local LM Studio)."""
        import json as json_module
        
        prompt_text = self.CLASSIFICATION_PROMPT.format(
            dependency_name=name,
            dependency_type=dep_type,
            detected_from=detected_from,
            context=context or "No additional context"
        )
        
        # Use LLMManager's generate_text method
        response = self.llm_manager.generate_text(
            prompt=prompt_text,
            max_tokens=150,
            temperature=0.0
        )
        
        if not response:
            raise Exception("LLM returned empty response")
        
        result_text = response.strip()
        
        # Remove markdown code blocks if present
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()
        
        # Extract JSON from response (sometimes LLM adds extra text)
        json_match = result_text
        if "{" in result_text and "}" in result_text:
            start = result_text.find("{")
            end = result_text.rfind("}") + 1
            json_match = result_text[start:end]
        
        result_json = json_module.loads(json_match)
        
        classification = DependencyClassification(
            type=DependencyType(result_json["type"]),
            confidence=result_json["confidence"],
            reasoning=result_json["reasoning"]
        )
        
        logger.info(
            f"Classified '{name}' as {classification.type.value} "
            f"(confidence: {classification.confidence:.2f}) - {classification.reasoning}"
        )
        
        return classification
    
    def _classify_with_rules(self, name: str, dep_type: str) -> DependencyClassification:
        """Fallback rule-based classification when LLM unavailable."""
        name_lower = name.lower()
        type_lower = dep_type.lower()
        
        # Technical infrastructure patterns
        technical_patterns = [
            "postgres", "mysql", "mariadb", "mongodb", "redis", "memcached",
            "kafka", "rabbitmq", "activemq", "nats",
            "elasticsearch", "opensearch", "solr",
            "docker", "kubernetes", "k8s",
            "s3", "blob", "storage",
            "datadog", "sentry", "prometheus", "grafana",
            "nginx", "apache", "traefik",
        ]
        
        technical_types = [
            "database", "cache", "messaging", "search", 
            "storage", "monitoring", "error-tracking"
        ]
        
        # Business system patterns
        business_patterns = [
            "stripe", "paypal", "braintree",
            "auth0", "okta", "cognito",
            "twilio", "sendgrid", "mailgun", "mailchimp",
            "salesforce", "hubspot",
            "slack", "teams", "discord",
            "mixpanel", "amplitude", "segment",
            "google analytics", "analytics",
        ]
        
        business_types = [
            "payment", "authentication", "auth", "sms", "email",
            "crm", "analytics", "notifications", "communication"
        ]
        
        # Check for technical infrastructure
        for pattern in technical_patterns:
            if pattern in name_lower:
                return DependencyClassification(
                    type=DependencyType.TECHNICAL_INFRA,
                    confidence=0.9,
                    reasoning=f"'{name}' is technical infrastructure (matched pattern: {pattern})"
                )
        
        if type_lower in technical_types:
            return DependencyClassification(
                type=DependencyType.TECHNICAL_INFRA,
                confidence=0.85,
                reasoning=f"Type '{dep_type}' indicates technical infrastructure"
            )
        
        # Check for business systems
        for pattern in business_patterns:
            if pattern in name_lower:
                return DependencyClassification(
                    type=DependencyType.BUSINESS_SYSTEM,
                    confidence=0.9,
                    reasoning=f"'{name}' is an external business service (matched pattern: {pattern})"
                )
        
        if type_lower in business_types:
            return DependencyClassification(
                type=DependencyType.BUSINESS_SYSTEM,
                confidence=0.85,
                reasoning=f"Type '{dep_type}' indicates business system"
            )
        
        # Unknown - cannot determine
        return DependencyClassification(
            type=DependencyType.UNKNOWN,
            confidence=0.5,
            reasoning=f"Could not determine classification for '{name}' with type '{dep_type}'"
        )
    
    def classify_batch(
        self,
        dependencies: list[dict[str, Any]]
    ) -> list[tuple[dict[str, Any], DependencyClassification]]:
        """Classify multiple dependencies.
        
        Args:
            dependencies: List of dependency dicts with 'name', 'type', etc.
        
        Returns:
            List of (dependency, classification) tuples
        """
        results = []
        
        for dep in dependencies:
            classification = self.classify_dependency(
                name=dep.get("name", ""),
                dep_type=dep.get("type", ""),
                detected_from=dep.get("detected_from", ""),
                context=dep.get("context", "")
            )
            results.append((dep, classification))
        
        return results
