"""安全 Agent 包（晴川 x-QingChuan，agents/security）。

导入时完成注册（模块内注册到 agent_registry，子图惰性编译）。
"""

from qingchuan_agent.agents.registry import AgentSpec, agent_registry
from qingchuan_agent.agents.security.agent import SecurityAgent

agent_registry.register(AgentSpec(agent=SecurityAgent()))

__all__ = ["SecurityAgent"]
