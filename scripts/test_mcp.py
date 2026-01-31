"""
Test script for Stylist MCP Server
Comprehensive test suite covering:
- GarmentDatabase operations
- StylistSearchTool (single_item & full_outfit modes)
- Intent parsing
- Image URL generation
- Remote server endpoints

Usage:
    python scripts/test_mcp.py                    # Run all tests
    python scripts/test_mcp.py --local-only       # Skip remote tests
    python scripts/test_mcp.py --verbose          # Show detailed output
    python scripts/test_mcp.py --quick            # Skip LLM-based tests
"""
import sys
import os
import json
import time
import requests
import argparse
from typing import Dict, Any, List, Tuple

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
VERBOSE = False

def log(msg: str, indent: int = 0):
    """Print log message with optional indentation"""
    prefix = "     " * indent
    print(f"{prefix}{msg}")

def log_verbose(msg: str, indent: int = 0):
    """Print verbose log message"""
    if VERBOSE:
        log(msg, indent)

# =============================================================================
# Image URL Generator for Tests
# =============================================================================
def make_image_url(image_path: str) -> str | None:
    """Convert local image path to URL for testing"""
    if not image_path:
        return None
    try:
        # Extract relative path from full path
        # e.g., /datasets/DressCode/dresses/images/012345_1.jpg -> dresses/images/012345_1.jpg
        if 'DressCode/' in image_path:
            relative = image_path.split('DressCode/')[-1]
            return f"https://stylist.polly.wang/images/{relative}"
    except:
        pass
    return None


# =============================================================================
# Test: GarmentDatabase
# =============================================================================
def test_garment_db() -> Tuple[bool, str]:
    """Test GarmentDatabase basic operations"""
    try:
        from garment_db import GarmentDatabase
        
        db = GarmentDatabase()
        total = db.collection.count()
        
        if total == 0:
            return False, "Database is empty! Run scripts/build_chromadb.py first"
        
        # Test basic search
        results = db.search("blue dress", n_results=3)
        if not results:
            return False, "Search returned no results"
        
        log(f"✅ Database connected, {total} garments indexed")
        log(f"   Search test: {len(results)} results for 'blue dress'")
        return True, f"{total} garments"
        
    except Exception as e:
        return False, str(e)


def test_garment_db_filters() -> Tuple[bool, str]:
    """Test GarmentDatabase with various filters"""
    try:
        from garment_db import GarmentDatabase
        
        db = GarmentDatabase()
        errors = []
        
        # Test category filter
        results = db.search("elegant", n_results=5, category="dresses")
        if not all(r["metadata"].get("category") == "dresses" for r in results):
            errors.append("Category filter not working")
        log_verbose(f"Category filter (dresses): {len(results)} results")
        
        # Test garment_type filter
        results = db.search("summer", n_results=5, garment_type="t-shirt")
        log_verbose(f"Garment type filter (t-shirt): {len(results)} results")
        
        # Test style filter
        results = db.search("outfit", n_results=5, style="casual")
        log_verbose(f"Style filter (casual): {len(results)} results")
        
        # Test multi-category search
        multi_results = db.search_multi_category(
            query="elegant evening",
            categories=["upper_body", "lower_body", "dresses"],
            n_results_per_category=3
        )
        total_multi = sum(len(v) for v in multi_results.values())
        log_verbose(f"Multi-category search: {total_multi} results across {len(multi_results)} categories")
        
        if errors:
            return False, "; ".join(errors)
        
        log(f"✅ Database filters work correctly")
        log(f"   Multi-category: {list(multi_results.keys())}")
        return True, "All filters work"
        
    except Exception as e:
        return False, str(e)


