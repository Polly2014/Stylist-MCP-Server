"""
MCP Server for Stylist Recommender
Provides fashion recommendation tools via Model Context Protocol

Supports two transport modes:
- stdio: For local Claude Desktop / Cursor integration
- sse: For remote HTTP access (cross-VM, Semantic Kernel integration)

Usage:
    # stdio mode (default, for local use)
    python mcp_server.py
    
    # SSE mode (for remote access)
    python mcp_server.py --sse --port 8080
    
    # Or with uvicorn directly
    uvicorn mcp_server:starlette_app --host 0.0.0.0 --port 8080
"""
import json
import asyncio
import argparse
import base64
from typing import Any
from pathlib import Path

from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, Resource

from stylist_tool import StylistSearchTool, TOOL_SCHEMA
from garment_db import GarmentDatabase
from config import DRESSCODE_ROOT, MCP_HOST, MCP_PORT, MCP_EXTERNAL_HOST, MCP_USE_SSL


# Initialize server and tools
app = Server("stylist-recommender")
stylist_tool = StylistSearchTool()

# Global variable to store the base URL for image serving
_image_base_url = None

def set_image_base_url(host: str, port: int, use_ssl: bool):
    """Set the base URL for image serving"""
    global _image_base_url
    protocol = "https" if use_ssl else "http"
    # If using standard ports (80/443) or behind reverse proxy, omit port
    if use_ssl and (port == 443 or MCP_USE_SSL):
        _image_base_url = f"{protocol}://{host}/images"
    elif not use_ssl and port == 80:
        _image_base_url = f"{protocol}://{host}/images"
    else:
        _image_base_url = f"{protocol}://{host}:{port}/images"

def get_image_url(image_path: str) -> str | None:
    """Convert local image path to URL"""
    if not _image_base_url or not image_path:
        return None
    # image_path example: /datasets/DressCode/dresses/images/012345_1.jpg
    # We need to extract: dresses/images/012345_1.jpg
    try:
        path = Path(image_path)
        # Find the category part (dresses, upper_body, lower_body)
        parts = path.parts
        for i, part in enumerate(parts):
            if part in ["dresses", "upper_body", "lower_body"]:
                relative_path = "/".join(parts[i:])
                return f"{_image_base_url}/{relative_path}"
    except Exception:
        pass
    return None


# Additional tool for getting garment images
GET_IMAGE_SCHEMA = {
    "name": "get_garment_image",
    "description": "Get the image of a specific garment by its ID. Returns base64 encoded image.",
    "input_schema": {
        "type": "object",
        "properties": {
            "garment_id": {
                "type": "string",
                "description": "The garment ID (e.g., '049119')"
            },
            "category": {
                "type": "string",
                "enum": ["dresses", "upper_body", "lower_body"],
                "description": "The garment category (optional, will search if not provided)"
            }
        },
        "required": ["garment_id"]
    }
}


def find_garment_image(garment_id: str, category: str = None) -> Path | None:
    """Find garment image path by ID"""
    if category:
        categories = [category]
    else:
        categories = ["dresses", "upper_body", "lower_body"]
    
    for cat in categories:
        image_path = DRESSCODE_ROOT / cat / "images" / f"{garment_id}_1.jpg"
        if image_path.exists():
            return image_path
    return None


def image_to_base64(image_path: Path, max_size: int = 400) -> str:
    """Convert image to base64 with optional resizing"""
    from PIL import Image
    import io
    
    img = Image.open(image_path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((max_size, max_size))
    
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name=TOOL_SCHEMA["name"],
            description=TOOL_SCHEMA["description"],
            inputSchema=TOOL_SCHEMA["input_schema"]
        ),
        Tool(
            name=GET_IMAGE_SCHEMA["name"],
            description=GET_IMAGE_SCHEMA["description"],
            inputSchema=GET_IMAGE_SCHEMA["input_schema"]
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:
    """Handle tool calls"""
    
    if name == "stylist_recommend":
        # Run recommend_outfit in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: stylist_tool.recommend_outfit(
                query=arguments["query"],
                include_reasoning=arguments.get("include_reasoning", True),
                include_image_urls=arguments.get("include_image_urls", True),
                image_url_generator=get_image_url
            )
        )
        
        # Format response
        return [TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2)
        )]
    
    elif name == "get_garment_image":
        garment_id = arguments["garment_id"]
        category = arguments.get("category")
        
        image_path = find_garment_image(garment_id, category)
        
        if image_path is None:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Image not found for garment {garment_id}"})
            )]
        
        # Return base64 encoded image
        try:
            image_base64 = image_to_base64(image_path)
            return [
                TextContent(
                    type="text",
                    text=json.dumps({
                        "garment_id": garment_id,
                        "image_path": str(image_path),
                        "format": "base64"
                    })
                ),
                ImageContent(
                    type="image",
                    data=image_base64,
                    mimeType="image/jpeg"
                )
            ]
        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Failed to load image: {str(e)}"})
            )]
    
    else:
        return [TextContent(
            type="text",
            text=json.dumps({"error": f"Unknown tool: {name}"})
        )]


