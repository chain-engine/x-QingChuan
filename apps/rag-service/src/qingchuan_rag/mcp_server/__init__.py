#!/usr/bin/env python3
"""
MCP Server Package

晴川 MCP（Model Context Protocol）服务层——与 HTTP 接入层（http_server/）
平级对称的双协议出口之一，只依赖共享业务核心（services/ 等）。

目录说明（按 MCP 协议原语组织，可扩展）：
    - server.py      MCPServer 实例 + 三大原语统一注册入口（bind_rag_service）
    - tools.py       Tools 原语：retrieve_docs / rag_query（当前暴露，只读）
    - prompts.py     Prompts 原语（预留，空实现 + 启用说明）
    - resources.py   Resources 原语（预留，空实现 + 启用说明）

命名说明：目录名使用 mcp_server 而非 mcp，避免与官方 mcp SDK 包同名冲突
（若本地包名为 mcp，import mcp 会命中本地包而遮蔽 site-packages 中的官方 SDK）。

安全：晴川为内部服务，不设应用身份鉴权；审计日志统一记 internal。
"""
