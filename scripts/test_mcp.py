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


def test_health(base_url: str):
    """Test health endpoint"""
    print("Testing /health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Server is healthy")
            print(f"     Status: {data.get('status')}")
            print(f"     Transport: {data.get('transport')}")
            print(f"     Tools: {data.get('tools')}")
            return True
        else:
            print(f"  ❌ Health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"  ❌ Cannot connect to {base_url}")
        return False


def test_tools_list(base_url: str):
    """Test tools listing endpoint"""
    print("\nTesting /tools endpoint...")
    try:
        response = requests.get(f"{base_url}/tools", timeout=5)
        if response.status_code == 200:
            data = response.json()
            tools = data.get("tools", [])
            print(f"  ✅ Found {len(tools)} tools:")
            for tool in tools:
                print(f"     - {tool['name']}: {tool['description'][:60]}...")
            return True
        else:
            print(f"  ❌ Tools list failed: {response.status_code}")
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
        
        # Test simple query
        result = tool.recommend_outfit(
            "recommend a casual dress for summer",
            include_reasoning=False
        )
        
        mode = result.get("mode")
        if mode == "full_outfit":
            count = result.get("num_outfits", 0)
        else:
            count = result.get("num_results", 0)
        
        print(f"  ✅ Tool works! Mode: {mode}, Results: {count}")
        return True
    except Exception as e:
        print(f"  ❌ Tool error: {e}")
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
        "--url", type=str, default="http://localhost:8080",
        help="Server URL for SSE mode tests"
    )
    parser.add_argument(
        "--local-only", action="store_true",
        help="Only run local tests (no HTTP)"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("  Stylist MCP Server Test Suite")
    print("=" * 60)
    print()
    
    results = []
    
    # Local tests
    results.append(("GarmentDatabase", test_garment_db()))
    results.append(("StylistSearchTool", test_stylist_tool()))
    
    # Remote tests (if not local-only)
    if not args.local_only:
        print(f"\nTesting remote server at {args.url}...")
        results.append(("Health Endpoint", test_health(args.url)))
        results.append(("Tools Endpoint", test_tools_list(args.url)))
    
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
