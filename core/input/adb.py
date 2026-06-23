#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ADB 输入后端：经 ``adb shell input tap`` 在安卓设备上点击。

坐标体系：``click(x, y)`` 收到的已是 worker 经 ``ScreenCapturer.game_to_screen``
转换出的**设备像素**坐标，直接交给 adb tap。本后端不依赖窗口句柄，靠
device serial 绑定（``set_device``）。
"""
import logging

from core import adb

from .base import InputBackend


class AdbInputBackend(InputBackend):
    """安卓设备输入后端（adb tap）。"""

    name = "adb"
    needs_window = False  # 用 device serial 绑定，无需窗口句柄

    def __init__(self):
        super().__init__()
        self._serial: str = ""

    def set_device(self, serial: str):
        """绑定目标设备 serial。"""
        self._serial = serial or ""
        if self._serial:
            logging.info(f"ADB 输入已绑定设备: {self._serial}")

    def click(self, x: int, y: int, screen_w: int = 1920, screen_h: int = 1080):
        if not self._serial:
            logging.warning("ADB 输入后端未绑定设备，点击被忽略")
            return
        adb.tap(self._serial, x, y)
