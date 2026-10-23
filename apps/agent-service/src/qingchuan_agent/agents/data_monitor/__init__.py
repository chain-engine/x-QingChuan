"""数据监控 Agent 包（晴川 x-QingChuan，agents/data_monitor）。

导入时完成注册（模块内注册到 agent_registry，子图惰性编译）。
"""

from qingchuan_agent.agents.data_monitor.agent import DataMonitorAgent
from qingchuan_agent.agents.registry import AgentSpec, agent_registry

agent_registry.register(AgentSpec(agent=DataMonitorAgent()))

__all__ = ["DataMonitorAgent"]
