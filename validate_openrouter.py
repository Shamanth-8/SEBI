#!/usr/bin/env python3
"""
RegGraph OpenRouter Configuration Validator
Verifies that OpenRouter API is properly configured and working.
"""

import sys
sys.path.insert(0, './backend')

from app.config import get_settings
from app.anthropic_adapter import create_anthropic_compatible_client
import json

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")

def test_configuration():
    """Test that configuration is properly loaded."""
    print_header("1. Configuration Check")
    
    settings = get_settings()
    
    print(f"✓ Provider: {settings.LLM_PROVIDER}")
    print(f"✓ Model: {settings.LLM_MODEL}")
    print(f"✓ API Key configured: {bool(settings.LLM_API_KEY)}")
    
    if not settings.LLM_API_KEY:
        print("❌ ERROR: API Key not configured!")
        return False
    
    print(f"✓ API Key (first 20 chars): {settings.LLM_API_KEY[:20]}...")
    return True

def test_adapter_initialization():
    """Test that the adapter initializes correctly."""
    print_header("2. Adapter Initialization")
    
    try:
        settings = get_settings()
        client = create_anthropic_compatible_client(settings.LLM_PROVIDER)
        
        print(f"✓ Client type: {type(client).__name__}")
        print(f"✓ Base URL: {settings.OPENROUTER_BASE_URL}")
        print(f"✓ OpenRouter model: {settings.OPENROUTER_MODEL}")
        
        return True
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_message_interface():
    """Test that the Anthropic-compatible interface works."""
    print_header("3. Message Interface Test")
    
    try:
        settings = get_settings()
        client = create_anthropic_compatible_client(settings.LLM_PROVIDER)
        
        print(f"Creating test message...")
        response = client.messages.create(
            messages=[
                {"role": "user", "content": "Say 'OpenRouter is working!' in exactly 4 words"}
            ],
            max_tokens=50,
            temperature=0.7
        )
        
        print(f"✓ Response received!")
        print(f"✓ Content: {response.content[0].text}")
        print(f"✓ Model: {response.model}")
        print(f"✓ Stop reason: {response.stop_reason}")
        print(f"✓ Tokens used - Input: {response.usage.input_tokens}, Output: {response.usage.output_tokens}")
        
        return True
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_agent_initialization():
    """Test that agents can be initialized."""
    print_header("4. Agent Initialization Test")
    
    try:
        from app.agents.extraction_agent import ObligationExtractionAgent
        from app.agents.diff_agent import SemanticDiffAgent
        from app.agents.mapping_agent import ComplianceMappingAgent
        from app.graph.obligation_graph import ObligationGraph
        
        # Test extraction agent
        extraction_agent = ObligationExtractionAgent()
        print(f"✓ Extraction agent initialized (model: {extraction_agent.model})")
        
        # Test graph
        graph = ObligationGraph()
        print(f"✓ Obligation graph initialized")
        
        # Test diff agent
        diff_agent = SemanticDiffAgent(graph)
        print(f"✓ Diff agent initialized (model: {diff_agent.model})")
        
        # Test mapping agent
        mapping_agent = ComplianceMappingAgent(graph)
        print(f"✓ Mapping agent initialized (model: {mapping_agent.model})")
        
        return True
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_provider_comparison():
    """Show provider comparison info."""
    print_header("5. Provider Configuration Status")
    
    settings = get_settings()
    
    print(f"\n📌 Current Configuration:")
    print(f"   Provider: {settings.LLM_PROVIDER.upper()}")
    print(f"   Model: {settings.LLM_MODEL}")
    print(f"   Timeout: {settings.LLM_TIMEOUT} seconds")
    
    print(f"\n📌 To Switch Providers:")
    print(f"\n   Switch to OpenRouter:")
    print(f"   LLM_PROVIDER=openrouter")
    print(f"   OPENROUTER_API_KEY=sk-or-v1-xxx")
    print(f"\n   Switch to Anthropic:")
    print(f"   LLM_PROVIDER=anthropic")
    print(f"   ANTHROPIC_API_KEY=sk-ant-xxx")
    
    return True

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("  RegGraph OpenRouter Configuration Validator")
    print("="*60)
    
    tests = [
        ("Configuration Check", test_configuration),
        ("Adapter Initialization", test_adapter_initialization),
        ("Message Interface", test_message_interface),
        ("Agent Initialization", test_agent_initialization),
        ("Provider Comparison", test_provider_comparison),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print_header("Summary")
    
    for test_name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All tests passed! OpenRouter is properly configured.")
        print("\n🚀 Next steps:")
        print("   1. Start the API: cd backend && python -m uvicorn app.main:app --reload")
        print("   2. Start the Dashboard: cd frontend && streamlit run dashboard.py")
        print("   3. Open http://localhost:8501")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    exit(main())
