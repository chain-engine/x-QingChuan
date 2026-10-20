"""人社参保人员领域实体（骨架占位）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InsuredPerson:
    """参保人员核心信息。

    TODO: 字段以下一步对接人社 API 的实际响应为准；落库前按脱敏策略处理
    （身份证号、手机号等敏感字段需掩码或分级存储）。
    """

    insured_id: str
    name: str
    id_card_masked: str | None = None
    company_name: str | None = None
    region_code: str | None = None
