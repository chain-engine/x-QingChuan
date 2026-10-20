#!/usr/bin/env python3
"""RAG 服务（晴川 x-QingChuan）。

承载语义检索（HTTP + MCP 双协议）、人社离线数据周期同步与索引管道。
领域协议（检索 / 同步 / 常量 / 异常）统一放共享领域包 qingchuan_domain。
"""

__version__ = "0.2.0"

__all__ = ["__version__"]
