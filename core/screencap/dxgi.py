import logging
from typing import Optional

import numpy as np

from .base import ScreencapBackend


class DXGIBackend(ScreencapBackend):
    """基于 dxcam 的 DXGI 桌面复制（Desktop Duplication）。

    速度极快，但抓取的是显示器最终合成画面：游戏窗口被遮挡 / 最小化时会失败。
    返回整块桌面，由 ScreenCapturer 按窗口矩形裁剪。
    """

    name = "dxgi"
    returns_window_only = False

    def __init__(self):
        super().__init__()
        self.camera = self._create_camera()

    def _create_camera(self):
        try:
            import dxcam
            return dxcam.create(output_color="BGR")
        except Exception as e:
            logging.error(f"创建 dxcam 失败: {e}")
            return None

    def grab(self) -> Optional[np.ndarray]:
        if self.camera is None:
            self.camera = self._create_camera()
            if self.camera is None:
                return None
        img = self.camera.grab()
        if img is None:
            img = self.camera.grab()
        if img is None:
            logging.warning("DXGI 截图失败，重建 dxcam 实例")
            self.close()
            return None
        return img

    def close(self):
        if self.camera is not None:
            try:
                self.camera.stop()
            except Exception:
                pass
            try:
                del self.camera
            except Exception:
                pass
        self.camera = None
