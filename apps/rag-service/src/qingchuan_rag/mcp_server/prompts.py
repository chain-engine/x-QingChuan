#!/usr/bin/env python3
"""MCP 提示词原语（Prompts）——预留，当前不开放。

MCP Prompts 是"用户可复用的问题模板"（由客户端触发，模型按模板执行），
与 Tools 的区别：Prompts 不新增能力，只是把常用提问方式固化为模板。

开放条件（按需启用）：
- 知识库内容固定且提问模式成熟（如"总结某主题""对比某两篇文档"）；
- 确认模板不泄露内部 prompt 细节，且不鼓励绕过 rag_query 的引用返回。

启用方式：取消下方示例的注释，将模板注册进 server，并删除本段说明。
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer


def register_prompts(server: MCPServer) -> None:
    """注册 MCP 提示词模板（当前为空实现，作为扩展入口预留）。

    示例骨架（按需启用，替换为真实模板）：
        @server.prompt()
        def summarize_knowledge(topic: str) -> str:
            \"\"\"基于知识库总结指定主题（topic 必填）。\"\"\"
            return (
                f"请基于晴川知识库中关于「{topic}」的内容进行总结，"
                "列出关键结论并标注引用片段。"
            )
    """
    # 预留：当前无开放模板，保持空实现
    return None


__all__ = ["register_prompts"]
