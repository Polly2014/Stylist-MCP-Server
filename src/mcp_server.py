"""
MCP Server for Stylist Recommender
Provides fashion recommendation tools via Model Context Protocol

Supports two transport modes:
- stdio: For local Claude Desktop / Cursor integration
- http: For remote HTTP access (Streamable HTTP + SSE)

Usage:
    # stdio mode (default, for local use)
    python mcp_server.py
    
    # HTTP mode (for remote access, supports both Streamable HTTP and SSE)
    python mcp_server.py --http --port 8888
    
    # Or with uvicorn directly
    uvicorn mcp_server:starlette_app --host 0.0.0.0 --port 8888
    
Client Configuration (Streamable HTTP - recommended):
    {
        "url": "https://stylist.polly.wang/mcp",
        "headers": {"X-API-Key": "your-api-key"}
    }

Client Configuration (SSE - legacy):
    {
        "command": "npx",
        "args": ["-y", "mcp-remote", "https://stylist.polly.wang/sse?apiKey=your-api-key", "--transport", "sse-only"]
    }
"""
import json
import asyncio
import argparse
import sys
from typing import Any
from pathlib import Path

# Support both direct run (python mcp_server.py) and module run (python -m src.mcp_server)
try:
    from stylist_tool import StylistSearchTool, TOOL_SCHEMA
    from garment_db import GarmentDatabase
    from config import DRESSCODE_ROOT, MCP_HOST, MCP_PORT, MCP_EXTERNAL_HOST, MCP_USE_SSL, MCP_API_KEY, MCP_API_KEY_ENABLED
except ImportError:
    from src.stylist_tool import StylistSearchTool, TOOL_SCHEMA
    from src.garment_db import GarmentDatabase
    from src.config import DRESSCODE_ROOT, MCP_HOST, MCP_PORT, MCP_EXTERNAL_HOST, MCP_USE_SSL, MCP_API_KEY, MCP_API_KEY_ENABLED

