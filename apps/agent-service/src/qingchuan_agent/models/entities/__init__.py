"""ORM 实体子包（晴川 x-QingChuan）。

当前骨架实体：
    AgentTask         任务表（编排中枢的任务载体）
    AgentEvent        事件表（协作事件留痕）
"""

from qingchuan_agent.models.entities.agent_event import AgentEvent
from qingchuan_agent.models.entities.agent_task import AgentTask

__all__ = ["AgentEvent", "AgentTask"]
