# Semantic Kernel MCP 集成配置
# 用于 .NET / Python Semantic Kernel 项目

# ============================================================================
# Python Semantic Kernel 配置示例
# ============================================================================

"""
from semantic_kernel import Kernel
from semantic_kernel.connectors.mcp import MCPServerConnector

# 创建 MCP 连接器
mcp_connector = MCPServerConnector(
    server_url="https://stylist.polly.wang/sse",
    transport="sse"
)

# 添加到 Kernel
kernel = Kernel()
kernel.add_connector(mcp_connector)

# 获取可用的 MCP 工具
tools = await mcp_connector.get_tools()

# 调用推荐工具
result = await mcp_connector.invoke_tool(
    tool_name="stylist_recommend",
    arguments={
        "query": "推荐适合春季穿的连衣裙",
        "include_reasoning": True,
        "include_image_urls": True
    }
)
"""

# ============================================================================
# .NET Semantic Kernel 配置示例 (C#)
# ============================================================================

"""
// appsettings.json
{
  "MCP": {
    "Servers": {
      "StylistRecommender": {
        "Url": "https://stylist.polly.wang/sse",
        "Transport": "sse"
      }
    }
  }
}

// Program.cs
using Microsoft.SemanticKernel;
using Microsoft.SemanticKernel.MCP;

var builder = Kernel.CreateBuilder();

// 添加 MCP 服务器
builder.AddMCPServer("StylistRecommender", new MCPServerOptions
{
    Url = "https://stylist.polly.wang/sse",
    Transport = MCPTransport.SSE
});

var kernel = builder.Build();

// 调用工具
var result = await kernel.InvokeAsync("StylistRecommender", "stylist_recommend", new()
{
    ["query"] = "recommend elegant party dresses",
    ["include_reasoning"] = true,
    ["include_image_urls"] = true
});
"""

# ============================================================================
# 环境变量配置
# ============================================================================

MCP_STYLIST_URL = "https://stylist.polly.wang"
MCP_STYLIST_SSE_ENDPOINT = "https://stylist.polly.wang/sse"
MCP_STYLIST_MESSAGES_ENDPOINT = "https://stylist.polly.wang/messages/"
MCP_STYLIST_HEALTH_ENDPOINT = "https://stylist.polly.wang/health"
MCP_STYLIST_IMAGES_BASE = "https://stylist.polly.wang/images"
