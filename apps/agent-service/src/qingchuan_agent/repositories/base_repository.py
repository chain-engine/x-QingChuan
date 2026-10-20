#!/usr/bin/env python3
"""仓储层通用基类（晴川 x-QingChuan，对齐北辰 repositories/base_repository）。

数据访问层职责边界：
    - 只做 ORM 对象与基础类型的增删改查
    - 不写业务判断、不拼业务规则、不读取 Request
    - 返回 ORM 对象或基础类型，由 service 层做业务转换
"""

from __future__ import annotations

from typing import TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from qingchuan_agent.infras.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository[ModelT: Base]:
    """通用 CRUD 仓储基类。

    子类只需声明 model_class，即可获得基础增删改查；
    复杂查询在子类中通过私有方法补充，保持数据流向 api→services→repositories 单向。
    """

    model_class: type[ModelT]

    def __init__(self, session: Session) -> None:
        self._session = session

    # ----------------------------------------------------------
    # 写操作
    # ----------------------------------------------------------

    def add(self, model: ModelT) -> ModelT:
        self._session.add(model)
        return model

    def add_all(self, models: list[ModelT]) -> list[ModelT]:
        self._session.add_all(models)
        return models

    def delete(self, model: ModelT) -> None:
        self._session.delete(model)

    # ----------------------------------------------------------
    # 读操作
    # ----------------------------------------------------------

    def get(self, model_id: int) -> ModelT | None:
        return self._session.get(self.model_class, model_id)

    def first(self, *where_clauses: object, order_by: object | None = None) -> ModelT | None:
        stmt: Select = select(self.model_class).where(*where_clauses)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        return self._session.scalar(stmt.limit(1))

    def list(
        self,
        *where_clauses: object,
        order_by: object | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[ModelT]:
        stmt: Select = select(self.model_class).where(*where_clauses)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        return list(self._session.scalars(stmt.offset(offset).limit(limit)).all())

    def count(self, *where_clauses: object) -> int:
        stmt = select(func.count()).select_from(self.model_class).where(*where_clauses)
        return int(self._session.scalar(stmt) or 0)

    # ----------------------------------------------------------
    # 会话
    # ----------------------------------------------------------

    def commit(self) -> None:
        self._session.commit()

    def refresh(self, model: ModelT) -> ModelT:
        self._session.refresh(model)
        return model


__all__ = ["BaseRepository"]
