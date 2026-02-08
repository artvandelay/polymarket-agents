"""
Simple test to verify OpenRouter API key works with Claude Sonnet.
"""
import os
import asyncio
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_openrouter():
    api_key = os.getenv("OPENROUTER_API_KEY")
    
    if not api_key:
        print("❌ OPENROUTER_API_KEY not found")
        return False
    
    print(f"✓ Key: {api_key[:20]}...")
    
    # OpenRouter API endpoint
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    # Simple test prompt
    payload = {
        "model": "anthropic/claude-3.5-sonnet",
        "messages": [
            {
                "role": "user",
                "content": "Say 'Hello from Claude Sonnet via OpenRouter!' and nothing else."
            }
        ],
        "max_tokens": 50
    }
    
    print("\n🔄 Testing...")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            message = data["choices"][0]["message"]["content"]
            
            print(f"✅ {message}\n")
            return True
            
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        print(f"   {e.response.text}\n")
        return False
    except Exception as e:
        print(f"❌ Error: {e}\n")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Testing OpenRouter")
    print("=" * 50 + "\n")
    
    success = asyncio.run(test_openrouter())
    
    if success:
        print("=" * 50)
        print("✅ Ready")
        print("=" * 50)
    else:
        print("=" * 50)
        print("❌ Failed")
        print("=" * 50)
