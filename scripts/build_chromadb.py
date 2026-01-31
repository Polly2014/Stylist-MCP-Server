"""
Build ChromaDB index from DressCode dataset
Run this script to initialize the garment database
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pathlib import Path
from garment_db import GarmentDatabase
from config import DRESSCODE_ROOT, CHROMADB_PATH


def main():
    print("=" * 60)
    print("  ChromaDB Index Builder")
    print("=" * 60)
    print()
    
    # Validate paths
    if not DRESSCODE_ROOT.exists():
        print(f"ERROR: DRESSCODE_ROOT does not exist: {DRESSCODE_ROOT}")
        print("Please set DRESSCODE_ROOT in your .env file")
        sys.exit(1)
    
    print(f"DressCode root: {DRESSCODE_ROOT}")
    print(f"ChromaDB path:  {CHROMADB_PATH}")
    print()
    
    # Check for existing database
    if CHROMADB_PATH.exists():
        response = input("ChromaDB already exists. Rebuild? [y/N]: ")
        if response.lower() != 'y':
            print("Aborted.")
            return
        
        import shutil
        shutil.rmtree(CHROMADB_PATH)
        print("Removed existing database.")
    
    # Look for JSONL files
    jsonl_files = list(DRESSCODE_ROOT.glob("**/*.jsonl"))
    
    if not jsonl_files:
        print("No JSONL files found in DRESSCODE_ROOT")
        print("Expected format: <category>/attributes.jsonl")
        sys.exit(1)
    
    print(f"Found {len(jsonl_files)} JSONL file(s):")
    for f in jsonl_files:
        print(f"  - {f.relative_to(DRESSCODE_ROOT)}")
    print()
    
    # Initialize database (this loads from JSONL automatically)
    print("Building ChromaDB index...")
    db = GarmentDatabase()
    
    # Print stats
    total = db.collection.count()
    print()
    print(f"Index built successfully!")
    print(f"Total garments indexed: {total}")
    
    # Test a simple query
    print()
    print("Testing search...")
    results = db.search("casual summer dress", n_results=3)
    print(f"Search for 'casual summer dress' returned {len(results)} results")
    if results:
        print(f"  Top result: {results[0]['garment_id']}")
    
    print()
    print("Done!")


if __name__ == "__main__":
    main()