@app.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources (garment categories)"""
    return [
        Resource(
            uri=f"stylist://categories/{cat}",
            name=f"DressCode {cat}",
            description=f"Garments in the {cat} category",
            mimeType="application/json"
        )
        for cat in ["dresses", "upper_body", "lower_body"]
    ]


# =============================================================================
# SSE Transport Setup (for remote/cross-VM access)
# =============================================================================

def create_starlette_app():
    """Create Starlette app with SSE transport for MCP"""
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    from starlette.responses import JSONResponse, Response
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    
    # SSE transport at /messages endpoint
    sse = SseServerTransport("/messages/")
    
    async def handle_sse(request):
        """Handle SSE connection for MCP"""
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await app.run(
                streams[0], streams[1], 
                app.create_initialization_options()
            )
        return Response()
    
    async def health_check(request):
        """Health check endpoint"""
        return JSONResponse({
            "status": "healthy",
            "server": "stylist-recommender",
            "transport": "sse",
            "tools": ["stylist_recommend", "get_garment_image"]
        })
    
    async def list_tools_http(request):
        """HTTP endpoint to list available tools (for debugging)"""
        tools = await list_tools()
        return JSONResponse({
            "tools": [
                {"name": t.name, "description": t.description}
                for t in tools
            ]
        })
    
    from starlette.staticfiles import StaticFiles
    
    # Create Starlette app with CORS enabled
    starlette_app = Starlette(
        debug=True,
        routes=[
            Route("/health", endpoint=health_check, methods=["GET"]),
            Route("/tools", endpoint=list_tools_http, methods=["GET"]),
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount("/messages/", app=sse.handle_post_message),
            # Static file serving for images
            Mount("/images", app=StaticFiles(directory=str(DRESSCODE_ROOT)), name="images"),
        ],
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            )
        ]
    )
    
    return starlette_app


# Create starlette app for uvicorn direct usage
starlette_app = create_starlette_app()


# =============================================================================
# Main Entry Point
# =============================================================================

async def run_stdio():
    """Run MCP server in stdio mode (for local use)"""
    from mcp.server.stdio import stdio_server
    
    print("Starting Stylist Recommender MCP Server (stdio mode)...", flush=True)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


async def run_sse(host: str = None, port: int = None, ssl_cert: str = None, ssl_key: str = None, external_host: str = None):
    """Run MCP server in SSE mode (for remote access)"""
    import uvicorn
    
    # Use provided args or fall back to config defaults
    host = host or MCP_HOST
    port = port or MCP_PORT
    external_host = external_host or MCP_EXTERNAL_HOST  # Use config default if not provided
    
    # Determine protocol - use MCP_USE_SSL for reverse proxy scenarios
    use_ssl = (ssl_cert and ssl_key) or MCP_USE_SSL
    protocol = "https" if use_ssl else "http"
    
    # Set image base URL for URL generation
    # Priority: external_host (arg or config) > host (if not 0.0.0.0) > localhost
    if external_host:
        url_host = external_host
    elif host != "0.0.0.0":
        url_host = host
    else:
        url_host = "localhost"
    set_image_base_url(url_host, port, use_ssl)
    
    print(f"Starting Stylist Recommender MCP Server (SSE mode)...", flush=True)
    print(f"  Listening on {protocol}://{host}:{port}", flush=True)
    print(f"  Health check: {protocol}://{host}:{port}/health", flush=True)
    print(f"  SSE endpoint: {protocol}://{host}:{port}/sse", flush=True)
    print(f"  Messages endpoint: {protocol}://{host}:{port}/messages", flush=True)
    print(f"  Images endpoint: {protocol}://{host}:{port}/images/", flush=True)
    
    config = uvicorn.Config(
        starlette_app,
        host=host,
        port=port,
        log_level="info",
        ssl_certfile=ssl_cert,
        ssl_keyfile=ssl_key
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """Run the MCP server"""
    parser = argparse.ArgumentParser(description="Stylist Recommender MCP Server")
    parser.add_argument(
        "--sse", action="store_true",
        help="Run in SSE mode (HTTP) instead of stdio"
    )
    parser.add_argument(
        "--host", type=str, default=None,
        help=f"Host to bind (SSE mode only, default: {MCP_HOST})"
    )
    parser.add_argument(
        "--port", type=int, default=None,
        help=f"Port to bind (SSE mode only, default: {MCP_PORT})"
    )
    parser.add_argument(
        "--ssl-cert", type=str, default=None,
        help="Path to SSL certificate file (enables HTTPS)"
    )
    parser.add_argument(
        "--ssl-key", type=str, default=None,
        help="Path to SSL private key file (enables HTTPS)"
    )
    parser.add_argument(
        "--external-host", type=str, default=None,
        help="External hostname/IP for image URLs (e.g., 20.51.201.85)"
    )
    
    args = parser.parse_args()
    
    if args.sse:
        await run_sse(args.host, args.port, args.ssl_cert, args.ssl_key, args.external_host)
    else:
        await run_stdio()


if __name__ == "__main__":
    asyncio.run(main())
