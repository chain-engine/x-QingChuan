#!/usr/bin/env python3
"""枚举基类族。

所有成员统一按二元组 (mark, desc) 定义：
    mark —— 存储值（str / int / float），落库、序列化、与裸值比较均用它
    desc —— 中文展示文案

选型：
    BaseEnum      通用基类，成员不具备原生值类型（推荐默认使用）
    StrBaseEnum   成员是 str 子类，可直接当字符串使用（事件类型、状态码等）
    IntBaseEnum   成员是 int 子类（HTTP 状态码、数值码）
    FloatBaseEnum 成员是 float 子类（浮点档位，不建议用于精确等值场景）

注：类型混入枚举需在 __new__ 中用原生类型构造并设置 _value_，
因为 EnumMeta 会把整个 (mark, desc) 二元组传给 __new__，
直接走原生构造会报 "decoding str is not supported" 之类错误。
mypy 不支持 Enum 泛型化（Enum class cannot be generic），
故基类 mark/value 声明为 ``int | str``，具体子类覆写收窄返回类型。
"""

from enum import Enum
from typing import Any, Self, cast


class BaseEnum(Enum):
    """可描述枚举基类，成员值为 (mark, desc)。"""

    def __init__(self, mark: int | str, desc: str) -> None:
        self._mark = mark
        self._desc = desc

    @property
    def mark(self) -> int | str:
        """存储值，用于落库与序列化。"""
        return self._mark

    @property
    def value(self) -> int | str:
        """同 mark（Enum / Pydantic 默认取 .value 序列化）。"""
        return self._mark

    @property
    def desc(self) -> str:
        """中文展示文案。"""
        return self._desc

    def __str__(self) -> str:
        return str(self._mark)

    def __eq__(self, other: object) -> bool:
        # 枚举之间按身份判等，不同枚举类型即使 mark 相同也不相等；
        # 与裸值比较时直接对比 mark，类型不符自然为 False。
        if isinstance(other, Enum):
            return super().__eq__(other)
        return self._mark == other

    def __hash__(self) -> int:
        # 自定义 __eq__ 后必须显式定义 __hash__，且与 mark 同哈希，
        # 成员才能与裸 mark 互换作为字典键。
        return hash(self._mark)

    @classmethod
    def get_all_marks(cls) -> list[int | str]:
        """全部成员的 mark 列表。"""
        return [member.mark for member in cls]

    @classmethod
    def get_all_descs(cls) -> list[str]:
        """全部成员的 desc 列表。"""
        return [member.desc for member in cls]

    @classmethod
    def get_choices(cls) -> tuple[tuple[int | str, str], ...]:
        """(mark, desc) 二元组序列，用于下拉选项。"""
        return tuple((member.mark, member.desc) for member in cls)

    @classmethod
    def get_desc_by_mark(cls, mark: int | str, default: str | None = None) -> str:
        """按 mark 反查 desc；未命中返回 default，default 为 None 时回退为 mark。"""
        for member in cls:
            if member.mark == mark:
                return member.desc
        return default if default is not None else str(mark)


def _new_native_member(cls: type, native_type: type, mark: object) -> object:
    """类型混入枚举的公共构造：只用 mark 调原生构造，并回填 Enum 要求的 _value_。"""
    obj = native_type.__new__(cls, mark)
    cast(Any, obj)._value_ = mark
    return obj


class StrBaseEnum(str, BaseEnum):
    """字符串型枚举：成员同时是 str，可直接 JSON 序列化、作字典键、与裸字符串比较。"""

    def __new__(cls, mark: str, desc: str) -> Self:
        return cast(Self, _new_native_member(cls, str, mark))

    def __str__(self) -> str:
        return str.__str__(self)

    @property
    def mark(self) -> str:
        """存储值（str）。"""
        return cast(str, self._mark)

    @property
    def value(self) -> str:
        """同 mark（str）。"""
        return cast(str, self._mark)


class IntBaseEnum(int, BaseEnum):
    """整数型枚举：成员同时是 int，可直接参与数值比较与 JSON 数字序列化。"""

    def __new__(cls, mark: int, desc: str) -> Self:
        return cast(Self, _new_native_member(cls, int, mark))

    @property
    def mark(self) -> int:
        """存储值（int）。"""
        return cast(int, self._mark)

    @property
    def value(self) -> int:
        """同 mark（int）。"""
        return cast(int, self._mark)


class FloatBaseEnum(float, BaseEnum):
    """浮点型枚举：成员同时是 float。浮点 mark 不适合精确等值场景。"""

    def __new__(cls, mark: float, desc: str) -> Self:
        return cast(Self, _new_native_member(cls, float, mark))

    @property
    def mark(self) -> float:  # type: ignore[override]
        """存储值（float）。"""
        return cast(float, self._mark)

    @property
    def value(self) -> float:  # type: ignore[override]
        """同 mark（float）。"""
        return cast(float, self._mark)
