#!/usr/bin/env python3
"""MCP 资源原语（Resources）——预留，当前不开放。

MCP Resources 是"应用提供的上下文数据"（客户端可枚举 / 读取，模型可引用），
与 Tools 的区别：Resources 暴露的是数据实体而非可调用能力。

开放条件（按需启用）：
- 需要按 document_id 暴露文档原文 / 元数据给客户端（模型侧引用或审计用）；
- 确认资源 URI 协议稳定（如 documents://{document_id}），且不暴露内部存储路径。

启用方式：取消下方示例的注释，将资源注册进 server，并删除本段说明。
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer


def register_resources(server: MCPServer) -> None:
    """注册 MCP 资源（当前为空实现，作为扩展入口预留）。

    示例骨架（按需启用，替换为真实资源协议）：
        @server.resource("documents://{document_id}")
        def get_document(document_id: str) -> str:
            \"\"\"按 document_id 返回文档原文（需先在 DocumentService 暴露只读查询）。\"\"\"
            raise NotImplementedError("预留：待 DocumentService 提供 get_document 后启用")
    """
    # 预留：当前无开放资源，保持空实现
    return None


__all__ = ["register_resources"]
