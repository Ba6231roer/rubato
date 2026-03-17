class MCPError(Exception):
    """MCP基础错误"""
    pass


class MCPConnectionError(MCPError):
    """MCP连接错误"""
    pass


class MCPToolCallError(MCPError):
    """MCP工具调用错误"""
    pass
