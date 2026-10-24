#!/usr/bin/env python3
"""
存储抽象层（Storage Abstraction Layer）— 文档内容对象存储

提供统一的文件存储接口，业务代码不关心底层存储实现：
    - LocalStorage：本地文件系统（开发 / 单机生产默认，锚定服务根 data 目录）
    - S3CompatibleStorage：S3 兼容对象存储（MinIO / 阿里云 OSS / 腾讯 COS / 七牛 Kodo，
      生产环境推荐），经 boto3 访问

通过配置切换实现，业务代码零改动：

    storage:
      provider: "local"        # local | s3

      local:
        base_dir: "./data/documents"     # 相对路径自动锚定 apps/rag-service/data
        public_prefix: "/files"
      s3:
        endpoint_url: "http://minio:9000"
        access_key: ""
        secret_key: ""
        bucket: "qingchuan"
        region: ""
        prefix: "documents"
        public_url: ""          # 可选：公开访问域名（含协议头）
        use_ssl: false

环境变量：STORAGE_PROVIDER / STORAGE_LOCAL_BASE_DIR / STORAGE_S3_*（见 core/config.py）

Usage:
    from qingchuan_rag.infras.storage import get_cached_storage_provider
    provider = get_cached_storage_provider()
    result = provider.upload_file(file_bytes, "documents/xx.txt", content_type="text/plain")
    url = provider.get_download_url("documents/xx.txt")
"""

from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from qingchuan_rag.core.logger import logger
from qingchuan_rag.core.paths import resolve_service_path


# ============================================================
# 统一返回结构
# ============================================================
class UploadResult:
    """上传结果，所有 provider 返回同一结构。"""

    __slots__ = ("key", "url", "size", "storage", "content_type")

    def __init__(
        self,
        key: str,
        url: str,
        size: int,
        storage: str,
        content_type: str = "application/octet-stream",
    ) -> None:
        self.key = key
        self.url = url
        self.size = size
        self.storage = storage
        self.content_type = content_type

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "url": self.url,
            "size": self.size,
            "storage": self.storage,
            "content_type": self.content_type,
        }


# ============================================================
# 抽象基类
# ============================================================
class StorageProvider(ABC):
    """存储提供者抽象接口。

    所有存储后端必须实现此接口；业务层仅依赖此抽象，
    切换存储实现只需修改配置，无需改动任何业务代码。
    """

    #: 存储后端标识（local / s3），供统计与诊断使用
    storage_type: str = "unknown"

    @abstractmethod
    def upload_file(
        self,
        data: bytes | BinaryIO,
        key: str,
        *,
        content_type: str = "application/octet-stream",
    ) -> UploadResult:
        """上传文件。

        Args:
            data: 文件内容（bytes 或可读的文件对象）
            key: 存储路径键，如 "documents/xx.txt"
            content_type: MIME 类型

        Returns:
            UploadResult: 上传结果（含 key、url、size、storage 类型）
        """

    @abstractmethod
    def get_download_url(self, key: str, *, expires: int = 3600) -> str:
        """获取文件下载 URL。

        本地存储返回相对路径（由静态文件中间件服务）；
        S3 兼容存储返回带签名的临时 URL。

        Args:
            key: 存储路径键
            expires: 签名有效期（秒），仅云存储有效

        Returns:
            str: 可访问的 URL 或相对路径
        """

    @abstractmethod
    def delete_file(self, key: str) -> bool:
        """删除文件。

        Args:
            key: 存储路径键

        Returns:
            bool: 删除是否成功
        """

    @abstractmethod
    def file_exists(self, key: str) -> bool:
        """判断文件是否存在。

        Args:
            key: 存储路径键

        Returns:
            bool: 文件是否存在
        """

    def make_object_key(self, folder: str, filename: str) -> str:
        """生成唯一的对象存储键。

        使用 时间戳+SHA1 保证唯一性，避免文件名冲突。

        Args:
            folder: 目录前缀，如 "documents"
            filename: 原始文件名

        Returns:
            str: 唯一的存储键
        """
        safe_name = os.path.basename(filename)
        stem, ext = os.path.splitext(safe_name)
        digest = hashlib.sha1(f"{datetime.now(UTC).isoformat()}:{safe_name}".encode()).hexdigest()[
            :12
        ]
        unique_name = f"{stem}-{digest}{ext}"
        folder_clean = folder.strip("/")
        if folder_clean:
            return f"{folder_clean}/{unique_name}"
        return unique_name


