#!/usr/bin/env python3
"""
HTTP 客户端基础设施模块
本模块提供通用的 HTTP 请求客户端封装，支持 GET、POST、PUT、DELETE 等方法。
功能特性：
    - 统一的 HTTP 请求封装
    - 超时配置
    - 请求/响应日志记录
    - 错误重试机制
    - JSON 响应自动解析

Usage:
    from src.infras.http import get_cached_http_provider
    client = get_cached_http_provider()
    response = client.get("https://api.example.com/users")
"""

from __future__ import annotations

import json as _json
import time
from abc import ABC, abstractmethod
from typing import Any

import requests
from requests import Response, Session

from qingchuan_rag.core.logger import logger


# ============================================================
# 抽象基类
# ============================================================
class HttpProvider(ABC):
    """HTTP 客户端抽象接口。
    所有 HTTP 客户端后端必须实现此接口。业务层仅依赖此抽象，
    切换 HTTP 实现只需修改配置，无需改动任何业务代码。
    """

    @abstractmethod
    def get(self, url: str, params: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        """发送 GET 请求。"""

    @abstractmethod
    def post(
        self, url: str, data: dict[str, Any] | None = None, json: dict[str, Any] | None = None, **kwargs: Any
    ) -> Any:
        """发送 POST 请求。"""

    @abstractmethod
    def put(
        self, url: str, data: dict[str, Any] | None = None, json: dict[str, Any] | None = None, **kwargs: Any
    ) -> Any:
        """发送 PUT 请求。"""

    @abstractmethod
    def delete(self, url: str, **kwargs: Any) -> Any:
        """发送 DELETE 请求。"""


# ============================================================
# requests 实现
# ============================================================


class RequestsHttpProvider(HttpProvider):
    """基于 requests 库的 HTTP 客户端实现。
    提供统一的 HTTP 请求封装，支持常见的 HTTP 方法和错误处理。

    Attributes:
        session: requests Session 对象
        timeout: 请求超时时间（秒）
        retries: 重试次数
    """

    def __init__(
        self,
        timeout: int = 30,
        retries: int = 3,
        base_url: str | None = None,
    ) -> None:
        """初始化 HTTP 客户端。

        Args:
            timeout: 请求超时时间（秒）
            retries: 重试次数
            base_url: 基础 URL，请求时会自动拼接
        """
        self.session: Session = requests.Session()
        self.timeout: int = timeout
        self.retries: int = retries
        self.base_url: str | None = base_url

    def _build_url(self, url: str) -> str:
        """构建完整的请求 URL。

        Args:
            url: 相对或绝对 URL

        Returns:
            str: 完整的请求 URL
        """
        if self.base_url and not url.startswith("http"):
            return f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"
        return url

    def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Response:
        """底层请求方法，处理重试逻辑。

        Args:
            method: HTTP 方法
            url: 请求 URL
            **kwargs: 请求参数

        Returns:
            Response: HTTP 响应对象

        Raises:
            requests.RequestException: 请求失败时抛出
        """
        full_url: str = self._build_url(url)
        headers: dict[str, str] = kwargs.get("headers", {})
        if "Content-Type" not in headers and kwargs.get("json") is not None:
            headers["Content-Type"] = "application/json"
        kwargs["headers"] = headers
        for attempt in range(self.retries):
            try:
                logger.debug(f"HTTP {method} request: {full_url}, attempt: {attempt + 1}")
                response: Response = self.session.request(
                    method=method,
                    url=full_url,
                    timeout=self.timeout,
                    **kwargs,
                )
                response.raise_for_status()
                logger.debug(f"HTTP {method} response: {full_url}, status: {response.status_code}")
                return response
            except requests.RequestException as e:
                logger.warning(f"HTTP {method} request failed: {full_url}, attempt: {attempt + 1}, error: {e}")
                if attempt < self.retries - 1:
                    time.sleep(2**attempt)
                else:
                    raise
        raise requests.RequestException(f"HTTP {method} request failed after {self.retries} attempts: {full_url}")

    def get(self, url: str, params: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        """发送 GET 请求。

        Args:
            url: 请求 URL
            params: 查询参数
            **kwargs: 其他请求参数

        Returns:
            Any: 响应数据（JSON 解析后）

        Raises:
            requests.RequestException: 请求失败时抛出
        """
        response: Response = self._request("GET", url, params=params, **kwargs)
        try:
            return response.json()
        except _json.JSONDecodeError:
            return response.text

    def post(
        self, url: str, data: dict[str, Any] | None = None, json: dict[str, Any] | None = None, **kwargs: Any
    ) -> Any:
        """发送 POST 请求。

        Args:
            url: 请求 URL
            data: 表单数据
            json: JSON 数据
            **kwargs: 其他请求参数

        Returns:
            Any: 响应数据（JSON 解析后）

        Raises:
            requests.RequestException: 请求失败时抛出
        """
        response: Response = self._request("POST", url, data=data, json=json, **kwargs)
        try:
            return response.json()
        except _json.JSONDecodeError:
            return response.text

    def put(
        self, url: str, data: dict[str, Any] | None = None, json: dict[str, Any] | None = None, **kwargs: Any
    ) -> Any:
        """发送 PUT 请求。

        Args:
            url: 请求 URL
            data: 表单数据
            json: JSON 数据
            **kwargs: 其他请求参数

        Returns:
            Any: 响应数据（JSON 解析后）

        Raises:
            requests.RequestException: 请求失败时抛出
        """
        response: Response = self._request("PUT", url, data=data, json=json, **kwargs)
        try:
            return response.json()
        except _json.JSONDecodeError:
            return response.text

    def delete(self, url: str, **kwargs: Any) -> Any:
        """发送 DELETE 请求。

        Args:
            url: 请求 URL
            **kwargs: 其他请求参数

        Returns:
            Any: 响应数据（JSON 解析后）

        Raises:
            requests.RequestException: 请求失败时抛出
        """
        response: Response = self._request("DELETE", url, **kwargs)
        try:
            return response.json()
        except _json.JSONDecodeError:
            return response.text

    def close(self) -> None:
        """关闭 HTTP 会话。"""
        self.session.close()


# ============================================================
# 工厂函数
# ============================================================


def get_http_provider(**kwargs: Any) -> HttpProvider:
    """创建 HTTP 客户端实例。"""
    return RequestsHttpProvider(**kwargs)


# 模块级缓存实例
_http_provider: HttpProvider | None = None


def get_cached_http_provider(**kwargs: Any) -> HttpProvider:
    """获取缓存的 HTTP 客户端（应用级别单例）。"""
    global _http_provider
    if _http_provider is None:
        _http_provider = get_http_provider(**kwargs)
    return _http_provider


__all__ = [
    "HttpProvider",
    "RequestsHttpProvider",
    "get_http_provider",
    "get_cached_http_provider",
]
