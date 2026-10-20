"""共享领域协议层：人社数据同步的请求 / 状态数据契约。

晴川与人社系统的差异点：离线数据由"触发接口 + 周期调度"同步进入
向量库，而非直接上传。本模块定义同步触发、任务状态的领域协议，
具体数据源实现细节（接口文档 / 认证 / 字段映射）见 rag-service 的
qingchuan_rag/sync/hrss_client.py 中 TODO。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SyncTaskStatusValue = Literal["pending", "running", "success", "failed"]
SyncTriggerChannel = Literal["manual", "scheduler"]


class SyncTriggerRequest(BaseModel):
    """同步触发请求（HTTP 触发接口入参）。"""

    source: str = Field(default="hrss", description="数据源标识，默认人社系统 hrss")
    full: bool = Field(default=False, description="True=全量同步，False=增量同步")
    force: bool = Field(default=False, description="True=忽略已同步标记强制重跑")


class SyncTaskStatus(BaseModel):
    """同步任务状态（触发接口 / 状态查询返回）。"""

    task_id: str = Field(description="同步任务 ID")
    status: SyncTaskStatusValue = Field(default="pending", description="任务状态")
    channel: SyncTriggerChannel = Field(default="manual", description="触发渠道：manual/scheduler")
    full: bool = Field(default=False, description="是否全量同步")
    total_records: int = Field(default=0, description="本次待同步记录总数")
    synced_records: int = Field(default=0, description="成功同步记录数")
    failed_records: int = Field(default=0, description="失败记录数")
    started_at: datetime | None = Field(default=None, description="开始时间")
    finished_at: datetime | None = Field(default=None, description="结束时间")
    message: str = Field(default="", description="执行说明 / 错误摘要")


class SyncTaskResult(SyncTaskStatus):
    """同步任务最终结果（含明细错误）。"""

    error: str | None = Field(default=None, description="失败明细（可为空）")


__all__ = ["SyncTaskResult", "SyncTaskStatus", "SyncTriggerRequest"]
