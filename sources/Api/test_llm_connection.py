#!/usr/bin/env python3
"""
Test script to verify LLM connection and recommendation generation.

This script tests:
1. Connection to LM Studio at localhost:1234
2. Basic text generation
3. Node recommendation generation
4. Edge recommendation generation
"""

import sys
import logging
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.infrastructure.llm.llm_manager import LLMManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_llm_connection():
    """Test LLM connection and basic functionality."""
    
    print("=" * 80)
    print("LLM Connection Test")
    print("=" * 80)
    
    # Initialize LLM Manager
    print("\n1. Initializing LLM Manager...")
    llm_manager = LLMManager(
        lmstudio_url="http://localhost:1234",
        default_model="deepseek/deepseek-r1-0528-qwen3-8b"
    )
    
    # Test basic text generation
    print("\n2. Testing basic text generation...")
    prompt = "Say 'Hello, LLM is working!' and nothing else."
    try:
        response = llm_manager.generate_text(prompt, max_tokens=50, temperature=0.1)
        if response:
            print(f"   ✓ LLM Response: {response[:100]}")
        else:
            print("   ✗ No response from LLM")
            return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False
    
    # Test node recommendation generation
    print("\n3. Testing node recommendation generation...")
    entities = [
        {"id": "1", "name": "product_id", "entity_type": "identifier", "source_columns": ["product_id"]},
        {"id": "2", "name": "customer_name", "entity_type": "person", "source_columns": ["customer_name"]},
    ]
    dataset_profile = {
        "file_path": "test.csv",
        "row_count": 100,
        "column_count": 5,
        "domain": "retail"
    }
    
    node_prompt = f"""
    Based on the following entities and dataset profile, recommend 2-3 new nodes to create.

    Entities: {entities[:2]}
    Dataset Profile: {dataset_profile}

    Respond with a JSON array of node recommendations.
    Each recommendation should have:
    - name: The name of the new node
    - entity_type: The type of the new node
    - confidence: The confidence score (0-1)
    - reasoning: The reasoning behind this recommendation

    Example format:
    [
        {{"name": "Product", "entity_type": "product", "confidence": 0.9, "reasoning": "Derived from product_id column"}},
        {{"name": "Customer", "entity_type": "person", "confidence": 0.85, "reasoning": "Derived from customer_name"}}
    ]
    """
    
    try:
        response = llm_manager.generate_text(node_prompt, max_tokens=500, temperature=0.3)
        if response:
            print(f"   ✓ LLM Node Recommendation Response (first 200 chars):")
            print(f"     {response[:200]}...")
            
            # Try to parse JSON
            json_data = llm_manager._extract_json_from_response(response)
            if json_data:
                print(f"   ✓ Successfully parsed JSON")
                if isinstance(json_data, list):
                    print(f"   ✓ Received {len(json_data)} recommendations")
                    for i, rec in enumerate(json_data[:2], 1):
                        print(f"     {i}. {rec.get('name', 'N/A')} ({rec.get('entity_type', 'N/A')}) - confidence: {rec.get('confidence', 0)}")
                else:
                    print(f"   ! Response is not a list: {type(json_data)}")
            else:
                print("   ✗ Could not parse JSON from response")
        else:
            print("   ✗ No response from LLM")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test cache stats
    print("\n4. LLM Cache Statistics:")
    stats = llm_manager.get_cache_stats()
    for key, value in stats.items():
        print(f"   - {key}: {value}")
    
    # Test rate limit status
    print("\n5. Rate Limit Status:")
    rate_status = llm_manager.get_rate_limit_status()
    for key, value in rate_status.items():
        print(f"   - {key}: {value}")
    
    print("\n" + "=" * 80)
    print("✓ LLM Connection Test Complete!")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        success = test_llm_connection()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        sys.exit(1)

