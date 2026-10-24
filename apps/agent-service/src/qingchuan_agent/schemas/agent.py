#!/usr/bin/env python3
"""Agent 编排域 Schema（晴川 x-QingChuan，对齐北辰 schemas/agent）。

任务提交 / 人工接管入参。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from qingchuan_agent.constants import AgentType, HumanDecision


class AgentTaskCreate(BaseModel):
    """提交一个 Agent 任务。

    路由（hybrid）：传了 task_type 直接查表命中；留空时由 LLM 依据 query/payload
    自然语言从已注册 Agent 中选择，未命中则任务失败。
    """

    model_config = ConfigDict(use_enum_values=True)

    task_type: AgentType | None = Field(
        default=None,
        description="任务类型（显式指定则直接路由；留空由 LLM 动态选择）",
    )
    query: str | None = Field(
        default=None,
        description="自然语言任务描述；task_type 留空时供 LLM 动态路由使用",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="任务入参（按最终路由到的 Agent 选用对应字段，各 Agent 自定义结构）",
    )
    timeout_at: datetime | None = Field(default=None, description="超时时间，默认按配置")


class AgentTaskResumeIn(BaseModel):
    """人工接管后恢复执行入参（interrupt/resume）。"""

    model_config = ConfigDict(use_enum_values=True)

    decision: HumanDecision = Field(description="人工决策：approve / reject / adjust")
    remark: str | None = Field(default=None, description="人工备注")
    extra: dict[str, Any] = Field(
        default_factory=dict, description="附加数据（人工补充的调整信息）"
    )


__all__ = ["AgentTaskCreate", "AgentTaskResumeIn"]
