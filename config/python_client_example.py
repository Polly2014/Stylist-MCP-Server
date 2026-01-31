"""
Python MCP Client Example for Stylist MCP Server

远程调用 https://stylist.polly.wang 的示例代码
"""

import asyncio
import httpx
import json

# ============================================================================
# 配置
# ============================================================================

MCP_SERVER_URL = "https://stylist.polly.wang"
SSE_ENDPOINT = f"{MCP_SERVER_URL}/sse"
MESSAGES_ENDPOINT = f"{MCP_SERVER_URL}/messages/"

# ============================================================================
# 方法 1: 直接 HTTP 调用（简单场景）
# ============================================================================

def health_check():
    """健康检查"""
    response = httpx.get(f"{MCP_SERVER_URL}/health")
    return response.json()

def list_tools():
    """列出可用工具"""
    response = httpx.get(f"{MCP_SERVER_URL}/tools")
    return response.json()

# ============================================================================
# 方法 2: 使用 MCP SDK（推荐）
# ============================================================================

async def call_with_mcp_sdk():
    """使用 MCP Python SDK 调用"""
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    
    async with sse_client(SSE_ENDPOINT) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # 初始化连接
            await session.initialize()
            
            # 列出可用工具
            tools = await session.list_tools()
            print("Available tools:", [t.name for t in tools.tools])
            
            # 调用推荐工具
            result = await session.call_tool(
                "stylist_recommend",
                arguments={
                    "query": "推荐3套适合约会的休闲装",
                    "include_reasoning": True,
                    "include_image_urls": True
                }
            )
            
            return result

# ============================================================================
# 方法 3: 原始 SSE 调用（调试用）
# ============================================================================

async def call_with_raw_sse():
    """使用原始 SSE 协议调用"""
    import httpx_sse
    
    async with httpx.AsyncClient() as client:
        # 1. 建立 SSE 连接获取 session
        async with httpx_sse.aconnect_sse(client, "GET", SSE_ENDPOINT) as event_source:
            # 获取 endpoint URI
            async for event in event_source.aiter_sse():
                if event.event == "endpoint":
                    messages_uri = event.data
                    break
            
            # 2. 发送初始化请求
            init_response = await client.post(
                f"{MCP_SERVER_URL}{messages_uri}",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "python-client", "version": "1.0.0"}
                    }
                }
            )
            
            # 3. 调用工具
            tool_response = await client.post(
                f"{MCP_SERVER_URL}{messages_uri}",
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "stylist_recommend",
                        "arguments": {
                            "query": "recommend 2 casual dresses",
                            "include_reasoning": True,
                            "include_image_urls": True
                        }
                    }
                }
            )
            
            return tool_response.json()

# ============================================================================
# 示例运行
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Stylist MCP Server Remote Client Example")
    print("=" * 60)
    
    # 健康检查
    print("\n1. Health Check:")
    print(json.dumps(health_check(), indent=2))
    
    # 列出工具
    print("\n2. Available Tools:")
    print(json.dumps(list_tools(), indent=2))
    
    # 使用 MCP SDK 调用
    print("\n3. Calling stylist_recommend via MCP SDK...")
    try:
        result = asyncio.run(call_with_mcp_sdk())
        print(json.dumps(json.loads(result.content[0].text), indent=2, ensure_ascii=False))
    except ImportError:
        print("MCP SDK not installed. Run: pip install mcp")
    except Exception as e:
        print(f"Error: {e}")
