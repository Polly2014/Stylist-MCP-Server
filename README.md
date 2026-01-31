# Stylist MCP Server

An AI-powered fashion recommendation MCP (Model Context Protocol) server that provides intelligent outfit suggestions using ChromaDB for semantic search and Claude for natural language understanding.

## Features

- 🎨 **Intelligent Outfit Recommendations**: Single items or complete outfit combinations
- 🌐 **Dual Transport Modes**: 
  - `stdio` for local Claude Desktop / Cursor integration
  - `SSE` for remote HTTP access (cross-VM, Semantic Kernel)
- 🔍 **Hybrid Search**: Combines metadata filtering with semantic vector search
- 🌍 **Multilingual**: Supports English and Chinese queries
- 🧥 **Full Outfit Coordination**: Top + bottom combinations or dresses with style reasoning
- 🔐 **API Key Authentication**: Secure remote access with configurable API keys
- 🖼️ **Image URLs**: Direct HTTPS links to garment images

## Quick Start

### 1. Setup

```bash
# Clone and setup
git clone https://github.com/Polly2014/Stylist-MCP-Server.git
cd Stylist-MCP-Server
chmod +x setup.sh
./setup.sh

# Edit configuration
cp .env.example .env
nano .env  # Configure DRESSCODE_ROOT, CHROMADB_PATH, etc.
```

### 2. Build Index

```bash
source venv/bin/activate
python scripts/build_chromadb.py
```

### 3. Run Server

```bash
# stdio mode (for Claude Desktop)
python src/mcp_server.py

# SSE mode (for remote access)
python src/mcp_server.py --sse --port 8888
```

## Configuration

Environment variables (set in `.env`):

### Data & Server

| Variable | Description | Default |
|----------|-------------|---------|
| `DRESSCODE_ROOT` | Path to DressCode dataset | Required |
| `CHROMADB_PATH` | Path to ChromaDB persistence | Required |
| `MCP_HOST` | SSE server host | `0.0.0.0` |
| `MCP_PORT` | SSE server port | `8888` |
| `MCP_EXTERNAL_HOST` | External hostname for image URLs | `localhost` |
| `MCP_USE_SSL` | Enable HTTPS for image URLs | `false` |
| `MCP_API_KEY` | API key for authentication | (empty = disabled) |

### LLM Provider

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | Provider: `anthropic`, `azure_openai`, `openai` | `anthropic` |

**Anthropic (Agent Maestro)** - Development mode:
| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_API_ENDPOINT` | Agent Maestro or Anthropic API endpoint | `http://localhost:23333/api/anthropic/v1/messages` |
| `MODEL_NAME` | Claude model name | `claude-3-5-haiku-20241022` |

**Azure OpenAI** - Production mode:
| Variable | Description | Default |
|----------|-------------|---------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | Required |
| `AZURE_OPENAI_API_KEY` | Azure API key | Required |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment name | `gpt-4o-mini` |
| `AZURE_OPENAI_API_VERSION` | API version | `2024-08-01-preview` |

## Available Tools

### `stylist_recommend`

Fashion recommendation tool that intelligently interprets user queries.

**Input:**
```json
{
  "query": "recommend 3 casual outfits for a date",
  "include_reasoning": true,
  "include_image_urls": true
}
```

**Output modes:**
- `single_item`: Returns list of individual garments (e.g., "推荐T恤", "show me dresses")
- `full_outfit`: Returns coordinated outfit combinations (e.g., "推荐3套穿搭", "outfit for date")