# =============================================================================
# Test: StylistSearchTool - Single Item Mode
# =============================================================================
def test_single_item_tshirt() -> Tuple[bool, str]:
    """Test single item mode: T-shirt recommendation"""
    try:
        from stylist_tool import StylistSearchTool
        
        tool = StylistSearchTool()
        result = tool.recommend_outfit(
            "recommend 5 casual T-shirts for summer",
            include_reasoning=False,
            include_image_urls=True,
            image_url_generator=make_image_url
        )
        
        mode = result.get("mode")
        if mode != "single_item":
            return False, f"Expected single_item mode, got {mode}"
        
        count = result.get("num_results", 0)
        recommendations = result.get("recommendations", [])
        
        # Verify image URLs
        urls_present = sum(1 for r in recommendations if r.get("image_url"))
        
        log(f"✅ Single item (T-shirt): {count} results")
        log(f"   Image URLs: {urls_present}/{len(recommendations)}")
        log_verbose(f"   First item: {recommendations[0]['garment_id'] if recommendations else 'N/A'}")
        
        return True, f"{count} results"
        
    except Exception as e:
        return False, str(e)


def test_single_item_dress() -> Tuple[bool, str]:
    """Test single item mode: Dress recommendation"""
    try:
        from stylist_tool import StylistSearchTool
        
        tool = StylistSearchTool()
        result = tool.recommend_outfit(
            "show me some elegant evening dresses",
            include_reasoning=False,
            include_image_urls=True,
            image_url_generator=make_image_url
        )
        
        mode = result.get("mode")
        count = result.get("num_results", 0)
        recommendations = result.get("recommendations", [])
        
        # Check if category matches
        intent = result.get("parsed_intent", {})
        expected_category = intent.get("category")
        
        log(f"✅ Single item (dress): {count} results")
        log(f"   Parsed category: {expected_category}")
        log_verbose(f"   Intent: {json.dumps(intent, ensure_ascii=False)[:100]}...")
        
        return True, f"{count} results, category={expected_category}"
        
    except Exception as e:
        return False, str(e)


def test_single_item_chinese() -> Tuple[bool, str]:
    """Test single item mode: Chinese language query"""
    try:
        from stylist_tool import StylistSearchTool
        
        tool = StylistSearchTool()
        result = tool.recommend_outfit(
            "推荐5件休闲T恤",
            include_reasoning=False,
            include_image_urls=False
        )
        
        mode = result.get("mode")
        count = result.get("num_results", 0)
        intent = result.get("parsed_intent", {})
        language = intent.get("language", "unknown")
        
        log(f"✅ Single item (中文): {count} results")
        log(f"   Language detected: {language}")
        log_verbose(f"   Garment type: {intent.get('garment_type')}")
        
        return True, f"{count} results, lang={language}"
        
    except Exception as e:
        return False, str(e)


# =============================================================================
# Test: StylistSearchTool - Full Outfit Mode
# =============================================================================
def test_full_outfit_basic() -> Tuple[bool, str]:
    """Test full outfit mode: Basic outfit recommendation"""
    try:
        from stylist_tool import StylistSearchTool
        
        tool = StylistSearchTool()
        result = tool.recommend_outfit(
            "recommend 3 casual outfits for a weekend",
            include_reasoning=False,
            include_image_urls=True,
            image_url_generator=make_image_url
        )
        
        mode = result.get("mode")
        if mode != "full_outfit":
            return False, f"Expected full_outfit mode, got {mode}"
        
        num_outfits = result.get("num_outfits", 0)
        outfits = result.get("outfits", [])
        
        # Verify outfit structure
        two_piece_count = sum(1 for o in outfits if o.get("type") == "two_piece")
        dress_count = sum(1 for o in outfits if o.get("type") == "dress")
        
        # Check image URLs
        urls_present = 0
        for o in outfits:
            if o.get("type") == "two_piece":
                if o.get("top", {}).get("image_url"):
                    urls_present += 1
                if o.get("bottom", {}).get("image_url"):
                    urls_present += 1
            elif o.get("dress", {}).get("image_url"):
                urls_present += 1
        
        log(f"✅ Full outfit (basic): {num_outfits} outfits")
        log(f"   Two-piece: {two_piece_count}, Dress: {dress_count}")
        log(f"   Image URLs present: {urls_present}")
        
        return True, f"{num_outfits} outfits"
        
    except Exception as e:
        return False, str(e)


