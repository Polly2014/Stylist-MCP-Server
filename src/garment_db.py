"""
ChromaDB storage and indexing for garment attributes
Supports hybrid search: metadata filtering + semantic similarity
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings

from config import CHROMADB_PATH, ATTRIBUTES_FILE, DRESSCODE_ROOT


class GarmentDatabase:
    """ChromaDB-based garment database with hybrid search"""
    
    def __init__(self, persist_directory: Optional[Path] = None):
        self.persist_directory = persist_directory or CHROMADB_PATH
        self.persist_directory = Path(self.persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB with persistence
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name="dresscode_garments",
            metadata={"description": "DressCode garment attributes for VTON stylist"}
        )
    
    def add_garment(self, garment_data: Dict[str, Any]):
        """Add a single garment to the database"""
        garment_id = garment_data["garment_id"]
        category = garment_data["category"]
        attributes = garment_data.get("attributes", {})
        
        # Create text document for embedding (description + key attributes)
        doc_parts = []
        if attributes.get("description"):
            doc_parts.append(attributes["description"])
        if attributes.get("garment_type"):
            doc_parts.append(f"Type: {attributes['garment_type']}")
        if attributes.get("colors"):
            doc_parts.append(f"Colors: {', '.join(attributes['colors'])}")
        if attributes.get("style"):
            styles = attributes["style"] if isinstance(attributes["style"], list) else [attributes["style"]]
            doc_parts.append(f"Style: {', '.join(styles)}")
        if attributes.get("occasion"):
            occasions = attributes["occasion"] if isinstance(attributes["occasion"], list) else [attributes["occasion"]]
            doc_parts.append(f"Occasion: {', '.join(occasions)}")
        
        document = " | ".join(doc_parts) if doc_parts else f"{category} garment"
        
        # Prepare metadata (ChromaDB only supports str, int, float, bool)
        metadata = {
            "category": category,
            "relative_path": garment_data.get("relative_path", ""),
            "gender": attributes.get("gender", "unknown"),
            "garment_type": attributes.get("garment_type", "unknown"),
            "pattern": attributes.get("pattern", "unknown"),
            "fit": attributes.get("fit", "unknown"),
            "length": attributes.get("length", "unknown"),
            # Convert lists to comma-separated strings
            "colors": ",".join(attributes.get("colors", [])),
            "styles": ",".join(attributes.get("style", []) if isinstance(attributes.get("style"), list) else [attributes.get("style", "")]),
            "seasons": ",".join(attributes.get("season", []) if isinstance(attributes.get("season"), list) else [attributes.get("season", "")]),
            "age_groups": ",".join(attributes.get("age_group", []) if isinstance(attributes.get("age_group"), list) else [attributes.get("age_group", "")]),
            "occasions": ",".join(attributes.get("occasion", []) if isinstance(attributes.get("occasion"), list) else [attributes.get("occasion", "")]),
            "body_types": ",".join(attributes.get("body_type_suitable", []) if isinstance(attributes.get("body_type_suitable"), list) else []),
        }
        
        # Add to collection
        self.collection.upsert(
            ids=[garment_id],
            documents=[document],
            metadatas=[metadata]
        )
    
    def import_from_jsonl(self, jsonl_path: Optional[Path] = None, batch_size: int = 100):
        """Import garments from JSONL file"""
        jsonl_path = jsonl_path or ATTRIBUTES_FILE
        jsonl_path = Path(jsonl_path)
        
        if not jsonl_path.exists():
            raise FileNotFoundError(f"JSONL file not found: {jsonl_path}")
        
        print(f"Importing from {jsonl_path}...")
        
        batch_ids = []
        batch_docs = []
        batch_metadatas = []
        count = 0
        skipped = 0
        
        with open(jsonl_path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                
                try:
                    garment_data = json.loads(line)
                except json.JSONDecodeError:
                    skipped += 1
                    continue
                
                # Skip entries with parse errors
                if garment_data.get("parse_error"):
                    skipped += 1
                    continue
                
                garment_id = garment_data["garment_id"]
                category = garment_data["category"]
                attributes = garment_data.get("attributes", {})
                
                # Create document
                doc_parts = []
                if attributes.get("description"):
                    doc_parts.append(attributes["description"])
                if attributes.get("garment_type"):
                    doc_parts.append(f"Type: {attributes['garment_type']}")
                if attributes.get("colors"):
                    doc_parts.append(f"Colors: {', '.join(attributes['colors'])}")
                if attributes.get("style"):
                    styles = attributes["style"] if isinstance(attributes["style"], list) else [attributes["style"]]
                    doc_parts.append(f"Style: {', '.join(styles)}")
                
                document = " | ".join(doc_parts) if doc_parts else f"{category} garment"
                
                # Prepare metadata
                metadata = {
                    "category": category,
                    "relative_path": garment_data.get("relative_path", ""),
                    "gender": attributes.get("gender", "unknown"),
                    "garment_type": attributes.get("garment_type", "unknown"),
                    "pattern": attributes.get("pattern", "unknown"),
                    "fit": attributes.get("fit", "unknown"),
                    "length": attributes.get("length", "unknown"),
                    "colors": ",".join(attributes.get("colors", [])),
                    "styles": ",".join(attributes.get("style", []) if isinstance(attributes.get("style"), list) else [attributes.get("style", "")]),
                    "seasons": ",".join(attributes.get("season", []) if isinstance(attributes.get("season"), list) else [attributes.get("season", "")]),
                    "age_groups": ",".join(attributes.get("age_group", []) if isinstance(attributes.get("age_group"), list) else [attributes.get("age_group", "")]),
                    "occasions": ",".join(attributes.get("occasion", []) if isinstance(attributes.get("occasion"), list) else [attributes.get("occasion", "")]),
                    "body_types": ",".join(attributes.get("body_type_suitable", []) if isinstance(attributes.get("body_type_suitable"), list) else []),
                }
                
                batch_ids.append(garment_id)
                batch_docs.append(document)
                batch_metadatas.append(metadata)
                count += 1
                
                # Upsert in batches
                if len(batch_ids) >= batch_size:
                    self.collection.upsert(
                        ids=batch_ids,
                        documents=batch_docs,
                        metadatas=batch_metadatas
                    )
                    print(f"  Imported {count} garments...", end="\r")
                    batch_ids = []
                    batch_docs = []
                    batch_metadatas = []
        
        # Final batch
        if batch_ids:
            self.collection.upsert(
                ids=batch_ids,
                documents=batch_docs,
                metadatas=batch_metadatas
            )
        
        print(f"\nImported {count} garments, skipped {skipped}")
        return count
    
    def search(
        self,
        query: str,
        n_results: int = 10,
        category: Optional[str] = None,
        gender: Optional[str] = None,
        garment_type: Optional[str] = None,
        style: Optional[str] = None,
        season: Optional[str] = None,
        occasion: Optional[str] = None,
        body_type: Optional[str] = None,
        color: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search: semantic similarity + metadata filtering
        
        Args:
            query: Natural language search query
            n_results: Number of results to return
            category: Filter by category (dresses, upper_body, lower_body)
            gender: Filter by gender (female, male, unisex)
            garment_type: Filter by specific garment type (t-shirt, jeans, etc.)
            style: Filter by style (contains this style)
            season: Filter by season (contains this season)
            occasion: Filter by occasion (contains this occasion)
            body_type: Filter by body type suitability
            color: Filter by color (contains this color)
        
        Returns:
            List of matching garments with metadata
        """
        # Build where clause for metadata filtering
        where_clauses = []
        
        if category:
            where_clauses.append({"category": category})
        if gender:
            where_clauses.append({"gender": gender})
        if garment_type:
            where_clauses.append({"garment_type": garment_type})
        
        # Combine filters
        where = None
        if len(where_clauses) == 1:
            where = where_clauses[0]
        elif len(where_clauses) > 1:
            where = {"$and": where_clauses}
        
        # Enhance query with filter hints for semantic matching
        enhanced_query = query
        if style:
            enhanced_query += f" {style} style"
        if season:
            enhanced_query += f" {season}"
        if occasion:
            enhanced_query += f" {occasion}"
        if body_type:
            enhanced_query += f" suitable for {body_type} body type"
        if color:
            enhanced_query += f" {color} color"
        
        # Execute search
        results = self.collection.query(
            query_texts=[enhanced_query],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )
        
        # Format results
        formatted = []
        if results["ids"] and results["ids"][0]:
            for i, garment_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                formatted.append({
                    "garment_id": garment_id,
                    "document": results["documents"][0][i] if results["documents"] else "",
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                    "metadata": metadata,
                    "image_path": str(DRESSCODE_ROOT / metadata.get("relative_path", ""))
                })
        
        return formatted

    def search_multi_category(
        self,
        query: str,
        categories: List[str],
        n_results_per_category: int = 5,
        gender: Optional[str] = None,
        style: Optional[str] = None,
        season: Optional[str] = None,
        occasion: Optional[str] = None,
        body_type: Optional[str] = None,
        color: Optional[str] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search multiple categories in parallel for outfit recommendations
        
        Args:
            query: Natural language search query
            categories: List of categories to search (e.g., ["upper_body", "lower_body"])
            n_results_per_category: Number of results per category
            gender, style, season, occasion, body_type, color: Filter parameters
        
        Returns:
            Dict mapping category to list of matching garments
        """
        results = {}
        for category in categories:
            results[category] = self.search(
                query=query,
                n_results=n_results_per_category,
                category=category,
                gender=gender,
                style=style,
                season=season,
                occasion=occasion,
                body_type=body_type,
                color=color,
            )
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        count = self.collection.count()
        
        # Sample some items to get category distribution
        sample = self.collection.get(limit=min(count, 1000), include=["metadatas"])
        
        categories = {}
        genders = {}
        
        if sample["metadatas"]:
            for meta in sample["metadatas"]:
                cat = meta.get("category", "unknown")
                categories[cat] = categories.get(cat, 0) + 1
                
                gen = meta.get("gender", "unknown")
                genders[gen] = genders.get(gen, 0) + 1
        
        return {
            "total_garments": count,
            "categories": categories,
            "genders": genders
        }


def main():
    """CLI for database operations"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Garment Database Operations")
    parser.add_argument("--import", dest="do_import", action="store_true", help="Import from JSONL")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--search", type=str, help="Search query")
    parser.add_argument("--category", type=str, help="Filter by category")
    parser.add_argument("--style", type=str, help="Filter by style")
    parser.add_argument("--color", type=str, help="Filter by color")
    parser.add_argument("-n", type=int, default=5, help="Number of results")
    
    args = parser.parse_args()
    
    db = GarmentDatabase()
    
    if args.do_import:
        db.import_from_jsonl()
    
    if args.stats:
        stats = db.get_stats()
        print(f"\nDatabase Statistics:")
        print(f"  Total garments: {stats['total_garments']}")
        print(f"  Categories: {stats['categories']}")
        print(f"  Genders: {stats['genders']}")
    
    if args.search:
        print(f"\nSearching for: '{args.search}'")
        results = db.search(
            query=args.search,
            n_results=args.n,
            category=args.category,
            style=args.style,
            color=args.color
        )
        
        for i, r in enumerate(results, 1):
            print(f"\n{i}. {r['garment_id']} (distance: {r['distance']:.3f})")
            print(f"   {r['document'][:100]}...")
            print(f"   Category: {r['metadata'].get('category')}")
            print(f"   Colors: {r['metadata'].get('colors')}")
            print(f"   Style: {r['metadata'].get('styles')}")


if __name__ == "__main__":
    main()
