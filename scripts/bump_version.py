#!/usr/bin/env python3
"""晴川（x-QingChuan）workspace 单版本号发版脚本。

VERSION 文件是仓库唯一的版本事实源；本脚本负责把该版本号
联动写入 workspace 内全部 pyproject.toml、各包 __init__.__version__
与服务运行时常量 constants.APP_VERSION（/health 对外暴露的版本号），
避免 domain / common / rag / agent 版本漂移。

用法：
    uv run python scripts/bump_version.py            # 按 VERSION 对齐（幂等）
    uv run python scripts/bump_version.py 0.3.0      # 指定新版本：更新 VERSION 后对齐

校验：
    uv run python scripts/bump_version.py --check    # 检查是否一致（CI 可接入）
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"

# 需要同步 version 的 pyproject.toml（根 workspace + 成员包）
PYPROJECT_TARGETS = [
    ROOT / "pyproject.toml",
    ROOT / "packages" / "domain" / "pyproject.toml",
    ROOT / "packages" / "common" / "pyproject.toml",
    ROOT / "apps" / "rag-service" / "pyproject.toml",
    ROOT / "apps" / "agent-service" / "pyproject.toml",
]

# 需要同步 __version__ 的包入口（存在性按需保留）
INIT_TARGETS = [
    ROOT / "packages" / "domain" / "src" / "qingchuan_domain" / "__init__.py",
    ROOT / "packages" / "common" / "src" / "qingchuan_common" / "__init__.py",
    ROOT / "apps" / "rag-service" / "src" / "qingchuan_rag" / "__init__.py",
    ROOT / "apps" / "agent-service" / "src" / "qingchuan_agent" / "__init__.py",
]

# 需要同步 APP_VERSION 的服务运行时常量（/health 与 FastAPI app 初始化读取）
CONSTANTS_TARGETS = [
    ROOT / "apps" / "agent-service" / "src" / "qingchuan_agent" / "constants" / "constants.py",
    ROOT / "apps" / "rag-service" / "src" / "qingchuan_rag" / "constants" / "constants.py",
]

_PYPROJECT_RE = re.compile(r'^(version\s*=\s*")([^"]*)(")', re.MULTILINE)
_INIT_RE = re.compile(r'(__version__\s*=\s*")([^"]*)(")')
_CONSTANTS_RE = re.compile(r'^(APP_VERSION:\s*str\s*=\s*")([^"]*)(")', re.MULTILINE)


def read_version() -> str:
    """读取 VERSION 文件（去除首尾空白）。"""
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not version:
        raise RuntimeError(f"{VERSION_FILE} 为空，无法作为版本事实源")
    return version


def write_version(version: str) -> None:
    """写入 VERSION 文件（保留单个换行）。"""
    VERSION_FILE.write_text(f"{version}\n", encoding="utf-8")


def sync_pyproject(version: str) -> list[Path]:
    """把 version 写入全部 pyproject.toml，返回实际改动文件。"""
    changed: list[Path] = []
    for path in PYPROJECT_TARGETS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        new_text, count = _PYPROJECT_RE.subn(rf"\g<1>{version}\g<3>", text, count=1)
        if count and new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed.append(path)
    return changed


def sync_init(version: str) -> list[Path]:
    """把 __version__ 写入各包 __init__.py（不存在该行则追加），返回实际改动文件。"""
    changed: list[Path] = []
    for path in INIT_TARGETS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if _INIT_RE.search(text):
            new_text, count = _INIT_RE.subn(rf"\g<1>{version}\g<3>", text, count=1)
            if count and new_text != text:
                path.write_text(new_text, encoding="utf-8")
                changed.append(path)
        else:
            # 无 __version__ 的包入口（如 agent）：在末尾追加，保证一致性
            with path.open("a", encoding="utf-8") as fh:
                fh.write(f'\n__version__ = "{version}"\n')
            changed.append(path)
    return changed


def sync_constants(version: str) -> list[Path]:
    """把 version 写入各服务 constants.APP_VERSION，返回实际改动文件。"""
    changed: list[Path] = []
    for path in CONSTANTS_TARGETS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        new_text, count = _CONSTANTS_RE.subn(rf"\g<1>{version}\g<3>", text, count=1)
        if count and new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed.append(path)
    return changed


def check_consistency() -> list[str]:
    """检查全部目标是否与 VERSION 一致，返回不一致项描述。"""
    expected = read_version()
    issues: list[str] = []
    for path in PYPROJECT_TARGETS:
        if not path.exists():
            continue
        match = _PYPROJECT_RE.search(path.read_text(encoding="utf-8"))
        if match is None or match.group(2) != expected:
            issues.append(f"{path.relative_to(ROOT)} 的 version 与 VERSION 不一致")
    for path in INIT_TARGETS:
        if not path.exists():
            continue
        match = _INIT_RE.search(path.read_text(encoding="utf-8"))
        if match is None or match.group(2) != expected:
            issues.append(f"{path.relative_to(ROOT)} 的 __version__ 与 VERSION 不一致")
    for path in CONSTANTS_TARGETS:
        if not path.exists():
            continue
        match = _CONSTANTS_RE.search(path.read_text(encoding="utf-8"))
        if match is None or match.group(2) != expected:
            issues.append(f"{path.relative_to(ROOT)} 的 APP_VERSION 与 VERSION 不一致")
    return issues


def main() -> int:
    args = sys.argv[1:]
    if "--check" in args:
        issues = check_consistency()
        if issues:
            print("版本不一致：")
            for issue in issues:
                print(f"  - {issue}")
            return 1
        print(f"版本一致（VERSION={read_version()}）")
        return 0

    if args:
        version = args[0]
        if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version):
            print(f"非法版本号：{version!r}（应为 X.Y.Z）")
            return 2
        write_version(version)
        print(f"VERSION 更新为 {version}")
    else:
        version = read_version()
        print(f"按 VERSION（{version}）对齐")

    changed_py = sync_pyproject(version)
    changed_init = sync_init(version)
    changed_constants = sync_constants(version)
    for path in changed_py:
        print(f"  updated pyproject: {path.relative_to(ROOT)}")
    for path in changed_init:
        print(f"  updated __init__:  {path.relative_to(ROOT)}")
    for path in changed_constants:
        print(f"  updated constants: {path.relative_to(ROOT)}")
    if not changed_py and not changed_init and not changed_constants:
        print("已一致，无改动")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