**Example Response (single_item mode):**
```json
{
  "query": "recommend 5 casual T-shirts for summer",
  "mode": "single_item",
  "parsed_intent": {
    "language": "en",
    "recommendation_mode": "single_item",
    "count": 5,
    "garment_type": "t-shirt",
    "category": "upper_body",
    "style": "casual",
    "season": "summer"
  },
  "num_results": 5,
  "recommendations": [
    {
      "garment_id": "003841",
      "description": "White cotton t-shirt with round neck, short sleeves, relaxed fit",
      "similarity_score": 0.87,
      "category": "upper_body",
      "garment_type": "t-shirt",
      "colors": ["white"],
      "styles": ["casual", "minimalist"],
      "occasions": ["everyday", "casual"],
      "image_url": "https://stylist.polly.wang/images/upper_body/images/003841_1.jpg"
    },
    {
      "garment_id": "003925",
      "description": "Light blue linen t-shirt, breathable fabric, classic cut",
      "similarity_score": 0.82,
      "category": "upper_body",
      "garment_type": "t-shirt",
      "colors": ["blue"],
      "styles": ["casual"],
      "occasions": ["everyday", "vacation"],
      "image_url": "https://stylist.polly.wang/images/upper_body/images/003925_1.jpg"
    }
    // ... more items
  ],
  "stylist_advice": "These lightweight cotton and linen t-shirts are perfect for summer..."
}
```

**Example Response (full_outfit mode):**
```json
{
  "query": "推荐3套约会穿搭",
  "mode": "full_outfit",
  "parsed_intent": {
    "language": "zh",
    "recommendation_mode": "full_outfit",
    "count": 3,
    "occasion": "date",
    "style": "elegant"
  },
  "num_outfits": 3,
  "outfits": [
    {
      "type": "two_piece",
      "top": {
        "garment_id": "005123",
        "description": "Soft pink silk blouse with subtle ruffle details",
        "similarity_score": 0.85,
        "category": "upper_body",
        "garment_type": "blouse",
        "colors": ["pink"],
        "styles": ["romantic", "elegant"],
        "occasions": ["date", "party"],
        "image_url": "https://stylist.polly.wang/images/upper_body/images/005123_1.jpg"
      },
      "bottom": {
        "garment_id": "012456",
        "description": "High-waisted black pencil skirt, knee length",
        "similarity_score": 0.83,
        "category": "lower_body",
        "garment_type": "skirt",
        "colors": ["black"],
        "styles": ["classic", "elegant"],
        "occasions": ["work", "date"],
        "image_url": "https://stylist.polly.wang/images/lower_body/images/012456_1.jpg"
      },
      "score": 0.90,
      "reason": "The soft pink blouse pairs beautifully with the classic black skirt, creating a romantic yet sophisticated look perfect for a date."
    },
    {
      "type": "dress",
      "dress": {
        "garment_id": "020714",
        "description": "Elegant navy blue A-line dress with V-neck, midi length",
        "similarity_score": 0.88,
        "category": "dresses",
        "garment_type": "dress",
        "colors": ["navy", "blue"],
        "styles": ["elegant", "classic"],
        "occasions": ["date", "party", "formal"],
        "image_url": "https://stylist.polly.wang/images/dresses/images/020714_1.jpg"
      },
      "score": 0.88,
      "reason": "This navy A-line dress is timeless and flattering, ideal for a romantic dinner date."
    }
    // ... more outfits
  ],
  "stylist_advice": "这些穿搭都非常适合约会场合。粉色丝质上衣搭配黑色铅笔裙展现优雅气质，而海军蓝连衣裙则是经典之选，适合各种约会场景。"
}
```

## Client Integration

### Claude Desktop (Local stdio)

Add to `~/.config/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "stylist-recommender": {
      "command": "python",
      "args": ["/path/to/Stylist-MCP-Server/src/mcp_server.py"],
      "env": {
        "DRESSCODE_ROOT": "/path/to/DressCode",
        "CHROMADB_PATH": "/path/to/chroma_db",
        "LLM_API_ENDPOINT": "http://localhost:23333/api/anthropic/v1/messages"
      }
    }
  }
}
```

### Claude Desktop (Remote SSE)

