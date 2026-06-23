#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ADB 设备提供者：通过 ``adb devices`` 发现已连接的安卓设备/模拟器。

每个在线设备产出一个 ``WindowTarget``：``hwnd=0``（无窗口句柄），``title`` 与
``device_id`` 均为设备 serial。运行期截屏/点击改用 serial 绑定，不走 Win32 句柄。
"""
from typing import List

from core import adb

from .base import WindowProvider, WindowTarget


class AdbDeviceProvider(WindowProvider):
    """ADB 设备来源（安卓真机 / 模拟器，经 USB 或 TCP 连接）。"""

    key = "adb"
    label = "ADB设备"

    def discover(self) -> List[WindowTarget]:
        targets: List[WindowTarget] = []
        for serial in adb.list_devices():
            targets.append(
                WindowTarget(
                    hwnd=0,
                    title=serial,
                    provider_key=self.key,
                    provider_label=self.label,
                    device_id=serial,
                )
            )
        return targets
