#!/usr/bin/env python3
"""晴川 x-QingChuan Agent 服务命令行入口（CLI）。

命令：
    uv run qingchuan-agent          编排运行时骨架演示（注册 → 构建编排图 → 演示调用一个任务）
    uv run qingchuan-agent-api     启动 HTTP 服务（等价 uvicorn qingchuan_agent.main:app）
"""

from __future__ import annotations

import uvicorn

from qingchuan_agent import (
    agents,  # noqa: F401  编排层入口：业务编排单元 + 工具注册在导入时完成
)
from qingchuan_agent.agents.registry import agent_registry
from qingchuan_agent.agents.runtime import get_agent_runtime
from qingchuan_agent.core.config import get_settings
from qingchuan_agent.core.logger import logger, setup_logging


def demo() -> None:
    """编排运行时骨架演示：注册 → 构建编排图 → 演示调用一个任务。"""
    setup_logging()
    settings = get_settings()
    logger.info(f"[{settings.service_name}] 编排运行时骨架启动")
    for spec in agent_registry.list_specs():
        logger.info(f"  已注册：[{spec.agent_type}] {spec.name}：{spec.description}")

    runtime = get_agent_runtime()
    final_state = runtime.invoke_task("customer_service", {"query": "演示：养老金的领取条件是什么"})
    logger.info(
        f"演示任务结束：status={final_state.get('status')} result={final_state.get('result')}"
    )


def serve() -> None:
    """启动 HTTP 服务（uvicorn）。"""
    from qingchuan_agent.core.config import settings

    uvicorn.run(
        "qingchuan_agent.main:app",
        host=settings.server.host,
        port=settings.server.port,
        workers=settings.server.workers,
        reload=settings.server.debug,
    )


def main() -> None:
    """CLI 入口（默认执行编排 demo）。"""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        serve()
    else:
        demo()


if __name__ == "__main__":
    main()


__all__ = ["demo", "main", "serve"]
