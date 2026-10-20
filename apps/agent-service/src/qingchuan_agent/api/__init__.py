"""API 接口层包（晴川 x-QingChuan）。

    router       全局路由聚合（/api/v1 前缀）
    response     统一响应构造（ApiResponse 包装）
    dependencies 跨域公共依赖注入（db 会话 / 任务服务）
    v1           v1 业务路由（health / agent_task）
"""