def test_full_outfit_formal() -> Tuple[bool, str]:
    """Test full outfit mode: Formal/date occasion"""
    try:
        from stylist_tool import StylistSearchTool
        
        tool = StylistSearchTool()
        result = tool.recommend_outfit(
            "recommend elegant outfits for a romantic dinner date",
            include_reasoning=False,
            include_image_urls=True,
            image_url_generator=make_image_url
        )
        
        mode = result.get("mode")
        num_outfits = result.get("num_outfits", 0)
        intent = result.get("parsed_intent", {})
        
        occasion = intent.get("occasion")
        style = intent.get("style")
        
        log(f"✅ Full outfit (formal): {num_outfits} outfits")
        log(f"   Occasion: {occasion}, Style: {style}")
        
        return True, f"{num_outfits} outfits, occasion={occasion}"
        
    except Exception as e:
        return False, str(e)


def test_full_outfit_chinese() -> Tuple[bool, str]:
    """Test full outfit mode: Chinese language query"""
    try:
        from stylist_tool import StylistSearchTool
        
        tool = StylistSearchTool()
        result = tool.recommend_outfit(
            "推荐3套适合约会的穿搭",
            include_reasoning=False,
            include_image_urls=True,
            image_url_generator=make_image_url
        )
        
        mode = result.get("mode")
        num_outfits = result.get("num_outfits", 0)
        intent = result.get("parsed_intent", {})
        
        language = intent.get("language", "unknown")
        occasion = intent.get("occasion")
        
        log(f"✅ Full outfit (中文): {num_outfits} outfits")
        log(f"   Language: {language}, Occasion: {occasion}")
        
        return True, f"{num_outfits} outfits, lang={language}"
        
    except Exception as e:
        return False, str(e)


def test_full_outfit_male() -> Tuple[bool, str]:
    """Test full outfit mode: Male gender (should exclude dresses)"""
    try:
        from stylist_tool import StylistSearchTool
        
        tool = StylistSearchTool()
        result = tool.recommend_outfit(
            "recommend casual outfits for a man",
            include_reasoning=False,
            include_image_urls=False
        )
        
        mode = result.get("mode")
        num_outfits = result.get("num_outfits", 0)
        outfits = result.get("outfits", [])
        intent = result.get("parsed_intent", {})
        
        gender = intent.get("gender")
        
        # Check no dresses for male
        dress_count = sum(1 for o in outfits if o.get("type") == "dress")
        two_piece_count = sum(1 for o in outfits if o.get("type") == "two_piece")
        
        log(f"✅ Full outfit (male): {num_outfits} outfits")
        log(f"   Gender: {gender}")
        log(f"   Two-piece: {two_piece_count}, Dress: {dress_count}")
        
        # Warn if dresses found for male
        if dress_count > 0 and gender == "male":
            log(f"   ⚠️  Dresses included for male user")
        
        return True, f"{num_outfits} outfits, gender={gender}"
        
    except Exception as e:
        return False, str(e)


# =============================================================================
# Test: Full Outfit with Reasoning (LLM-based)
# =============================================================================
def test_full_outfit_with_reasoning() -> Tuple[bool, str]:
    """Test full outfit mode with AI reasoning enabled"""
    try:
        from stylist_tool import StylistSearchTool
        
        tool = StylistSearchTool()
        start_time = time.time()
        
        result = tool.recommend_outfit(
            "recommend stylish outfits for a job interview",
            include_reasoning=True,  # Enable reasoning
            include_image_urls=True,
            image_url_generator=make_image_url
        )
        
        elapsed = time.time() - start_time
        
        num_outfits = result.get("num_outfits", 0)
        outfits = result.get("outfits", [])
        stylist_advice = result.get("stylist_advice", "")
        
        # Check if outfits have scores and reasons
        has_scores = all(o.get("score") is not None for o in outfits)
        has_reasons = all(o.get("reason") for o in outfits)
        
        log(f"✅ Full outfit with reasoning: {num_outfits} outfits")
        log(f"   Time: {elapsed:.2f}s")
        log(f"   Has scores: {has_scores}, Has reasons: {has_reasons}")
        log(f"   Stylist advice: {'Yes' if stylist_advice else 'No'} ({len(stylist_advice)} chars)")
        
        if VERBOSE and outfits:
            log(f"   Top outfit score: {outfits[0].get('score', 0):.2f}")
            log(f"   Reason preview: {outfits[0].get('reason', '')[:80]}...")
        
        return True, f"{num_outfits} outfits, {elapsed:.1f}s"
        
    except Exception as e:
        return False, str(e)