# ============================================================
# 本地文件系统实现
# ============================================================
class LocalStorage(StorageProvider):
    """本地文件系统存储。

    文件保存在服务数据目录（apps/rag-service/data/<base_dir>，相对路径自动锚定），
    适合开发与单机生产；通过 FastAPI StaticFiles 中间件提供静态访问（public_prefix）。
    """

    def __init__(self, base_dir: str = "./data/documents", public_prefix: str = "/files") -> None:
        self.storage_type = "local"
        # 相对路径锚定到服务根目录，避免随 CWD 漂移写入仓库根目录
        self.base_dir = Path(resolve_service_path(base_dir)).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.public_prefix = public_prefix.rstrip("/")
        logger.info(
            f"LocalStorage initialized: base_dir={self.base_dir} public_prefix={self.public_prefix}"
        )

    def upload_file(
        self,
        data: bytes | BinaryIO,
        key: str,
        *,
        content_type: str = "application/octet-stream",
    ) -> UploadResult:
        target = (self.base_dir / key).resolve()
        # 安全检查：防止路径穿越
        try:
            target.relative_to(self.base_dir)
        except ValueError as exc:
            raise ValueError(f"非法的存储路径: {key}") from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            content = data
        else:
            content = data.read()
        target.write_bytes(content)
        url = f"{self.public_prefix}/{key.lstrip('/')}"
        logger.info(f"LocalStorage upload: key={key} size={len(content)}")
        return UploadResult(
            key=key, url=url, size=len(content), storage="local", content_type=content_type
        )

    def get_download_url(self, key: str, *, expires: int = 3600) -> str:
        """返回本地相对路径（由静态文件中间件直接服务）。"""
        return f"{self.public_prefix}/{key.lstrip('/')}"

    def delete_file(self, key: str) -> bool:
        target = (self.base_dir / key).resolve()
        try:
            target.relative_to(self.base_dir)
        except ValueError:
            return False
        if target.is_file():
            target.unlink()
            logger.info(f"LocalStorage deleted: key={key}")
            return True
        return False

    def file_exists(self, key: str) -> bool:
        target = (self.base_dir / key).resolve()
        try:
            target.relative_to(self.base_dir)
        except ValueError:
            return False
        return target.is_file()


