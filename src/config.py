"""
Configuration for Stylist MCP Server
Supports environment variable overrides for deployment flexibility
"""
import os
from pathlib import Path

# Load .env file if it exists
def _load_dotenv():
    """Load environment variables from .env file"""
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    if key not in os.environ:  # Don't override existing env vars
                        os.environ[key] = value

_load_dotenv()

# =============================================================================
# Data Paths (configurable via environment variables)
# =============================================================================

# DressCode dataset root
DRESSCODE_ROOT = Path(os.getenv("DRESSCODE_ROOT", "/data/DressCode"))

# ChromaDB persistence directory
CHROMADB_PATH = Path(os.getenv("CHROMADB_PATH", str(Path(__file__).parent.parent / "data" / "chromadb")))

# Garment attributes JSONL file
ATTRIBUTES_FILE = Path(os.getenv("ATTRIBUTES_FILE", str(Path(__file__).parent.parent / "data" / "garment_attributes.jsonl")))

# Output directory
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(Path(__file__).parent.parent / "output")))

# DressCode categories
CATEGORIES = ["dresses", "lower_body", "upper_body"]

# =============================================================================
# LLM API Configuration
# =============================================================================

# LLM Provider: 'anthropic' (Agent Maestro), 'azure_openai', or 'openai'
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")

# Anthropic / Agent Maestro Configuration
LLM_API_ENDPOINT = os.getenv("LLM_API_ENDPOINT", "http://localhost:23333/api/anthropic/v1/messages")
MODEL_NAME = os.getenv("MODEL_NAME", "claude-3-5-haiku-20241022")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", None)

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

# OpenAI Configuration (for direct OpenAI API)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Legacy alias for compatibility
ANTHROPIC_API_ENDPOINT = LLM_API_ENDPOINT
AGENT_MAESTRO_BASE_URL = os.getenv("AGENT_MAESTRO_BASE_URL", "http://localhost:23333")

# =============================================================================
# MCP Server Configuration
# =============================================================================

MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8888"))
MCP_EXTERNAL_HOST = os.getenv("MCP_EXTERNAL_HOST", None)  # External IP/hostname for image URLs
MCP_USE_SSL = os.getenv("MCP_USE_SSL", "false").lower() in ("true", "1", "yes")  # Use HTTPS for image URLs

# API Key for authentication (optional, leave empty to disable)
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
MCP_API_KEY = os.getenv("MCP_API_KEY", None)
MCP_API_KEY_ENABLED = MCP_API_KEY is not None and len(MCP_API_KEY) > 0

# =============================================================================
# Attribute Schema (for garment classification)
# =============================================================================

ATTRIBUTE_SCHEMA = {
    "gender": ["female", "male", "unisex"],
    "garment_type": [
        "dress", "top", "blouse", "shirt", "t-shirt", "sweater", "jacket", "coat",
        "pants", "jeans", "shorts", "skirt", "jumpsuit", "romper"
    ],
    "colors": [
        "black", "white", "gray", "navy", "blue", "red", "pink", "purple",
        "green", "yellow", "orange", "brown", "beige", "cream", "gold", "silver", "multicolor"
    ],
    "pattern": [
        "solid", "striped", "plaid", "floral", "polka_dot", "animal_print",
        "geometric", "abstract", "tie_dye", "camouflage", "paisley"
    ],
    "style": [
        "classic", "boho", "minimalist", "preppy", "casual", "street_style",
        "sporty_chic", "grunge", "romantic", "edgy", "vintage", "elegant"
    ],
    "occasion": [
        "casual", "work", "formal", "party", "date", "vacation", "athletic", "everyday"
    ],
    "body_type_suitable": [
        "rectangle", "triangle", "inverted_triangle", "oval", "trapezoid",
        "hourglass", "pear", "apple", "athletic"
    ],
    "season": ["spring", "summer", "fall", "winter", "all_season"],
    "fit": ["fitted", "regular", "loose", "oversized"],
    "length": ["mini", "knee", "midi", "maxi", "cropped", "full_length"],
    "age_group": ["teen", "young_adult", "adult", "mature"]
}
