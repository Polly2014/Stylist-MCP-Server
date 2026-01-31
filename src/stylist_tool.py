"""
Stylist Search Tool - MCP Tool for garment recommendation
Integrates with Agent systems for natural language fashion queries
"""
import json
import requests
from typing import Dict, Any, List, Optional
from pathlib import Path

from config import ANTHROPIC_API_ENDPOINT, MODEL_NAME, DRESSCODE_ROOT, ATTRIBUTE_SCHEMA
from garment_db import GarmentDatabase


# Intent parsing prompt for Claude
INTENT_PARSE_PROMPT = """You are a fashion stylist assistant. Parse the user's clothing request into structured search parameters.

User query: "{query}"

Extract the following parameters (return null if not specified or not applicable):

1. LANGUAGE & MODE DETECTION:
   - language: "zh" | "en" (detect from user's query language)
   - recommendation_mode: "single_item" | "full_outfit"
     * "single_item": user wants specific garment types (e.g., "推荐T恤", "show me some dresses")
     * "full_outfit": user wants complete outfits/穿搭 (e.g., "推荐3套穿搭", "recommend outfits for date")
   - count: number of items/outfits to recommend (default: 3 for full_outfit, 5 for single_item)

2. GARMENT FILTERS:
   - garment_type: specific garment type if mentioned, one of ["dress", "top", "blouse", "shirt", "t-shirt", "sweater", "jacket", "coat", "pants", "jeans", "shorts", "skirt", "jumpsuit", "romper"] or null
   - category: "dresses" | "upper_body" | "lower_body" | null
     * If garment_type is specified, infer category automatically:
       - dress/jumpsuit/romper → "dresses"
       - top/blouse/shirt/t-shirt/sweater/jacket/coat → "upper_body"
       - pants/jeans/shorts/skirt → "lower_body"
     * If full_outfit mode and no specific type, leave as null

3. STYLE ATTRIBUTES:
   - gender: "female" | "male" | "unisex" | null
   - style: one of ["classic", "boho", "minimalist", "preppy", "casual", "street_style", "sporty_chic", "grunge", "romantic", "edgy", "vintage", "elegant"] or null
   - season: one of ["spring", "summer", "fall", "winter", "all_season"] or null
   - occasion: one of ["casual", "work", "formal", "party", "date", "vacation", "athletic", "everyday"] or null
   - body_type: one of ["rectangle", "triangle", "inverted_triangle", "oval", "trapezoid", "hourglass", "pear", "apple", "athletic"] or null
   - color: primary color mentioned or null

4. SEMANTIC QUERY:
   - semantic_query: a refined search query describing the desired garment/outfit style (always provide this)

Return ONLY a JSON object with these fields."""


