"""
Build ChromaDB index directly from garment_attributes.jsonl
No need for DressCode dataset directory
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pathlib import Path
import shutil


def main():
    print("=" * 60)
    print("  ChromaDB Index Builder (from JSONL)")
    print("=" * 60)
    print()
    
    # Import after path setup
    from config import CHROMADB_PATH, ATTRIBUTES_FILE
    from garment_db import GarmentDatabase
    
    # Validate JSONL file
    if not ATTRIBUTES_FILE.exists():
        print(f"ERROR: ATTRIBUTES_FILE does not exist: {ATTRIBUTES_FILE}")
        sys.exit(1)
    
    print(f"Source JSONL:   {ATTRIBUTES_FILE}")
    print(f"ChromaDB path:  {CHROMADB_PATH}")
    print()
    
    # Count lines in JSONL
    with open(ATTRIBUTES_FILE) as f:
        total_lines = sum(1 for line in f if line.strip())
    print(f"Total entries in JSONL: {total_lines}")
    print()
    
    # Check for existing database
    if CHROMADB_PATH.exists():
        response = input("ChromaDB already exists. Rebuild? [y/N]: ")
        if response.lower() != 'y':
            print("Aborted.")
            return
        
        shutil.rmtree(CHROMADB_PATH)
        print("Removed existing database.")
    
    # Initialize database
    print("\nBuilding ChromaDB index...")
    db = GarmentDatabase()
    
    # Import from JSONL
    count = db.import_from_jsonl(ATTRIBUTES_FILE)
    
    # Print stats
    total = db.collection.count()
    print()
    print(f"✅ Index built successfully!")
    print(f"   Total garments indexed: {total}")
    
    # Test a simple query
    print()
    print("Testing search...")
    results = db.search("casual summer dress", n_results=3)
    print(f"  Search for 'casual summer dress' returned {len(results)} results")
    if results:
        for i, r in enumerate(results[:3], 1):
            print(f"    {i}. {r['garment_id']} ({r['category']}) - {r.get('garment_type', 'N/A')}")
    
    print()
    print("Done!")


if __name__ == "__main__":
    main()