# ============================================================
# S3 兼容对象存储实现（MinIO / 阿里云 OSS / 腾讯 COS / 七牛 Kodo）
# ============================================================
class S3CompatibleStorage(StorageProvider):
    """S3 兼容对象存储。

    通过 boto3 调用 S3 兼容 API。需要安装 boto3：uv add boto3
    配置项：
        endpoint_url: S3 兼容服务地址（MinIO / 云厂商 S3 端点）
        access_key:   AccessKey
        secret_key:   SecretKey
        bucket:       存储空间名称
        region:       存储区域（可选，部分实现可留空）
        prefix:       对象键前缀（可选，如 "documents"）
        public_url:   公开访问域名（可选，含协议头，如 https://cdn.example.com）
        use_ssl:      是否使用 HTTPS
    """

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "",
        prefix: str = "",
        public_url: str = "",
        use_ssl: bool = True,
    ) -> None:
        try:
            import boto3
            from botocore.config import Config as BotoConfig
            from botocore.exceptions import ClientError
        except ImportError as exc:
            raise ImportError("S3 兼容存储需要 boto3，请执行: uv pip install boto3") from exc
        self._bucket_name = bucket
        self._region = region
        self.storage_type = "s3"
        self._prefix = prefix.strip("/")
        self._public_url = public_url.rstrip("/") if public_url else ""
        # 构建 S3 客户端
        s3_config = BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
        )
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region or None,
            use_ssl=use_ssl,
            config=s3_config,
        )
        logger.info(
            f"S3CompatibleStorage initialized: bucket={bucket} endpoint={endpoint_url} region={region}"
        )
        # 确保 bucket 存在（幂等；本地 MinIO 与 compose 内置 minio 均无需手动建桶）
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """确保 bucket 存在（幂等创建；失败仅告警不阻断，上传时再明确报错）。

        - 本地调试：D:\\04Docker\\MinIO（默认已建 qingchuan）
        - compose 部署：内置 minio 容器首次启动自动创建
        - 云厂商（OSS/COS/Kodo）：按各自 region 规则创建
        """
        try:
            self._client.head_bucket(Bucket=self._bucket_name)
            logger.info(f"S3CompatibleStorage bucket ready: {self._bucket_name}")
            return
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code not in ("404", "NoSuchBucket"):
                logger.warning(
                    f"S3CompatibleStorage bucket check failed: bucket={self._bucket_name} "
                    f"code={code} error={e}"
                )
                return
        try:
            kwargs: dict[str, Any] = {}
            if self._region:
                kwargs["CreateBucketConfiguration"] = {"LocationConstraint": self._region}
            self._client.create_bucket(Bucket=self._bucket_name, **kwargs)
            logger.info(f"S3CompatibleStorage bucket created: {self._bucket_name}")
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                logger.info(f"S3CompatibleStorage bucket already exists: {self._bucket_name}")
            else:
                logger.warning(
                    f"S3CompatibleStorage bucket create failed: bucket={self._bucket_name} "
                    f"code={code} error={e}"
                )

    def _full_key(self, key: str) -> str:
        """拼接 prefix。"""
        key_clean = key.strip("/")
        if self._prefix:
            return f"{self._prefix}/{key_clean}"
        return key_clean

    def _get_public_url(self, key: str) -> str:
        """获取公开访问 URL（配置了 public_url 时使用，否则返回空，由 get_download_url 出签名 URL）。"""
        if self._public_url:
            return f"{self._public_url}/{key.lstrip('/')}"
        return ""

    def upload_file(
        self,
        data: bytes | BinaryIO,
        key: str,
        *,
        content_type: str = "application/octet-stream",
    ) -> UploadResult:
        full_key = self._full_key(key)
        if not isinstance(data, bytes):
            data = data.read()
        extra_args: dict[str, str] = {"ContentType": content_type}
        self._client.put_object(
            Bucket=self._bucket_name,
            Key=full_key,
            Body=data,
            **extra_args,
        )
        url = self._get_public_url(full_key)
        logger.info(f"S3CompatibleStorage upload: key={full_key} size={len(data)}")
        return UploadResult(
            key=full_key,
            url=url,
            size=len(data),
            storage="s3",
            content_type=content_type,
        )

    def get_download_url(self, key: str, *, expires: int = 3600) -> str:
        """生成带签名的临时下载 URL。"""
        full_key = self._full_key(key)
        url: str = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket_name, "Key": full_key},
            ExpiresIn=expires,
        )
        return url

    def delete_file(self, key: str) -> bool:
        full_key = self._full_key(key)
        try:
            self._client.delete_object(Bucket=self._bucket_name, Key=full_key)
            logger.info(f"S3CompatibleStorage deleted: key={full_key}")
            return True
        except Exception as e:
            logger.warning(f"S3CompatibleStorage delete failed: key={full_key} error={e}")
            return False

    def file_exists(self, key: str) -> bool:
        full_key = self._full_key(key)
        try:
            self._client.head_object(Bucket=self._bucket_name, Key=full_key)
            return True
        except Exception:
            return False


# ============================================================
# 工厂函数
# ============================================================
def get_storage_provider() -> StorageProvider:
    """根据配置创建存储提供者实例（从 settings.storage 读取，自动选择实现）。"""
    from qingchuan_rag.core.config import settings

    storage_cfg = settings.storage
    if storage_cfg.provider == "s3":
        if not all(
            [
                storage_cfg.s3_endpoint_url,
                storage_cfg.s3_access_key,
                storage_cfg.s3_secret_key,
                storage_cfg.s3_bucket,
            ]
        ):
            logger.warning("S3 storage selected but credentials incomplete, falling back to local")
            return LocalStorage(
                base_dir=storage_cfg.base_dir, public_prefix=storage_cfg.public_prefix
            )
        return S3CompatibleStorage(
            endpoint_url=storage_cfg.s3_endpoint_url,
            access_key=storage_cfg.s3_access_key,
            secret_key=storage_cfg.s3_secret_key,
            bucket=storage_cfg.s3_bucket,
            region=storage_cfg.s3_region,
            prefix=storage_cfg.s3_prefix,
            public_url=storage_cfg.s3_public_url,
            use_ssl=storage_cfg.s3_use_ssl,
        )
    # 默认本地存储
    return LocalStorage(base_dir=storage_cfg.base_dir, public_prefix=storage_cfg.public_prefix)


# 模块级缓存，避免每次请求都重新创建（应用级单例）
_provider: StorageProvider | None = None


def get_cached_storage_provider() -> StorageProvider:
    """获取缓存的存储提供者（应用级单例，首次调用创建）。"""
    global _provider
    if _provider is None:
        _provider = get_storage_provider()
    return _provider


def _reset_storage_provider() -> None:
    """重置单例缓存（测试隔离用）。"""
    global _provider
    _provider = None


__all__ = [
    "StorageProvider",
    "LocalStorage",
    "S3CompatibleStorage",
    "UploadResult",
    "get_storage_provider",
    "get_cached_storage_provider",
]