class StylistSearchTool:
    """
    Fashion recommendation tool that combines:
    1. Intent parsing (using Claude via Agent Maestro)
    2. Hybrid search (ChromaDB metadata + semantic)
    3. Garment recommendation with reasoning
    """
    
    def __init__(self, db: Optional[GarmentDatabase] = None):
        self.db = db or GarmentDatabase()
    
    def _parse_intent(self, query: str) -> Dict[str, Any]:
        """Use Claude to parse natural language query into search parameters"""
        
        prompt = INTENT_PARSE_PROMPT.format(query=query)
        
        payload = {
            "model": MODEL_NAME,
            "max_tokens": 512,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        try:
            response = requests.post(
                ANTHROPIC_API_ENDPOINT,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                timeout=30
            )
            
            if response.status_code != 200:
                return {"semantic_query": query}  # Fallback to raw query
            
            result = response.json()
            text = result["content"][0]["text"]
            
            # Parse JSON from response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            return json.loads(text.strip())
            
        except Exception as e:
            print(f"Intent parsing failed: {e}")
            return {"semantic_query": query}
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        parse_intent: bool = True,
        **override_filters
    ) -> Dict[str, Any]:
        """
        Main search function for the stylist tool (single item mode)
        
        Args:
            query: Natural language search query
            n_results: Number of results to return
            parse_intent: Whether to use LLM to parse intent (set False for direct search)
            **override_filters: Manual filter overrides (category, gender, style, etc.)
        
        Returns:
            Dict with parsed_intent, results, and recommendations
        """
        
        # Step 1: Parse intent
        if parse_intent:
            intent = self._parse_intent(query)
        else:
            intent = {"semantic_query": query}
        
        # Apply overrides
        intent.update(override_filters)
        
        # Step 2: Execute search
        search_query = intent.get("semantic_query", query)
        
        results = self.db.search(
            query=search_query,
            n_results=n_results,
            category=intent.get("category"),
            gender=intent.get("gender"),
            garment_type=intent.get("garment_type"),
            style=intent.get("style"),
            season=intent.get("season"),
            occasion=intent.get("occasion"),
            body_type=intent.get("body_type"),
            color=intent.get("color"),
        )
        
        # Step 3: Format output
        recommendations = []
        for r in results:
            rec = self._format_garment(r)
            recommendations.append(rec)
        
        return {
            "query": query,
            "parsed_intent": intent,
            "num_results": len(recommendations),
            "recommendations": recommendations
        }

    def _format_garment(self, r: Dict[str, Any]) -> Dict[str, Any]:
        """Format a single garment result"""
        return {
            "garment_id": r["garment_id"],
            "description": r["document"],
            "similarity_score": 1 - r["distance"],
            "category": r["metadata"].get("category"),
            "garment_type": r["metadata"].get("garment_type"),
            "colors": r["metadata"].get("colors", "").split(","),
            "styles": r["metadata"].get("styles", "").split(","),
            "occasions": r["metadata"].get("occasions", "").split(","),
            "image_path": r["image_path"],
        }

    def _generate_outfit_combinations(
        self,
        multi_results: Dict[str, List[Dict[str, Any]]],
        gender: Optional[str],
        max_combos: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Generate outfit combinations from multi-category search results
        Each garment appears in at most ONE outfit to ensure variety.
        
        Args:
            multi_results: Dict mapping category to list of garments
            gender: User gender for deciding outfit types
            max_combos: Maximum number of combinations to generate
        
        Returns:
            List of outfit candidates, each with 'type' and garment(s)
        """
        combos = []
        used_garment_ids = set()  # Track used garments to avoid duplicates
        
        # Get garments by category
        tops = multi_results.get("upper_body", [])
        bottoms = multi_results.get("lower_body", [])
        dresses = multi_results.get("dresses", [])
        
        # Generate top + bottom combinations (no duplicate garments)
        # Each top and bottom can only be used once
        for top in tops:
            top_id = top["garment_id"]
            if top_id in used_garment_ids:
                continue
            
            # Find an unused bottom for this top
            for bottom in bottoms:
                bottom_id = bottom["garment_id"]
                if bottom_id in used_garment_ids:
                    continue
                
                # Found a valid pairing
                combos.append({
                    "type": "two_piece",
                    "top": self._format_garment(top),
                    "bottom": self._format_garment(bottom),
                })
                used_garment_ids.add(top_id)
                used_garment_ids.add(bottom_id)
                break  # Move to next top after finding one valid bottom
            
            if len(combos) >= max_combos:
                break
        
        # Add dress options for female users (no duplicates)
        if gender != "male" and dresses:
            for dress in dresses:
                dress_id = dress["garment_id"]
                if dress_id in used_garment_ids:
                    continue
                
                combos.append({
                    "type": "dress",
                    "dress": self._format_garment(dress),
                })
                used_garment_ids.add(dress_id)
                
                if len(combos) >= max_combos:
                    break
        
        return combos[:max_combos]

    def _evaluate_outfits_batch(
        self,
        combinations: List[Dict[str, Any]],
        query: str,
        language: str = "en"
    ) -> List[Dict[str, Any]]:
        """
        Evaluate all outfit combinations in a single LLM call
        
        Args:
            combinations: List of outfit candidates
            query: Original user query for context
            language: Response language ("zh" or "en")
        
        Returns:
            Combinations with score and reason added, sorted by score
        """
        if not combinations:
            return []
        
        # Build description for each combination
        combo_descriptions = []
        for i, combo in enumerate(combinations):
            if combo["type"] == "two_piece":
                desc = f"Combo {i}: Top [{combo['top']['garment_id']}]: {combo['top']['description'][:80]}... + Bottom [{combo['bottom']['garment_id']}]: {combo['bottom']['description'][:80]}..."
            else:
                desc = f"Combo {i}: Dress [{combo['dress']['garment_id']}]: {combo['dress']['description'][:100]}..."
            combo_descriptions.append(desc)
        
        lang_instruction = "回复请使用中文。" if language == "zh" else "Respond in English."
        
        eval_prompt = f"""You are a fashion stylist evaluating outfit combinations for this request: "{query}"

Here are the outfit candidates:
{chr(10).join(combo_descriptions)}

For EACH combination, evaluate how well it matches the user's request considering:
- Style coherence between pieces
- Color coordination
- Occasion appropriateness
- Overall aesthetic appeal

{lang_instruction}

Return a JSON array with one object per combo:
[
  {{"combo_id": 0, "score": 0.85, "reason": "Brief explanation why this works or doesn't..."}},
  ...
]

Score from 0.0 (poor match) to 1.0 (perfect match). Return ONLY the JSON array."""

        try:
            response = requests.post(
                ANTHROPIC_API_ENDPOINT,
                json={
                    "model": MODEL_NAME,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": eval_prompt}]
                },
                headers={
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result["content"][0]["text"]
                
                # Parse JSON from response
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                
                evaluations = json.loads(text.strip())
                
                # Merge evaluations into combinations
                eval_map = {e["combo_id"]: e for e in evaluations}
                for i, combo in enumerate(combinations):
                    if i in eval_map:
                        combo["score"] = eval_map[i].get("score", 0.5)
                        combo["reason"] = eval_map[i].get("reason", "")
                    else:
                        combo["score"] = 0.5
                        combo["reason"] = ""
                
                # Sort by score descending
                combinations.sort(key=lambda x: x.get("score", 0), reverse=True)
                
        except Exception as e:
            print(f"Outfit evaluation failed: {e}")
            # Assign default scores
            for combo in combinations:
                combo["score"] = 0.5
                combo["reason"] = ""
        
        return combinations

    def _generate_stylist_advice(
        self,
        outfits: List[Dict[str, Any]],
        query: str,
        language: str = "en"
    ) -> str:
        """Generate final stylist advice based on selected outfits"""
        if not outfits:
            return ""
        
        lang_instruction = "回复请使用中文，简洁专业。" if language == "zh" else "Respond in English, brief and professional."
        
        outfit_summary = []
        for i, outfit in enumerate(outfits[:3], 1):
            if outfit["type"] == "two_piece":
                outfit_summary.append(f"{i}. {outfit['top']['description'][:50]}... + {outfit['bottom']['description'][:50]}...")
            else:
                outfit_summary.append(f"{i}. {outfit['dress']['description'][:80]}...")
        
        advice_prompt = f"""Based on the user's request: "{query}"

I've selected these outfits:
{chr(10).join(outfit_summary)}

{lang_instruction}
Provide a brief (2-3 sentences) overall styling recommendation explaining why these outfit selections suit the user's needs."""

        try:
            response = requests.post(
                ANTHROPIC_API_ENDPOINT,
                json={
                    "model": MODEL_NAME,
                    "max_tokens": 256,
                    "messages": [{"role": "user", "content": advice_prompt}]
                },
                headers={
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["content"][0]["text"]
        except Exception as e:
            print(f"Stylist advice generation failed: {e}")
        
        return ""

    def recommend_outfit(
        self,
        query: str,
        include_reasoning: bool = True
    ) -> Dict[str, Any]:
        """
        Unified outfit recommendation entry point
        
        Automatically detects whether user wants:
        - Single items (e.g., "recommend T-shirts") -> returns recommendations list
        - Full outfits (e.g., "recommend 3 outfits") -> returns outfits list with coordination
        
        Args:
            query: User's fashion request
            include_reasoning: Whether to include AI explanation
        
        Returns:
            Dict with recommendations or outfits based on detected mode
        """
        
        # Step 1: Parse intent to determine mode
        intent = self._parse_intent(query)
        mode = intent.get("recommendation_mode", "full_outfit")
        language = intent.get("language", "en")
        count = intent.get("count", 3)  # Default to 3 for both modes
        gender = intent.get("gender")
        
        # Step 2: Branch based on mode
        if mode == "single_item":
            return self._recommend_single_items(query, intent, count, language, include_reasoning)
        else:
            return self._recommend_full_outfits(query, intent, count, language, gender, include_reasoning)

    def _recommend_single_items(
        self,
        query: str,
        intent: Dict[str, Any],
        count: int,
        language: str,
        include_reasoning: bool
    ) -> Dict[str, Any]:
        """Handle single item recommendations (T-shirts, dresses, etc.)"""
        
        search_query = intent.get("semantic_query", query)
        
        results = self.db.search(
            query=search_query,
            n_results=count,
            category=intent.get("category"),
            gender=intent.get("gender"),
            garment_type=intent.get("garment_type"),
            style=intent.get("style"),
            season=intent.get("season"),
            occasion=intent.get("occasion"),
            body_type=intent.get("body_type"),
            color=intent.get("color"),
        )
        
        recommendations = [self._format_garment(r) for r in results]
        
        result = {
            "query": query,
            "mode": "single_item",
            "parsed_intent": intent,
            "num_results": len(recommendations),
            "recommendations": recommendations
        }
        
        if include_reasoning and recommendations:
            lang_instruction = "回复请使用中文。" if language == "zh" else "Respond in English."
            recommendations_text = "\n".join([
                f"- {r['garment_id']}: {r['description'][:100]}..." 
                for r in recommendations
            ])
            
            reasoning_prompt = f"""Based on the user's request: "{query}"

I found these garment options:
{recommendations_text}

{lang_instruction}
Provide a brief (2-3 sentences) styling recommendation explaining why these choices suit the user's needs."""

            try:
                response = requests.post(
                    ANTHROPIC_API_ENDPOINT,
                    json={
                        "model": MODEL_NAME,
                        "max_tokens": 256,
                        "messages": [{"role": "user", "content": reasoning_prompt}]
                    },
                    headers={
                        "Content-Type": "application/json",
                        "anthropic-version": "2023-06-01"
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    reasoning = response.json()["content"][0]["text"]
                    result["stylist_advice"] = reasoning
            except Exception as e:
                result["stylist_advice"] = f"(Reasoning unavailable: {e})"
        
        return result

    def _recommend_full_outfits(
        self,
        query: str,
        intent: Dict[str, Any],
        count: int,
        language: str,
        gender: Optional[str],
        include_reasoning: bool
    ) -> Dict[str, Any]:
        """Handle full outfit recommendations (top+bottom or dress)"""
        
        search_query = intent.get("semantic_query", query)
        
        # Determine categories to search based on gender
        if gender == "male":
            categories = ["upper_body", "lower_body"]
        else:
            # Female or unspecified: include dresses
            categories = ["upper_body", "lower_body", "dresses"]
        
        # Search multiple categories
        multi_results = self.db.search_multi_category(
            query=search_query,
            categories=categories,
            n_results_per_category=5,
            gender=gender,
            style=intent.get("style"),
            season=intent.get("season"),
            occasion=intent.get("occasion"),
            body_type=intent.get("body_type"),
            color=intent.get("color"),
        )
        
        # Generate outfit combinations
        combinations = self._generate_outfit_combinations(multi_results, gender, max_combos=15)
        
        if not combinations:
            return {
                "query": query,
                "mode": "full_outfit",
                "parsed_intent": intent,
                "num_outfits": 0,
                "outfits": [],
                "stylist_advice": "No matching outfits found."
            }
        
        # Evaluate and rank combinations
        if include_reasoning:
            evaluated = self._evaluate_outfits_batch(combinations, query, language)
        else:
            evaluated = combinations
            for combo in evaluated:
                combo["score"] = 0.5
                combo["reason"] = ""
        
        # Select top N outfits
        selected_outfits = evaluated[:count]
        
        result = {
            "query": query,
            "mode": "full_outfit",
            "parsed_intent": intent,
            "num_outfits": len(selected_outfits),
            "outfits": selected_outfits
        }
        
        # Generate overall stylist advice
        if include_reasoning:
            result["stylist_advice"] = self._generate_stylist_advice(selected_outfits, query, language)
        
        return result


# MCP Tool Schema (for integration with MCP servers)
TOOL_SCHEMA = {
    "name": "stylist_recommend",
    "description": """Fashion recommendation tool that intelligently interprets user queries to provide either:
- Single items (when user asks for specific garment types like "T-shirts", "dresses", "jeans")
- Full outfits (when user asks for complete looks like "outfit for date", "穿搭推荐")

Supports natural language queries in both English and Chinese. Automatically detects user intent and returns coordinated outfit combinations with style reasoning.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language fashion request. Examples: '推荐3套约会穿搭', 'casual summer outfits', 'recommend some T-shirts for work'"
            },
            "include_reasoning": {
                "type": "boolean",
                "description": "Whether to include AI stylist advice and outfit coordination reasoning",
                "default": True
            }
        },
        "required": ["query"]
    }
}


def main():
    """Test the stylist search tool"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Stylist Search Tool")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("-n", type=int, default=5, help="Number of results")
    parser.add_argument("--no-parse", action="store_true", help="Skip intent parsing")
    parser.add_argument("--no-reasoning", action="store_true", help="Skip AI reasoning")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    if not args.query:
        # Interactive mode
        print("Stylist Search Tool - Interactive Mode")
        print("Type your fashion query (or 'quit' to exit):\n")
        
        tool = StylistSearchTool()
        
        while True:
            query = input("You: ").strip()
            if query.lower() in ["quit", "exit", "q"]:
                break
            if not query:
                continue
            
            print("\nSearching...\n")
            results = tool.recommend_outfit(query, include_reasoning=True)
            
            # Handle both single_item and full_outfit modes
            mode = results.get("mode", "single_item")
            
            if mode == "full_outfit":
                print(f"Found {results.get('num_outfits', 0)} outfit combinations:\n")
                
                for i, outfit in enumerate(results.get("outfits", []), 1):
                    if outfit["type"] == "two_piece":
                        print(f"{i}. 👕 Top: [{outfit['top']['garment_id']}]")
                        print(f"      {outfit['top']['description'][:60]}...")
                        print(f"   👖 Bottom: [{outfit['bottom']['garment_id']}]")
                        print(f"      {outfit['bottom']['description'][:60]}...")
                    else:
                        print(f"{i}. 👗 Dress: [{outfit['dress']['garment_id']}]")
                        print(f"      {outfit['dress']['description'][:80]}...")
                    
                    print(f"   ⭐ Score: {outfit.get('score', 0):.2f}")
                    if outfit.get("reason"):
                        print(f"   💬 {outfit['reason'][:80]}...")
                    print()
            else:
                print(f"Found {results.get('num_results', 0)} recommendations:\n")
                
                for i, rec in enumerate(results.get("recommendations", []), 1):
                    print(f"{i}. [{rec['garment_id']}] (score: {rec.get('similarity_score', 0):.2f})")
                    print(f"   {rec['description'][:80]}...")
                    print(f"   Category: {rec['category']} | Colors: {', '.join(rec.get('colors', [])[:3])}")
                    print()
            
            if results.get("stylist_advice"):
                print(f"💡 Stylist Advice:\n{results['stylist_advice']}\n")
            
            print("-" * 50)
    else:
        tool = StylistSearchTool()
        results = tool.recommend_outfit(
            args.query,
            include_reasoning=not args.no_reasoning
        )
        
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            mode = results.get("mode", "single_item")
            print(f"\nQuery: {args.query}")
            print(f"Mode: {mode}")
            print(f"Parsed Intent: {results.get('parsed_intent', {})}\n")
            
            if mode == "full_outfit":
                print(f"Outfits ({results.get('num_outfits', 0)}):\n")
                for i, outfit in enumerate(results.get("outfits", []), 1):
                    if outfit["type"] == "two_piece":
                        print(f"{i}. Top: {outfit['top']['garment_id']} + Bottom: {outfit['bottom']['garment_id']}")
                        print(f"   Score: {outfit.get('score', 0):.2f}")
                        print(f"   Reason: {outfit.get('reason', '')}")
                    else:
                        print(f"{i}. Dress: {outfit['dress']['garment_id']}")
                        print(f"   Score: {outfit.get('score', 0):.2f}")
                        print(f"   Reason: {outfit.get('reason', '')}")
                    print()
            else:
                print(f"Recommendations ({results.get('num_results', 0)}):\n")
                for i, rec in enumerate(results.get("recommendations", []), 1):
                    print(f"{i}. [{rec['garment_id']}] (score: {rec.get('similarity_score', 0):.2f})")
                    print(f"   {rec['description']}")
                    print(f"   Image: {rec.get('image_path', '')}")
                    print()
            
            if results.get("stylist_advice"):
                print(f"💡 Stylist Advice:\n{results['stylist_advice']}")


if __name__ == "__main__":
    main()
