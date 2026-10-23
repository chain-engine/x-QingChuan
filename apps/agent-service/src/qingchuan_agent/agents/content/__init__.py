"""内容创作 Agent 包（晴川 x-QingChuan，agents/content）。

导入时完成注册（模块内注册到 agent_registry，子图惰性编译）。
"""

from qingchuan_agent.agents.content.agent import ContentCreationAgent
from qingchuan_agent.agents.registry import AgentSpec, agent_registry

agent_registry.register(AgentSpec(agent=ContentCreationAgent()))

__all__ = ["ContentCreationAgent"]
