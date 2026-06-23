#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ADB 截屏后端：经 ``adb exec-out screencap -p`` 抓取安卓设备屏幕。

``grab()`` 返回设备原生分辨率 BGR 帧，并缓存设备尺寸（``device_size``）供
``ScreenCapturer.game_to_screen`` 把基准坐标映射回设备像素。本后端为「设备型」
（``is_device=True``）：无 Win32 几何，门面跳过窗口裁剪、统一缩放到 1920x1080。
"""
import logging
from typing import Optional, Tuple

import numpy as np

from core import adb

from .base import ScreencapBackend


class AdbScreencapBackend(ScreencapBackend):
    """安卓设备截屏后端（adb screencap）。"""

    name = "adb"
    is_device = True

    def __init__(self):
        super().__init__()
        self._serial: str = ""
        # 最近一帧的设备分辨率 (w, h)，供坐标映射使用
        self.device_size: Optional[Tuple[int, int]] = None

    def set_device(self, serial: str):
        """绑定目标设备 serial。"""
        self._serial = serial or ""
        if self._serial:
            logging.info(f"ADB 截屏已绑定设备: {self._serial}")

    def grab(self) -> Optional[np.ndarray]:
        if not self._serial:
            return None
        frame = adb.screencap(self._serial)
        if frame is None:
            return None
        self.device_size = (frame.shape[1], frame.shape[0])
        return frame