```json
{
  "mcpServers": {
    "stylist-remote": {
      "command": "npx",
      "args": [
        "-y", "@anthropic-ai/mcp-remote@latest",
        "--transport", "sse-only",
        "https://stylist.polly.wang/sse?apiKey=YOUR_API_KEY"
      ]
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "stylist": {
      "url": "https://stylist.polly.wang/sse?apiKey=YOUR_API_KEY"
    }
  }
}
```

### Python Client (SSE)

```python
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    url = "https://stylist.polly.wang/sse?apiKey=YOUR_API_KEY"
    
    async with sse_client(url) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            
            result = await session.call_tool(
                "stylist_recommend",
                {"query": "推荐3套约会穿搭", "include_reasoning": True}
            )
            print(result)
```

## SSE Mode Endpoints

| Endpoint | Auth | Description |
|----------|------|-------------|
| `/health` | ❌ | Health check |
| `/sse` | ✅ | SSE connection for MCP |
| `/messages/` | ✅ | MCP message handling |
| `/tools` | ✅ | List available tools |
| `/images/*` | ❌ | Static image serving |

**Authentication Methods:**
- Query parameter: `?apiKey=YOUR_KEY`
- Header: `X-API-Key: YOUR_KEY`
- Bearer token: `Authorization: Bearer YOUR_KEY`

## Project Structure

```
Stylist-MCP-Server/
├── src/
│   ├── config.py          # Configuration (env vars)
│   ├── garment_db.py      # ChromaDB wrapper
│   ├── stylist_tool.py    # Recommendation logic (single_item + full_outfit)
│   └── mcp_server.py      # MCP server (stdio + SSE + auth)
├── scripts/
│   ├── build_chromadb.py  # Index builder
│   ├── build_from_jsonl.py # Build from attributes JSONL
│   └── test_mcp.py        # Comprehensive test suite
├── config/
│   ├── claude_desktop.json           # Local stdio config
│   ├── claude_desktop_remote.example.json  # Remote SSE config
│   ├── cursor_mcp.example.json       # Cursor config
│   └── python_client_example.py      # Python client example
├── data/
│   ├── garment_attributes.jsonl      # Garment metadata
│   └── chroma_db/                    # Vector database
├── requirements.txt
├── setup.sh
├── .env.example
└── README.md
```

## Testing

```bash
# Quick test (skip LLM reasoning)
python scripts/test_mcp.py --quick

# Full test with LLM reasoning
python scripts/test_mcp.py

# Verbose output
python scripts/test_mcp.py --verbose

# Local only (no remote server tests)
python scripts/test_mcp.py --local-only

# Custom LLM endpoint
LLM_API_ENDPOINT=http://localhost:23335/api/anthropic/v1/messages python scripts/test_mcp.py
```

**Test Coverage:**
- 📦 Database: Basic search, filters, multi-category
- 👕 Single Item: T-shirt, dress, Chinese queries
- 👔 Full Outfit: Basic, formal, Chinese, male (no dresses)
- 🧠 LLM Reasoning: Scoring, reasons, stylist advice
- 🌐 Remote: Health, tools, images, URL accessibility

## Deployment

### With Nginx (Recommended)

1. Run MCP Server on internal port:
   ```bash
   python src/mcp_server.py --sse --port 8888
   ```

2. Configure Nginx reverse proxy with SSL:
   ```nginx
   server {
       listen 443 ssl;
       server_name stylist.polly.wang;
       
       ssl_certificate /etc/letsencrypt/live/stylist.polly.wang/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/stylist.polly.wang/privkey.pem;
       
       location / {
           proxy_pass http://127.0.0.1:8888;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_buffering off;
           proxy_read_timeout 86400;
       }
   }
   ```

3. Set environment variables:
   ```bash
   MCP_EXTERNAL_HOST=stylist.polly.wang
   MCP_USE_SSL=true
   MCP_API_KEY=your-secure-api-key
   ```

## Performance

- **Haiku model**: ~19s per full outfit query (recommended for speed)
- **Sonnet model**: ~48s per full outfit query (higher quality)
- **Quick mode** (no reasoning): ~2s per query

## License

MIT