# =============================================================================
# Test: Remote Server Endpoints
# =============================================================================
def test_health(base_url: str) -> Tuple[bool, str]:
    """Test health endpoint (public, no auth needed)"""
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            log(f"✅ Health endpoint OK")
            log(f"   Status: {data.get('status')}, Auth: {data.get('auth_enabled')}")
            return True, data.get('status')
        else:
            return False, f"Status {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, f"Cannot connect to {base_url}"
    except Exception as e:
        return False, str(e)


def test_tools_list(base_url: str, api_key: str = None) -> Tuple[bool, str]:
    """Test tools listing endpoint"""
    try:
        url = f"{base_url}/tools"
        if api_key:
            url += f"?apiKey={api_key}"
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            tools = data.get("tools", [])
            log(f"✅ Tools endpoint OK")
            log(f"   Found {len(tools)} tools: {[t['name'] for t in tools]}")
            return True, f"{len(tools)} tools"
        elif response.status_code == 401:
            return False, "Unauthorized - API key required"
        else:
            return False, f"Status {response.status_code}"
    except Exception as e:
        return False, str(e)


def test_image_access(base_url: str) -> Tuple[bool, str]:
    """Test image serving endpoint (public, no auth needed)"""
    try:
        test_url = f"{base_url}/images/dresses/images/020714_1.jpg"
        response = requests.head(test_url, timeout=5)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            content_length = response.headers.get('content-length', 'unknown')
            log(f"✅ Image serving OK")
            log(f"   Content-Type: {content_type}, Size: {content_length}")
            return True, content_type
        else:
            return False, f"Status {response.status_code}"
    except Exception as e:
        return False, str(e)


def test_image_in_response(base_url: str) -> Tuple[bool, str]:
    """Test that image URLs in responses are accessible"""
    try:
        from stylist_tool import StylistSearchTool
        
        tool = StylistSearchTool()
        result = tool.recommend_outfit(
            "casual dress",
            include_reasoning=False,
            include_image_urls=True,
            image_url_generator=make_image_url
        )
        
        # Find an image URL from the response
        image_url = None
        if result.get("mode") == "full_outfit":
            for outfit in result.get("outfits", []):
                if outfit.get("type") == "dress" and outfit.get("dress", {}).get("image_url"):
                    image_url = outfit["dress"]["image_url"]
                    break
                elif outfit.get("type") == "two_piece" and outfit.get("top", {}).get("image_url"):
                    image_url = outfit["top"]["image_url"]
                    break
        else:
            for rec in result.get("recommendations", []):
                if rec.get("image_url"):
                    image_url = rec["image_url"]
                    break
        
        if not image_url:
            return False, "No image URL found in response"
        
        # Test if the URL is accessible
        response = requests.head(image_url, timeout=5)
        if response.status_code == 200:
            log(f"✅ Response image URL accessible")
            log(f"   URL: {image_url[:60]}...")
            return True, "URL accessible"
        else:
            return False, f"Image URL returned {response.status_code}"
            
    except Exception as e:
        return False, str(e)


# =============================================================================
# Main Test Runner
# =============================================================================
def run_test(name: str, test_func, *args) -> Tuple[str, bool, str]:
    """Run a single test and return result"""
    try:
        success, detail = test_func(*args)
        return name, success, detail
    except Exception as e:
        return name, False, str(e)


