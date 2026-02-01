"""
Python MCP Client Example for Stylist MCP Server

远程调用 https://stylist.polly.wang 的示例代码
使用 Streamable HTTP 传输协议
"""

import asyncio
import httpx
import json

# ============================================================================
# 配置
# ============================================================================

MCP_SERVER_URL = "https://stylist.polly.wang"
MCP_ENDPOINT = f"{MCP_SERVER_URL}/mcp"
API_KEY = "YOUR_API_KEY_HERE"  # 替换为你的 API Key

# ============================================================================
# 方法 1: 直接 HTTP 调用（简单场景）
# ============================================================================

def health_check():
    """健康检查"""
    response = httpx.get(f"{MCP_SERVER_URL}/health")
    return response.json()

def list_tools():
    """列出可用工具（需要 API Key）"""
    response = httpx.get(
        f"{MCP_SERVER_URL}/tools",
        headers={"X-API-Key": API_KEY}
    )
    return response.json()

# ============================================================================
# 方法 2: 使用 Streamable HTTP（推荐）
# ============================================================================

async def call_mcp_streamable_http(query: str, include_reasoning: bool = True):
    """
    使用 Streamable HTTP 协议调用 MCP Server
    
    这是 MCP 协议的标准传输方式，配置简单：
    {"url": "https://stylist.polly.wang/mcp", "headers": {"X-API-Key": "..."}}
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-API-Key": API_KEY
    }
    
    async with httpx.AsyncClient() as client:
        # 1. 初始化 MCP 会话
        init_response = await client.post(
            MCP_ENDPOINT,
            headers=headers,
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
        
        init_data = init_response.json()
        print(f"Server: {init_data.get('result', {}).get('serverInfo', {})}")
        
        # 获取 session ID (如果服务器返回)
        session_id = init_response.headers.get("mcp-session-id")
        if session_id:
            headers["mcp-session-id"] = session_id
        
        # 2. 发送 initialized 通知
        await client.post(
            MCP_ENDPOINT,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
        )
        
        # 3. 调用推荐工具
        tool_response = await client.post(
            MCP_ENDPOINT,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "stylist_recommend",
                    "arguments": {
                        "query": query,
                        "include_reasoning": include_reasoning,
                        "include_image_urls": True
                    }
                }
            }
        )
        
        return tool_response.json()


def call_mcp_sync(query: str, include_reasoning: bool = True):
    """同步版本的 MCP 调用"""
    return asyncio.run(call_mcp_streamable_http(query, include_reasoning))


# ============================================================================
# 方法 3: 使用 MCP Python SDK（如果安装了）
# ============================================================================

async def call_with_mcp_sdk(query: str):
    """
    使用 MCP Python SDK 调用（需要 pip install mcp）
    
    注意：SDK 会自动处理协议细节
    """
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
        
        async with streamablehttp_client(MCP_ENDPOINT, headers={"X-API-Key": API_KEY}) as (read_stream, write_stream):
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
                        "query": query,
                        "include_reasoning": True,
                        "include_image_urls": True
                    }
                )
                
                return result
    except ImportError:
        print("MCP SDK not installed. Run: pip install mcp")
        return None


# ============================================================================
# 示例运行
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Stylist MCP Server - Python Client Example")
    print("=" * 60)
    print(f"Server: {MCP_SERVER_URL}")
    print(f"Endpoint: {MCP_ENDPOINT}")
    print()
    
    # 健康检查（不需要认证）
    print("1. Health Check:")
    print(json.dumps(health_check(), indent=2))
    
    # 使用 Streamable HTTP 调用
    print("\n2. Calling stylist_recommend via Streamable HTTP...")
    print("-" * 40)
    
    try:
        result = call_mcp_sync("推荐3套适合春季约会的穿搭", include_reasoning=True)
        
        if "result" in result:
            # 解析工具调用结果
            content = result["result"].get("content", [])
            if content and content[0].get("type") == "text":
                data = json.loads(content[0]["text"])
                print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
