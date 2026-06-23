#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""窗口目标发现抽象层。

把「到底要操作哪个窗口」从散落的 ``FindWindowW(None, 标题)`` 调用里抽出来，
统一成「提供者(provider) 发现一批候选窗口(WindowTarget)」的面向对象模型，
方便后续接入模拟器（雷电/MuMu 等各自一个 provider），见 ``core/window/__init__.py``。
"""
import ctypes
from abc import ABC, abstractmethod
from ctypes import wintypes
from dataclasses import dataclass
from typing import List, Tuple

user32 = ctypes.windll.user32


@dataclass(frozen=True)
class WindowTarget:
    """一个可被绑定的目标窗口。

    - ``hwnd``: Win32 窗口句柄（运行期有效，重启后会变，不应持久化）。
    - ``title``: 窗口标题文本（用于持久化与重新定位）。
    - ``provider_key`` / ``provider_label``: 来源提供者的标识与中文显示名。
    """

    hwnd: int
    title: str
    provider_key: str
    provider_label: str

    @property
    def display(self) -> str:
        """下拉框展示用文本：``标题 · 来源``。"""
        return f"{self.title} · {self.provider_label}"


# WNDENUMPROC 回调签名：BOOL CALLBACK(HWND, LPARAM)
_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def get_window_title(hwnd: int) -> str:
    """读取窗口标题文本，失败返回空串。"""
    if not hwnd:
        return ""
    try:
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        return ""


def enum_top_windows() -> List[Tuple[int, str]]:
    """枚举所有「可见且有标题」的顶层窗口，返回 ``[(hwnd, title), ...]``。"""
    results: List[Tuple[int, str]] = []

    def _cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = get_window_title(hwnd)
        if title:
            results.append((int(hwnd), title))
        return True

    try:
        user32.EnumWindows(_WNDENUMPROC(_cb), 0)
    except Exception:
        pass
    return results


def find_window_by_title(title: str) -> int:
    """按窗口标题精确查找顶层窗口句柄，未找到返回 0（兜底用）。"""
    if not title:
        return 0
    return user32.FindWindowW(None, title) or 0


class WindowProvider(ABC):
    """窗口目标提供者抽象基类。

    每个提供者负责「发现一类目标窗口」：游戏窗口、某品牌模拟器……
    子类只需声明 ``key``/``label`` 并实现 :meth:`discover`。
    """

    key: str = "base"
    label: str = "窗口"

    @abstractmethod
    def discover(self) -> List[WindowTarget]:
        """枚举当前系统中属于本提供者的目标窗口。"""
        raise NotImplementedError
