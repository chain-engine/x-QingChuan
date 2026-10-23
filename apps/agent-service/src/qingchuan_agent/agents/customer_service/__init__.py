"""问答（客服）Agent 包（晴川 x-QingChuan，agents/customer_service）。

导入时完成注册（模块内注册到 agent_registry，子图惰性编译）。
"""

from qingchuan_agent.agents.customer_service.agent import CustomerServiceAgent
from qingchuan_agent.agents.registry import AgentSpec, agent_registry

agent_registry.register(AgentSpec(agent=CustomerServiceAgent()))

__all__ = ["CustomerServiceAgent"]
