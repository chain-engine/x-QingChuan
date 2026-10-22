"""基础设施子包（晴川 x-QingChuan）。

database    数据库提供者（SQLAlchemy 2.0 + MySQL）
llm         LLM 提供方抽象（LangChain 兼容 / Mock）
event_bus   事件总线（InMemory 单进程广播 / Redis Pub/Sub 跨进程广播）
redis        Redis 连接设施（checkpoint 与事件总线共用同一实例配置）
"""
