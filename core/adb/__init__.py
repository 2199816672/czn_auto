#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ADB 调用包：内置 adb.exe 的统一封装。

对外导出底层函数，供 ``core/window``（设备发现）、``core/input``（点击）、
``core/screencap``（截屏）三处复用：

- ``adb_path()``       : 定位内置 adb.exe
- ``list_devices()``   : 枚举在线设备 serial
- ``screencap(serial)``: 截屏 -> BGR ndarray
- ``tap(serial, x, y)``: 模拟点击
"""
from .client import adb_path, list_devices, run, screencap, tap

__all__ = [
    "adb_path",
    "list_devices",
    "run",
    "screencap",
    "tap",
]
