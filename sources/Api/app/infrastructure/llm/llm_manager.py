"""LLM manager module for LM Studio integration."""

import hashlib
import json
import logging
import pickle
import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import requests
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@dataclass
class ResponseCache:
    """Response cache entry."""

    prompt_hash: str
    response: str
    timestamp: datetime
    model: str
    confidence: float


class EntityExtractionSchema(BaseModel):
    """Schema for entity extraction."""

    entities: list[dict[str, Any]]
    confidence: float
    extraction_method: str
    processing_time: float


class RelationshipExtractionSchema(BaseModel):
    """Schema for relationship extraction."""

    relationships: list[dict[str, Any]]
    confidence: float
    extraction_method: str
    processing_time: float


class SemanticTypeClassification(BaseModel):
    """Schema for semantic type classification."""

    semantic_type: str
    confidence: float
    reasoning: str
    alternative_types: list[str]


class OntologyMappingSchema(BaseModel):
    """Schema for ontology mapping."""

    mappings: list[dict[str, Any]]
    confidence: float
    ontology_type: str
    processing_time: float


class LLMManager:
    """Manages interactions with LM Studio LLM for semantic analysis."""

    def __init__(
        self,
        lmstudio_url: str = "http://localhost:1234",
        default_model: str = "deepseek/deepseek-r1-0528-qwen3-8b",
        use_embeddings: bool = True,
        cache_dir: Optional[str] = None,
        max_retries: int = 3,
        rate_limit_requests: int = 10,
        rate_limit_window: int = 60,
        openai_api_key: Optional[str] = None,
        openai_base_url: str = "https://api.openai.com/v1",
    ):
        """Initialize the LLM manager.

        Args:
            lmstudio_url: URL of the LM Studio service
            default_model: Default model to use
            use_embeddings: Whether to use sentence embeddings for similarity
            cache_dir: Directory for response caching
            max_retries: Maximum retry attempts
            rate_limit_requests: Maximum requests per time window
            rate_limit_window: Time window in seconds for rate limiting
            openai_api_key: OpenAI API key (if provided, uses OpenAI instead of LM Studio)
            openai_base_url: OpenAI API base URL
        """
        # Determine which LLM provider to use
        self.openai_api_key = openai_api_key
        self.use_openai = bool(openai_api_key)
        
        if self.use_openai:
            self.base_url = openai_base_url.rstrip("/")
            logger.info(f"LLM Manager initialized with OpenAI API (model: {default_model})")
        else:
            self.base_url = lmstudio_url.rstrip("/")
            logger.info(f"LLM Manager initialized with LM Studio (url: {lmstudio_url})")
        
        self.lmstudio_url = lmstudio_url.rstrip("/")  # Keep for compatibility
        self.default_model = default_model
        self.model_name = default_model  # Alias for compatibility
        self.use_embeddings = use_embeddings
        self.max_retries = max_retries
        self.timeout = 30  # Default timeout

        # Rate limiting
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_window = rate_limit_window
        self.request_timestamps = deque()
        self.rate_limit_lock = threading.Lock()

        # Connection pooling
        self.session = requests.Session()
        self.session.mount(
            "http://",
            requests.adapters.HTTPAdapter(
                pool_connections=10, pool_maxsize=20, max_retries=3
            ),
        )

        # Response caching
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.response_cache: dict[str, ResponseCache] = {}
        self.cache_ttl_hours = 24

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._load_cache()

        # Initialize sentence transformer for embeddings
        self.embedding_model = None
        if self.use_embeddings:
            try:
                self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("Sentence transformer model loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load sentence transformer: {e}")
                self.use_embeddings = False

        # Model fallback chain
        self.model_fallback_chain = [
            "llama2",
            "mistral",
            "phi3",
            "codellama",
            "llama2-7b",
        ]

        # Prompt templates
        self.prompt_templates = self._initialize_prompt_templates()

        # Test LM Studio connection
        self._test_connection()

    def _initialize_prompt_templates(self) -> dict[str, str]:
        """Initialize prompt templates with few-shot examples."""
        return {
            "entity_extraction": """
You are an expert at extracting entities from text data. Extract entities according to the following schema:

{entity_schema}

Few-shot examples:
Text: "Apple Inc. was founded by Steve Jobs in 1976 and is headquartered in Cupertino, California."
Entities: [
    {{"name": "Apple Inc.", "type": "organization", "confidence": 0.95}},
    {{"name": "Steve Jobs", "type": "person", "confidence": 0.90}},
    {{"name": "1976", "type": "temporal", "confidence": 0.85}},
    {{"name": "Cupertino, California", "type": "location", "confidence": 0.90}}
]

Text: "{text}"
Extract entities in JSON format:
""",
            "relationship_extraction": """
You are an expert at identifying relationships between entity pairs. Analyze the following entity pairs and identify relationships:

Entity 1: {entity1}
Entity 2: {entity2}

Few-shot examples:
Entity 1: "Apple Inc." (organization)
Entity 2: "Steve Jobs" (person)
Relationship: {{"type": "founded_by", "confidence": 0.95, "direction": "entity2 -> entity1"}}

Entity 1: "Cupertino" (location)
Entity 2: "California" (location)
Relationship: {{"type": "is_part_of", "confidence": 0.90, "direction": "entity1 -> entity2"}}

Identify the relationship between the given entities in JSON format:
""",
            "semantic_type_classification": """
You are an expert at classifying semantic types of data columns. Classify the following column data:

Column name: {column_name}
Sample values: {sample_values}

Few-shot examples:
Column: "email_address"
Values: ["john@example.com", "jane@company.org"]
Classification: {{"semantic_type": "email", "confidence": 0.95, "reasoning": "Values match email format"}}

Column: "phone_number"
Values: ["+1-555-1234", "555-5678"]
Classification: {{"semantic_type": "phone", "confidence": 0.90, "reasoning": "Values match phone number patterns"}}

Classify the semantic type in JSON format:
""",
            "ontology_mapping": """
You are an expert at creating ontology mappings from data profiles. Create mappings for the following dataset profile:

{profile_summary}

Few-shot examples:
Profile: Customer dataset with columns: customer_id, name, email, purchase_date, amount
Mapping: [
    {{"concept": "Customer", "type": "entity", "attributes": ["id", "name", "email"], "confidence": 0.95}},
    {{"concept": "Purchase", "type": "entity", "attributes": ["date", "amount"], "confidence": 0.90}},
    {{"concept": "has_purchase", "type": "relationship", "source": "Customer", "target": "Purchase", "confidence": 0.85}}
]

Create ontology mappings in JSON format:
""",
        }

    def _test_connection(self) -> bool:
        """Test connection to LM Studio service."""
        try:
            provider = "OpenAI" if self.use_openai else "LM Studio"
            logger.info(f"Testing connection to {provider} at {self.base_url}")
            headers = {}
            if self.use_openai and self.openai_api_key:
                headers["Authorization"] = f"Bearer {self.openai_api_key}"
            response = self.session.get(self._build_url("/models"), headers=headers, timeout=5)
            if response.status_code == 200:
                models = response.json().get("data", [])
                model_names = [m.get("id", "unknown") for m in models[:3]]
                logger.info(
                    f"✓ Successfully connected to {provider} at {self.base_url}"
                )
                logger.info(f"✓ Available models: {', '.join(model_names) if model_names else 'None'}")
                logger.info(f"✓ Using model: {self.default_model}")
                return True
            else:
                logger.warning(
                    f"✗ {provider} service responded with status {response.status_code}"
                )
                return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"✗ Cannot connect to {provider} at {self.base_url}")
            if not self.use_openai:
                logger.error("  Make sure LM Studio is running and accessible")
            logger.error(f"  Error: {e}")
            return False
        except requests.exceptions.RequestException as e:
            provider = "OpenAI" if self.use_openai else "LM Studio"
            logger.warning(f"✗ Failed to connect to {provider} service: {e}")
            return False
    
    def _build_url(self, path: str) -> str:
        """Build provider URL that works with or without a /v1 base."""
        base = self.base_url.rstrip("/")
        suffix = path.lstrip("/")
        if base.endswith("/v1"):
            return f"{base}/{suffix}"
        return f"{base}/v1/{suffix}"

    def _check_rate_limit(self) -> bool:
        """Check if request is within rate limits."""
        with self.rate_limit_lock:
            now = time.time()

            # Remove old timestamps outside the window
            while (
                self.request_timestamps
                and self.request_timestamps[0] < now - self.rate_limit_window
            ):
                self.request_timestamps.popleft()

            # Check if we can make a request
            if len(self.request_timestamps) < self.rate_limit_requests:
                self.request_timestamps.append(now)
                return True

            return False

    def _wait_for_rate_limit(self):
        """Wait until rate limit allows another request."""
        while not self._check_rate_limit():
            sleep_time = 1
            logger.debug(f"Rate limited, waiting {sleep_time} seconds")
            time.sleep(sleep_time)

    def _get_cached_response(self, prompt: str, model: str) -> Optional[ResponseCache]:
        """Get cached response if available and valid."""
        prompt_hash = hashlib.md5(f"{prompt}:{model}".encode()).hexdigest()

        # Check memory cache first
        if prompt_hash in self.response_cache:
            cache_entry = self.response_cache[prompt_hash]
            if datetime.now() - cache_entry.timestamp < timedelta(
                hours=self.cache_ttl_hours
            ):
                return cache_entry

        # Check file cache
        if self.cache_dir:
            cache_file = self.cache_dir / f"{prompt_hash}.pkl"
            if cache_file.exists():
                try:
                    with open(cache_file, "rb") as f:
                        cache_entry: ResponseCache = pickle.load(f)

                    if datetime.now() - cache_entry.timestamp < timedelta(
                        hours=self.cache_ttl_hours
                    ):
                        # Update memory cache
                        self.response_cache[prompt_hash] = cache_entry
                        return cache_entry
                except Exception as e:
                    logger.warning(f"Failed to load cached response: {e}")

        return None

    def _cache_response(
        self, prompt: str, model: str, response: str, confidence: float
    ):
        """Cache response for future use."""
        prompt_hash = hashlib.md5(f"{prompt}:{model}".encode()).hexdigest()

        cache_entry = ResponseCache(
            prompt_hash=prompt_hash,
            response=response,
            timestamp=datetime.now(),
            model=model,
            confidence=confidence,
        )

        # Update memory cache
        self.response_cache[prompt_hash] = cache_entry

        # Save to file cache
        if self.cache_dir:
            try:
                cache_file = self.cache_dir / f"{prompt_hash}.pkl"
                with open(cache_file, "wb") as f:
                    pickle.dump(cache_entry, f)
            except Exception as e:
                logger.warning(f"Failed to save cached response: {e}")

    def _load_cache(self):
        """Load cached responses from disk."""
        if not self.cache_dir:
            return

        try:
            for cache_file in self.cache_dir.glob("*.pkl"):
                try:
                    with open(cache_file, "rb") as f:
                        cache_entry: ResponseCache = pickle.load(f)

                    # Only load recent cache entries
                    if datetime.now() - cache_entry.timestamp < timedelta(
                        hours=self.cache_ttl_hours
                    ):
                        self.response_cache[cache_entry.prompt_hash] = cache_entry
                except Exception as e:
                    logger.warning(f"Failed to load cache file {cache_file}: {e}")

            logger.info(f"Loaded {len(self.response_cache)} cached responses")
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")

    def _make_request_with_retry(
        self, payload: dict[str, Any], model: str
    ) -> Optional[str]:
        """Make request with retry logic and exponential backoff."""
        for attempt in range(self.max_retries + 1):
            try:
                # Check rate limit
                self._wait_for_rate_limit()

                # Make request (use base_url which is either OpenAI or LM Studio)
                headers = {}
                if self.use_openai:
                    headers["Authorization"] = f"Bearer {self.openai_api_key}"
                
                response = self.session.post(
                    self._build_url("/chat/completions"),
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    result = response.json()
                    return (
                        result.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                        .strip()
                    )
                elif response.status_code == 429:
                    # Rate limit - wait longer before retry
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited (429), waiting {retry_after} seconds before retry")
                    if attempt < self.max_retries:
                        time.sleep(retry_after)
                        continue
                else:
                    logger.warning(f"Request failed with status {response.status_code}: {response.text[:200]}")

            except Exception as e:
                logger.warning(f"Request attempt {attempt + 1} failed: {e}")

                if attempt < self.max_retries:
                    # Exponential backoff
                    sleep_time = 2**attempt
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"All retry attempts failed for model {model}")

        return None

    def _try_model_fallback(
        self, prompt: str, max_tokens: int, temperature: float
    ) -> tuple[Optional[str], str]:
        """Try models in fallback chain until one succeeds."""
        for model in self.model_fallback_chain:
            if not self._is_model_available(model):
                continue

            logger.info(f"Trying model: {model}")

            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": temperature},
            }

            response = self._make_request_with_retry(payload, model)
            if response:
                return response, model

        return None, "none"

    def _is_model_available(self, model: str) -> bool:
        """Check if a specific model is available."""
        try:
            response = self.session.get(self._build_url("/models"), timeout=5)
            if response.status_code == 200:
                models = response.json().get("data", [])
                return any(m.get("id", "").startswith(model) for m in models)
            return False
        except Exception:
            return False

    def _count_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        # Simple estimation: 1 token ≈ 4 characters for English text
        return len(text) // 4

    def _extract_json_from_response(self, response: str) -> Optional[dict[str, Any]]:
        """Extract JSON from LLM response."""
        # Try to find JSON in the response
        json_patterns = [
            r"\{.*\}",  # Basic JSON object
            r"\[.*\]",  # JSON array
            r"\{[\s\S]*\}",  # JSON with newlines
            r"\[[\s\S]*\]",  # Array with newlines
        ]

        for pattern in json_patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue

        return None

    def _calculate_confidence(self, response: str, model: str) -> float:
        """Calculate confidence score based on response quality and model."""
        confidence = 0.5  # Base confidence

        # Model-specific confidence adjustments
        model_confidence = {
            "llama2": 0.9,
            "mistral": 0.85,
            "phi3": 0.8,
            "codellama": 0.85,
            "llama2-7b": 0.75,
        }

        confidence *= model_confidence.get(model, 0.7)

        # Response quality adjustments
        if response.strip():
            confidence += 0.1

        # JSON response bonus
        if self._extract_json_from_response(response):
            confidence += 0.2

        # Length bonus for detailed responses
        if len(response) > 100:
            confidence += 0.1

        return min(confidence, 1.0)

    def generate_text(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 100,
        temperature: float = 0.7,
        use_cache: bool = True,
    ) -> Optional[str]:
        """Generate text using LM Studio with caching and fallback."""
        model = model or self.default_model

        # Check cache first
        if use_cache:
            cached_response = self._get_cached_response(prompt, model)
            if cached_response:
                logger.info("Using cached response for prompt")
                return cached_response.response

        # Try primary model first
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        response = self._make_request_with_retry(payload, model)

        if response:
            confidence = self._calculate_confidence(response, model)
            if use_cache:
                self._cache_response(prompt, model, response, confidence)
            return response

        # Try model fallback
        logger.info(f"Primary model {model} failed, trying fallback models")
        response, fallback_model = self._try_model_fallback(
            prompt, max_tokens, temperature
        )

        if response:
            confidence = self._calculate_confidence(response, fallback_model)
            if use_cache:
                self._cache_response(prompt, fallback_model, response, confidence)
            return response

        return None

    def extract_entities(
        self, text: str, schema: dict[str, Any]
    ) -> Optional[EntityExtractionSchema]:
        """Extract entities from text using LLM.

        Args:
            text: Text to extract entities from
            schema: Entity extraction schema

        Returns:
            EntityExtractionSchema or None if failed
        """
        start_time = time.time()

        # Format schema for prompt
        schema_str = json.dumps(schema, indent=2)

        prompt = self.prompt_templates["entity_extraction"].format(
            entity_schema=schema_str, text=text
        )

        try:
            response = self.generate_text(prompt, max_tokens=500, temperature=0.3)
            if response:
                # Extract JSON from response
                json_data = self._extract_json_from_response(response)
                if json_data:
                    processing_time = time.time() - start_time

                    return EntityExtractionSchema(
                        entities=json_data.get("entities", []),
                        confidence=json_data.get("confidence", 0.7),
                        extraction_method="llm_extraction",
                        processing_time=processing_time,
                    )

            logger.warning("Failed to extract entities from LLM response")
            return None

        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return None

    def find_relationships(
        self, entity_pairs: list[tuple[dict[str, Any], dict[str, Any]]]
    ) -> Optional[RelationshipExtractionSchema]:
        """Find relationships between entity pairs using LLM.

        Args:
            entity_pairs: List of entity pairs to analyze

        Returns:
            RelationshipExtractionSchema or None if failed
        """
        start_time = time.time()
        all_relationships = []

        for entity1, entity2 in entity_pairs:
            prompt = self.prompt_templates["relationship_extraction"].format(
                entity1=f"{entity1.get('name', 'Unknown')} ({entity1.get('type', 'Unknown')})",
                entity2=f"{entity2.get('name', 'Unknown')} ({entity2.get('type', 'Unknown')})",
            )

            try:
                response = self.generate_text(prompt, max_tokens=200, temperature=0.3)
                if response:
                    json_data = self._extract_json_from_response(response)
                    if json_data:
                        all_relationships.append(json_data)

            except Exception as e:
                logger.warning(f"Relationship extraction failed for pair: {e}")
                continue

        if all_relationships:
            processing_time = time.time() - start_time

            return RelationshipExtractionSchema(
                relationships=all_relationships,
                confidence=0.8,  # Average confidence
                extraction_method="llm_relationship_extraction",
                processing_time=processing_time,
            )

        return None

    def classify_semantic_type(
        self, column_data: list[str], column_name: str
    ) -> Optional[SemanticTypeClassification]:
        """Classify semantic type of column data using LLM.

        Args:
            column_data: List of column values
            column_name: Name of the column

        Returns:
            SemanticTypeClassification or None if failed
        """
        # Sample data for analysis
        sample_values = column_data[:10] if len(column_data) > 10 else column_data
        sample_str = json.dumps(sample_values)

        prompt = self.prompt_templates["semantic_type_classification"].format(
            column_name=column_name, sample_values=sample_str
        )

        try:
            response = self.generate_text(prompt, max_tokens=300, temperature=0.3)
            if response:
                json_data = self._extract_json_from_response(response)
                if json_data:
                    return SemanticTypeClassification(
                        semantic_type=json_data.get("semantic_type", "unknown"),
                        confidence=json_data.get("confidence", 0.7),
                        reasoning=json_data.get("reasoning", ""),
                        alternative_types=json_data.get("alternative_types", []),
                    )

            logger.warning("Failed to classify semantic type from LLM response")
            return None

        except Exception as e:
            logger.error(f"Semantic type classification failed: {e}")
            return None

    def classify_entity_type(self, value: str, column_name: str) -> Optional[str]:
        """Classify the type of a single entity value using LLM.

        Args:
            value: The entity value to classify
            column_name: Name of the column containing the value

        Returns:
            Entity type string or None if failed
        """
        prompt = f"""
You are an expert at classifying entity types. Classify the following entity value:

Value: "{value}"
Column: "{column_name}"

Choose from these entity types:
- person: Names of people
- organization: Company names, institutions
- location: Places, addresses, cities
- product: Product names, services
- date: Dates, timestamps
- identifier: IDs, codes, serial numbers
- category: Types, classifications
- measurement: Quantities, amounts, dimensions
- contact: Emails, phone numbers, addresses
- concept: General concepts, ideas

Respond with only the entity type:
"""

        try:
            response = self.generate_text(prompt, max_tokens=50, temperature=0.1)
            if response:
                # Clean and validate response
                entity_type = response.strip().lower()
                valid_types = [
                    "person",
                    "organization",
                    "location",
                    "product",
                    "date",
                    "identifier",
                    "category",
                    "measurement",
                    "contact",
                    "concept",
                ]

                if entity_type in valid_types:
                    return entity_type
                else:
                    # Try to extract type from response
                    for valid_type in valid_types:
                        if valid_type in entity_type:
                            return valid_type

                    # Default fallback
                    return "concept"

            return None

        except Exception as e:
            logger.warning(f"Entity type classification failed: {e}")
            return None

    def suggest_relationship_type(
        self, entity_type1: str, entity_type2: str
    ) -> Optional[str]:
        """Suggest relationship type between two entity types using LLM.

        Args:
            entity_type1: First entity type
            entity_type2: Second entity type

        Returns:
            Relationship type string or None if failed
        """
        prompt = f"""
You are an expert at identifying relationships between entity types. Suggest a relationship type for:

Entity Type 1: {entity_type1}
Entity Type 2: {entity_type2}

Choose from these common relationship types:
- belongs_to: Entity 1 belongs to Entity 2
- contains: Entity 1 contains Entity 2
- references: Entity 1 references Entity 2
- is_part_of: Entity 1 is part of Entity 2
- has: Entity 1 has Entity 2
- located_in: Entity 1 is located in Entity 2
- works_for: Entity 1 works for Entity 2
- owns: Entity 1 owns Entity 2
- related_to: General relationship between entities

Respond with only the relationship type:
"""

        try:
            response = self.generate_text(prompt, max_tokens=50, temperature=0.1)
            if response:
                # Clean and validate response
                relationship_type = response.strip().lower()
                valid_types = [
                    "belongs_to",
                    "contains",
                    "references",
                    "is_part_of",
                    "has",
                    "located_in",
                    "works_for",
                    "owns",
                    "related_to",
                ]

                if relationship_type in valid_types:
                    return relationship_type
                else:
                    # Try to extract type from response
                    for valid_type in valid_types:
                        if valid_type in relationship_type:
                            return valid_type

                    # Default fallback
                    return "related_to"

            return None

        except Exception as e:
            logger.warning(f"Relationship type suggestion failed: {e}")
            return None

    def infer_column_relationship(
        self, col1_name: str, col2_name: str, sample_data: list[dict[str, Any]]
    ) -> Optional[dict[str, Any]]:
        """Infer relationship between two columns using LLM.

        Args:
            col1_name: Name of first column
            col2_name: Name of second column
            sample_data: Sample data from both columns

        Returns:
            Relationship information dict or None if failed
        """
        # Format sample data for prompt
        sample_str = json.dumps(sample_data[:5], indent=2)  # Limit to 5 samples

        prompt = f"""
You are an expert at analyzing relationships between data columns. Analyze the relationship between:

Column 1: "{col1_name}"
Column 2: "{col2_name}"
Sample Data: {sample_str}

Determine:
1. The type of relationship between these columns
2. The confidence level (0.0-1.0) in your assessment
3. Your reasoning for the relationship

Respond in JSON format:
{{
    "relationship_type": "relationship_type_here",
    "confidence": 0.85,
    "reasoning": "Your reasoning here"
}}

Common relationship types:
- foreign_key: One column references values in another
- hierarchical: Parent-child or category relationships
- temporal: Time-based relationships
- spatial: Location or address relationships
- ownership: Belongs to, contains, has relationships
- measurement: Quantity, amount, size relationships
- co_occurrence: Values that appear together
- unrelated: No clear relationship
"""

        try:
            response = self.generate_text(prompt, max_tokens=300, temperature=0.3)
            if response:
                # Extract JSON from response
                json_data = self._extract_json_from_response(response)
                if json_data:
                    return {
                        "relationship_type": json_data.get(
                            "relationship_type", "unrelated"
                        ),
                        "confidence": json_data.get("confidence", 0.5),
                        "reasoning": json_data.get(
                            "reasoning", "No reasoning provided"
                        ),
                    }

            return None

        except Exception as e:
            logger.warning(f"Column relationship inference failed: {e}")
            return None

    def generate_ontology_mapping(
        self, profile: dict[str, Any]
    ) -> Optional[OntologyMappingSchema]:
        """Generate ontology mapping from dataset profile using LLM.

        Args:
            profile: Dataset profile dictionary

        Returns:
            OntologyMappingSchema or None if failed
        """
        start_time = time.time()

        # Create profile summary
        profile_summary = {
            "columns": profile.get("columns", []),
            "row_count": profile.get("row_count", 0),
            "data_types": profile.get("data_types", {}),
            "key_columns": profile.get("key_columns", []),
        }

        prompt = self.prompt_templates["ontology_mapping"].format(
            profile_summary=json.dumps(profile_summary, indent=2)
        )

        try:
            response = self.generate_text(prompt, max_tokens=500, temperature=0.3)
            if response:
                json_data = self._extract_json_from_response(response)
                if json_data:
                    processing_time = time.time() - start_time

                    return OntologyMappingSchema(
                        mappings=json_data.get("mappings", []),
                        confidence=json_data.get("confidence", 0.7),
                        ontology_type=json_data.get("ontology_type", "general"),
                        processing_time=processing_time,
                    )

            logger.warning("Failed to generate ontology mapping from LLM response")
            return None

        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"Ontology mapping generation failed: {e}")
            return None

    def clear_cache(self) -> bool:
        """Clear all cached responses."""
        try:
            # Clear memory cache
            self.response_cache.clear()

            # Clear file cache
            if self.cache_dir:
                cache_files = list(self.cache_dir.glob("*.pkl"))
                for cache_file in cache_files:
                    cache_file.unlink()

                logger.info(f"Cleared {len(cache_files)} cached responses")

            return True

        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "memory_cache_size": len(self.response_cache),
            "cache_dir": str(self.cache_dir) if self.cache_dir else None,
            "cache_ttl_hours": self.cache_ttl_hours,
            "rate_limit_requests": self.rate_limit_requests,
            "rate_limit_window": self.rate_limit_window,
        }

    def get_rate_limit_status(self) -> dict[str, Any]:
        """Get current rate limit status."""
        with self.rate_limit_lock:
            now = time.time()
            recent_requests = [
                ts
                for ts in self.request_timestamps
                if now - ts < self.rate_limit_window
            ]

            return {
                "requests_in_window": len(recent_requests),
                "max_requests": self.rate_limit_requests,
                "window_seconds": self.rate_limit_window,
                "can_make_request": len(recent_requests) < self.rate_limit_requests,
            }

    def list_models(self) -> list[dict[str, Any]]:
        """List available models from LM Studio."""
        try:
            response = self.session.get(f"{self.lmstudio_url}/v1/models", timeout=5)
            if response.status_code == 200:
                return response.json().get("data", [])
            else:
                logger.warning(f"Failed to get models: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    def identify_business_entities(self, prompt: str, **kwargs) -> dict[str, Any]:
        """Identify business entities from the given prompt."""
        try:
            response = self.generate_text(
                prompt, 
                max_tokens=kwargs.get('max_tokens', 500),
                temperature=kwargs.get('temperature', 0.3)
            )
            
            if response:
                # Try to extract JSON from response
                json_data = self._extract_json_from_response(response)
                if json_data:
                    return json_data
                
                # If no JSON found, return basic structure
                return {
                    "entities": [],
                    "confidence": 0.5,
                    "raw_response": response
                }
            
            return {"entities": [], "confidence": 0.0}
            
        except Exception as e:
            logger.error(f"Business entity identification failed: {e}")
            return {"entities": [], "confidence": 0.0, "error": str(e)}

    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, "session"):
            self.session.close()