from mcp.server import Server
from mcp.types import Tool, TextContent, Resource


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


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name=TOOL_SCHEMA["name"],
            description=TOOL_SCHEMA["description"],
            inputSchema=TOOL_SCHEMA["input_schema"]
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
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
    """Create Starlette app with SSE and Streamable HTTP transport for MCP"""
    from mcp.server.sse import SseServerTransport
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    from starlette.responses import JSONResponse, Response
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    import contextlib
    
    # =========================================================================
    # API Key Authentication Middleware (Pure ASGI - compatible with SSE)
    # =========================================================================
    class APIKeyMiddleware:
        """
        Pure ASGI middleware to validate API key for protected endpoints.
        Note: We use pure ASGI instead of BaseHTTPMiddleware because 
        BaseHTTPMiddleware is incompatible with SSE streaming responses.
        """
        
        # Endpoints that don't require authentication
        PUBLIC_PATHS = {"/health", "/favicon.ico"}
        PUBLIC_PREFIXES = ("/images/", "/.well-known/")  # Image serving and OAuth discovery are public
        
        def __init__(self, app):
            self.app = app
        
        async def __call__(self, scope, receive, send):
            # Only process HTTP requests
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return
            
            # Skip auth if API key is not configured
            if not MCP_API_KEY_ENABLED:
                await self.app(scope, receive, send)
                return
            
            path = scope["path"]
            
            # Allow public endpoints without auth
            if path in self.PUBLIC_PATHS:
                await self.app(scope, receive, send)
                return
            
            # Allow public prefixes (like /images/)
            if any(path.startswith(prefix) for prefix in self.PUBLIC_PREFIXES):
                await self.app(scope, receive, send)
                return
            
            # Extract API key from query params or headers
            api_key = None
            
            # Check query params
            query_string = scope.get("query_string", b"").decode()
            if query_string:
                from urllib.parse import parse_qs
                params = parse_qs(query_string)
                api_key = params.get("apiKey", params.get("api_key", [None]))[0]
            
            # Check headers if not in query params
            if not api_key:
                headers = dict(scope.get("headers", []))
                api_key = headers.get(b"x-api-key", b"").decode()
                if not api_key:
                    auth_header = headers.get(b"authorization", b"").decode()
                    if auth_header.startswith("Bearer "):
                        api_key = auth_header[7:]
            
            if api_key != MCP_API_KEY:
                # Return 401 Unauthorized
                response = JSONResponse(
                    {"error": "Unauthorized", "message": "Invalid or missing API key"},
                    status_code=401
                )
                await response(scope, receive, send)
                return
            
            await self.app(scope, receive, send)
    
    # SSE transport at /messages endpoint (legacy, for mcp-remote compatibility)
    sse = SseServerTransport("/messages/")
    
    # Streamable HTTP session manager (new standard, simpler client config)
    session_manager = StreamableHTTPSessionManager(
        app=app,
        json_response=True,  # Use JSON responses for better compatibility
        stateless=False  # Enable session tracking
    )
    
    async def handle_sse(request):
        """Handle SSE connection for MCP (legacy)"""
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await app.run(
                streams[0], streams[1], 
                app.create_initialization_options()
            )
        return Response()
    
    # Custom ASGI app for MCP endpoint - handles response lifecycle directly
    class MCPEndpointApp:
        """
        ASGI application for Streamable HTTP MCP endpoint.
        Allows simple client config like Tavily:
        {"url": "https://stylist.polly.wang/mcp", "headers": {"X-API-Key": "..."}}
        """
        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                await session_manager.handle_request(scope, receive, send)
    
    mcp_endpoint = MCPEndpointApp()
    
    async def health_check(request):
        """Health check endpoint"""
        return JSONResponse({
            "status": "healthy",
            "server": "stylist-recommender",
            "transport": ["streamable-http", "sse"],
            "tools": ["stylist_recommend"],
            "auth_enabled": MCP_API_KEY_ENABLED,
            "endpoints": {
                "mcp": "/mcp (recommended)",
                "sse": "/sse (legacy)"
            }
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
    
    async def oauth_not_supported(request):
        """Return 404 for OAuth discovery - we use API key auth instead"""
        return JSONResponse(
            {"error": "not_found", "message": "OAuth not supported. Use API key authentication."},
            status_code=404
        )
    
    from starlette.staticfiles import StaticFiles
    
    # Lifespan context manager to manage StreamableHTTP session manager
    @contextlib.asynccontextmanager
    async def lifespan(app_instance):
        """Manage application lifecycle including StreamableHTTP sessions"""
        async with session_manager.run():
            yield
    
    # Build middleware list - only CORS uses the Middleware wrapper
    middleware_list = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ]
    
    # Create Starlette app with CORS and lifespan
    base_app = Starlette(
        debug=True,
        lifespan=lifespan,
        routes=[
            Route("/health", endpoint=health_check, methods=["GET"]),
            Route("/tools", endpoint=list_tools_http, methods=["GET"]),
            # Streamable HTTP endpoint (new standard - simpler client config)
            # Using Route with ASGI app directly for proper path handling
            Route("/mcp", endpoint=mcp_endpoint, methods=["GET", "POST", "DELETE"]),
            # SSE endpoints (legacy - for mcp-remote compatibility)
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount("/messages/", app=sse.handle_post_message),
            # OAuth discovery endpoints - return 404 to indicate we don't support OAuth
            Route("/.well-known/oauth-authorization-server", endpoint=oauth_not_supported, methods=["GET"]),
            Route("/.well-known/openid-configuration", endpoint=oauth_not_supported, methods=["GET"]),
            # Static file serving for images
            Mount("/images", app=StaticFiles(directory=str(DRESSCODE_ROOT)), name="images"),
        ],
        middleware=middleware_list
    )
    
    # Wrap with API Key middleware if enabled (pure ASGI, SSE compatible)
    if MCP_API_KEY_ENABLED:
        starlette_app = APIKeyMiddleware(base_app)
    else:
        starlette_app = base_app
    
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


async def run_http(host: str = None, port: int = None, ssl_cert: str = None, ssl_key: str = None, external_host: str = None):
    """Run MCP server in HTTP mode (supports Streamable HTTP and SSE for remote access)"""
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
    
    print(f"Starting Stylist Recommender MCP Server (HTTP mode)...", flush=True)
    print(f"  Listening on {protocol}://{host}:{port}", flush=True)
    print(f"  Health check: {protocol}://{host}:{port}/health", flush=True)
    print(f"  MCP endpoint: {protocol}://{host}:{port}/mcp (recommended)", flush=True)
    print(f"  SSE endpoint: {protocol}://{host}:{port}/sse (legacy)", flush=True)
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
        "--http", "--sse", action="store_true", dest="http",
        help="Run in HTTP mode (supports both Streamable HTTP and SSE) instead of stdio"
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
    
    if args.http:
        await run_http(args.host, args.port, args.ssl_cert, args.ssl_key, args.external_host)
    else:
        await run_stdio()


if __name__ == "__main__":
    asyncio.run(main())
