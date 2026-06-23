#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""窗口目标发现包。

设计要点：目标窗口**不进 config**。三个固定游戏标题写在
:class:`GameWindowProvider` 里；用户每次打开应用在首页选一次，选择即作为
**进程内的全局状态**（见 :func:`select_window` / :func:`resolve_hwnd`），
运行/采集/诊断/点击统一读取这个全局选中窗口，进程退出即失效。

对外提供：
- ``discover_windows()``: 跨所有提供者枚举当前候选窗口（首页下拉用）。
- ``select_window(target)`` / ``get_selected()``: 设置/读取进程全局选中窗口。
- ``resolve_hwnd()``: 解析当前应使用的窗口句柄（句柄失效自动按标题重定位，
  未选择时兜底取第一个候选）。
- ``register_provider()`` / ``available_providers()``: 注册/列出提供者，未来接模拟器在此扩展。

新增模拟器：新建 ``core/window/<brand>.py`` 继承 :class:`WindowProvider` 实现
``discover()``，然后在下方 ``_PROVIDERS`` 注册即可。
"""
from typing import List, Optional

from .base import (
    WindowProvider,
    WindowTarget,
    enum_top_windows,
    find_window_by_title,
    get_window_title,
    user32,
)
from .adb import AdbDeviceProvider
from .game import GameWindowProvider

__all__ = [
    "WindowProvider",
    "WindowTarget",
    "GameWindowProvider",
    "AdbDeviceProvider",
    "register_provider",
    "available_providers",
    "discover_windows",
    "select_window",
    "get_selected",
    "get_selected_device",
    "resolve_hwnd",
    "enum_top_windows",
    "get_window_title",
    "find_window_by_title",
]

# 注册表：顺序即优先级（首页下拉展示顺序、兜底优先级）
_PROVIDERS: List[WindowProvider] = [
    GameWindowProvider(),
    AdbDeviceProvider(),
]

# 进程全局选中窗口（不持久化，退出即失效）
_selected: Optional[WindowTarget] = None


def register_provider(provider: WindowProvider) -> None:
    """注册一个窗口提供者（去重按 key）。"""
    if any(p.key == provider.key for p in _PROVIDERS):
        return
    _PROVIDERS.append(provider)


def available_providers() -> List[WindowProvider]:
    """返回已注册的提供者列表（副本）。"""
    return list(_PROVIDERS)


def discover_windows() -> List[WindowTarget]:
    """跨所有提供者发现候选窗口/设备，去重。

    去重键含来源与设备 id：窗口型靠 hwnd 唯一，ADB 设备 hwnd 恒为 0、靠 device_id 区分。
    """
    out: List[WindowTarget] = []
    seen = set()
    for provider in _PROVIDERS:
        try:
            for target in provider.discover():
                key = (target.provider_key, target.hwnd, target.device_id)
                if key in seen:
                    continue
                seen.add(key)
                out.append(target)
        except Exception:
            continue
    return out


def select_window(target: Optional[WindowTarget]) -> None:
    """设置进程全局选中窗口（首页选择时调用）。"""
    global _selected
    _selected = target


def get_selected() -> Optional[WindowTarget]:
    """返回当前进程全局选中窗口（未选择返回 None）。"""
    return _selected


def get_selected_device() -> Optional[str]:
    """返回当前选中的 ADB 设备 serial；非 adb 来源或未选择返回 None。"""
    if _selected is not None and _selected.provider_key == "adb":
        return _selected.device_id or None
    return None


def _is_window(hwnd: int) -> bool:
    try:
        return bool(hwnd) and bool(user32.IsWindow(hwnd))
    except Exception:
        return False


def resolve_hwnd() -> int:
    """解析当前应使用的窗口句柄，未找到返回 0。

    1. 已有全局选择且句柄仍有效 → 直接返回；
    2. 句柄失效（窗口重开 hwnd 变化）→ 按标题(+提供者)在候选里重定位并刷新全局；
    3. 从未选择（直接运行 / CLI）→ 兜底取第一个候选并记为全局选择。
    """
    global _selected
    if _selected is not None and _is_window(_selected.hwnd):
        return _selected.hwnd

    candidates = discover_windows()
    if _selected is not None:
        for target in candidates:
            if target.title == _selected.title and target.provider_key == _selected.provider_key:
                _selected = target
                return target.hwnd
        for target in candidates:
            if target.title == _selected.title:
                _selected = target
                return target.hwnd
        return 0

    if candidates:
        _selected = candidates[0]
        return candidates[0].hwnd
    return 0