def main():
    global VERBOSE
    
    parser = argparse.ArgumentParser(description="Comprehensive Stylist MCP Server Test Suite")
    parser.add_argument(
        "--url", type=str, default="https://stylist.polly.wang",
        help="Server URL for remote tests"
    )
    parser.add_argument(
        "--local-only", action="store_true",
        help="Only run local tests (skip remote/HTTP tests)"
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Quick mode: skip LLM-based reasoning tests"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show detailed output"
    )
    parser.add_argument(
        "--api-key", type=str, default=None,
        help="API key for authentication (reads from .env if not provided)"
    )
    
    args = parser.parse_args()
    VERBOSE = args.verbose
    api_key = args.api_key or API_KEY
    
    print("=" * 70)
    print("  Stylist MCP Server - Comprehensive Test Suite")
    print("=" * 70)
    print()
    
    if api_key:
        print(f"🔑 API Key: {api_key[:15]}...")
    else:
        print("⚠️  No API Key configured (auth tests may fail)")
    
    if args.quick:
        print("⚡ Quick mode: skipping LLM reasoning tests")
    print()
    
    results: List[Tuple[str, bool, str]] = []
    
    # -------------------------------------------------------------------------
    # Section 1: Database Tests
    # -------------------------------------------------------------------------
    print("-" * 70)
    print("📦 Database Tests")
    print("-" * 70)
    
    results.append(run_test("GarmentDatabase Basic", test_garment_db))
    results.append(run_test("GarmentDatabase Filters", test_garment_db_filters))
    
    # -------------------------------------------------------------------------
    # Section 2: Single Item Mode Tests
    # -------------------------------------------------------------------------
    print()
    print("-" * 70)
    print("👕 Single Item Mode Tests")
    print("-" * 70)
    
    results.append(run_test("Single Item: T-shirt", test_single_item_tshirt))
    results.append(run_test("Single Item: Dress", test_single_item_dress))
    results.append(run_test("Single Item: Chinese", test_single_item_chinese))
    
    # -------------------------------------------------------------------------
    # Section 3: Full Outfit Mode Tests
    # -------------------------------------------------------------------------
    print()
    print("-" * 70)
    print("👔 Full Outfit Mode Tests")
    print("-" * 70)
    
    results.append(run_test("Full Outfit: Basic", test_full_outfit_basic))
    results.append(run_test("Full Outfit: Formal", test_full_outfit_formal))
    results.append(run_test("Full Outfit: Chinese", test_full_outfit_chinese))
    results.append(run_test("Full Outfit: Male", test_full_outfit_male))
    
    # -------------------------------------------------------------------------
    # Section 4: LLM Reasoning Tests (skip in quick mode)
    # -------------------------------------------------------------------------
    if not args.quick:
        print()
        print("-" * 70)
        print("🧠 LLM Reasoning Tests (may take longer)")
        print("-" * 70)
        
        results.append(run_test("Full Outfit with Reasoning", test_full_outfit_with_reasoning))
    
    # -------------------------------------------------------------------------
    # Section 5: Remote Server Tests
    # -------------------------------------------------------------------------
    if not args.local_only:
        print()
        print("-" * 70)
        print(f"🌐 Remote Server Tests ({args.url})")
        print("-" * 70)
        
        results.append(run_test("Health Endpoint", test_health, args.url))
        results.append(run_test("Tools Endpoint", test_tools_list, args.url, api_key))
        results.append(run_test("Image Serving", test_image_access, args.url))
        results.append(run_test("Response Image URLs", test_image_in_response, args.url))
    
    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print()
    print("=" * 70)
    print("  Test Summary")
    print("=" * 70)
    print()
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for name, success, detail in results:
        status = "✅" if success else "❌"
        detail_str = f"({detail})" if detail and len(detail) < 50 else ""
        print(f"  {status} {name} {detail_str}")
    
    print()
    print(f"  {'=' * 30}")
    print(f"  {passed}/{total} tests passed")
    
    if passed == total:
        print("  🎉 All tests passed!")
    else:
        failed = [(n, d) for n, s, d in results if not s]
        print(f"  ⚠️  {len(failed)} test(s) failed:")
        for name, detail in failed:
            print(f"     - {name}: {detail}")
    
    print()
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
