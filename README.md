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

## Quick Start

### 1. Setup

```bash
# Clone and setup
git clone <repo-url>
cd stylist-mcp-server
chmod +x setup.sh
./setup.sh

# Edit configuration
cp .env.example .env
nano .env  # Configure DRESSCODE_ROOT, CHROMADB_PATH
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
python src/mcp_server.py --sse --port 8080
```

## Configuration

Environment variables (set in `.env`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DRESSCODE_ROOT` | Path to DressCode dataset | Required |
| `CHROMADB_PATH` | Path to ChromaDB persistence | Required |
| `LLM_API_ENDPOINT` | LLM API endpoint | `http://localhost:23333/api/anthropic/v1/messages` |
| `MODEL_NAME` | Claude model name | `claude-3-5-haiku-20241022` |
| `MCP_HOST` | SSE server host | `0.0.0.0` |
| `MCP_PORT` | SSE server port | `8080` |

## Available Tools

### `stylist_recommend`

Fashion recommendation tool that intelligently interprets user queries.

**Input:**
```json
{
  "query": "recommend 3 casual outfits for a date",
  "include_reasoning": true
}
```

**Output modes:**
- `single_item`: Returns list of individual garments
- `full_outfit`: Returns coordinated outfit combinations (top+bottom or dress)

### `get_garment_image`

Get the image of a specific garment by ID.

**Input:**
```json
{
  "garment_id": "049119",
  "category": "dresses"
}
```

## Claude Desktop Integration

Add to your Claude Desktop config (`~/.config/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "stylist-recommender": {
      "command": "python",
      "args": ["/path/to/stylist-mcp-server/src/mcp_server.py"],
      "env": {
        "DRESSCODE_ROOT": "/path/to/data/DressCode",
        "CHROMADB_PATH": "/path/to/chroma_db",
        "LLM_API_ENDPOINT": "http://localhost:23333/api/anthropic/v1/messages"
      }
    }
  }
}
```

## SSE Mode Endpoints

When running in SSE mode:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/tools` | GET | List available tools |
| `/sse` | GET | SSE connection for MCP |
| `/messages` | POST | MCP message handling |

## Project Structure

```
stylist-mcp-server/
├── src/
│   ├── config.py          # Configuration (env vars)
│   ├── garment_db.py      # ChromaDB wrapper
│   ├── stylist_tool.py    # Recommendation logic
│   └── mcp_server.py      # MCP server (stdio + SSE)
├── scripts/
│   ├── build_chromadb.py  # Index builder
│   └── test_mcp.py        # Test suite
├── config/
│   └── claude_desktop.json # Example config
├── requirements.txt
├── setup.sh
├── .env.example
└── README.md
```

## Testing

```bash
# Run local tests
python scripts/test_mcp.py --local-only

# Run full tests (with SSE server running)
python scripts/test_mcp.py --url http://localhost:8080
```

## Performance

- **Haiku model**: ~19s per query (recommended for speed)
- **Sonnet model**: ~48s per query (higher quality)

## License

MIT
