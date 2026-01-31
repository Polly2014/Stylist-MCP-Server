"""
Test script for Stylist MCP Server
Validates that the server is running and tools are working
"""
import sys
import os
import json
import requests
import argparse

# Change to project root so .env is found
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)

# Add src to path
sys.path.insert(0, os.path.join(project_root, 'src'))

# Load API key from .env
def load_api_key():
    env_file = os.path.join(project_root, '.env')
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                if line.strip().startswith('MCP_API_KEY='):
                    return line.strip().split('=', 1)[1]
    return None

API_KEY = load_api_key()


def test_health(base_url: str):
    """Test health endpoint (public, no auth needed)"""
    print("Testing /health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Server is healthy")
            print(f"     Status: {data.get('status')}")
            print(f"     Transport: {data.get('transport')}")
            print(f"     Tools: {data.get('tools')}")
            print(f"     Auth enabled: {data.get('auth_enabled')}")
            return True
        else:
            print(f"  ❌ Health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"  ❌ Cannot connect to {base_url}")
        return False


def test_tools_list(base_url: str, api_key: str = None):
    """Test tools listing endpoint"""
    print("\nTesting /tools endpoint...")
    try:
        url = f"{base_url}/tools"
        if api_key:
            url += f"?apiKey={api_key}"
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            tools = data.get("tools", [])
            print(f"  ✅ Found {len(tools)} tools:")
            for tool in tools:
                print(f"     - {tool['name']}: {tool['description'][:60]}...")
            return True
        elif response.status_code == 401:
            print(f"  ❌ Unauthorized - API key required or invalid")
            return False
        else:
            print(f"  ❌ Tools list failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_image_access(base_url: str):
    """Test image serving endpoint"""
    print("\nTesting /images endpoint...")
    try:
        # Test a known image
        test_url = f"{base_url}/images/dresses/images/020714_1.jpg"
        response = requests.head(test_url, timeout=5)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            print(f"  ✅ Image serving works")
            print(f"     Content-Type: {content_type}")
            return True
        else:
            print(f"  ❌ Image access failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_stylist_tool():
    """Test the StylistSearchTool directly"""
    print("\nTesting StylistSearchTool directly...")
    try:
        from stylist_tool import StylistSearchTool
        
        tool = StylistSearchTool()
        
        # Test simple query with image URLs
        result = tool.recommend_outfit(
            "recommend a casual dress for summer",
            include_reasoning=False,
            include_image_urls=True,
            image_url_generator=lambda x: f"https://stylist.polly.wang/images/{x.split('DressCode/')[-1]}" if x else None
        )
        
        mode = result.get("mode")
        if mode == "full_outfit":
            count = result.get("num_outfits", 0)
            # Check if image_url is present
            outfits = result.get("outfits", [])
            has_urls = any(
                o.get("dress", {}).get("image_url") or 
                o.get("top", {}).get("image_url") 
                for o in outfits
            )
        else:
            count = result.get("num_results", 0)
            recommendations = result.get("recommendations", [])
            has_urls = any(r.get("image_url") for r in recommendations)
        
        print(f"  ✅ Tool works! Mode: {mode}, Results: {count}")
        print(f"     Image URLs included: {'Yes' if has_urls else 'No'}")
        return True
    except Exception as e:
        print(f"  ❌ Tool error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_garment_db():
    """Test the GarmentDatabase"""
    print("\nTesting GarmentDatabase...")
    try:
        from garment_db import GarmentDatabase
        
        db = GarmentDatabase()
        total = db.collection.count()
        
        if total == 0:
            print(f"  ⚠️  Database is empty! Run scripts/build_chromadb.py first")
            return False
        
        print(f"  ✅ Database connected, {total} garments indexed")
        
        # Test search
        results = db.search("blue dress", n_results=3)
        print(f"     Search test: {len(results)} results for 'blue dress'")
        
        return True
    except Exception as e:
        print(f"  ❌ Database error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test Stylist MCP Server")
    parser.add_argument(
        "--url", type=str, default="https://stylist.polly.wang",
        help="Server URL for SSE mode tests"
    )
    parser.add_argument(
        "--local-only", action="store_true",
        help="Only run local tests (no HTTP)"
    )
    parser.add_argument(
        "--api-key", type=str, default=None,
        help="API key for authentication (reads from .env if not provided)"
    )
    
    args = parser.parse_args()
    api_key = args.api_key or API_KEY
    
    print("=" * 60)
    print("  Stylist MCP Server Test Suite")
    print("=" * 60)
    print()
    
    if api_key:
        print(f"Using API Key: {api_key[:15]}...")
    else:
        print("⚠️  No API Key configured (auth may fail)")
    print()
    
    results = []
    
    # Local tests
    results.append(("GarmentDatabase", test_garment_db()))
    results.append(("StylistSearchTool", test_stylist_tool()))
    
    # Remote tests (if not local-only)
    if not args.local_only:
        print(f"\nTesting remote server at {args.url}...")
        results.append(("Health Endpoint", test_health(args.url)))
        results.append(("Tools Endpoint", test_tools_list(args.url, api_key)))
        results.append(("Image Serving", test_image_access(args.url)))
    
    # Summary
    print()
    print("=" * 60)
    print("  Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}  {name}")
    
    print()
    print(f"  {passed}/{total} tests passed")
    
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
