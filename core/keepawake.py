#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行时防锁屏 / 防休眠。

通过 Windows ``SetThreadExecutionState`` 告知系统"任务进行中"，从而阻止显示器
自动关闭、屏保启动与系统睡眠（覆盖绝大多数"自动锁屏"场景）。状态随调用线程
持续生效，线程退出或显式 ``disable()`` 后恢复，因此应在状态机所在线程内启用。

注意：无法绕过由组策略强制的"无操作即锁定"或 Win+L 手动锁屏。
"""
import ctypes
import logging

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

try:
    _set_state = ctypes.windll.kernel32.SetThreadExecutionState
    _set_state.argtypes = [ctypes.c_uint]
    _set_state.restype = ctypes.c_uint
except (AttributeError, OSError):  # 非 Windows / 无 kernel32
    _set_state = None


class KeepAwake:
    """运行时防锁屏开关。

    ``enable()`` 持续保持显示器/系统唤醒，``disable()`` 恢复系统默认电源策略。
    可作为上下文管理器使用：``with KeepAwake(): ...``。重复调用安全（幂等）。
    """

    def __init__(self, keep_display: bool = True):
        self.keep_display = keep_display
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def enable(self) -> bool:
        if self._active:
            return True
        if _set_state is None:
            logging.warning("防锁屏不可用（非 Windows 或缺少 kernel32）")
            return False
        flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        if self.keep_display:
            flags |= ES_DISPLAY_REQUIRED
        if _set_state(flags) == 0:
            logging.warning("防锁屏启用失败（SetThreadExecutionState 返回 0）")
            return False
        self._active = True
        logging.info("已启用运行时防锁屏（阻止显示器休眠/屏保）")
        return True

    def disable(self) -> None:
        if not self._active or _set_state is None:
            self._active = False
            return
        _set_state(ES_CONTINUOUS)
        self._active = False
        logging.info("已关闭运行时防锁屏，恢复系统电源策略")

    def __enter__(self) -> "KeepAwake":
        self.enable()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.disable()
