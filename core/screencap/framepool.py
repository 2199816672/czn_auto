import logging
import threading
import time
from typing import Optional

import numpy as np

from .base import ScreencapBackend, get_window_title


class FramePoolBackend(ScreencapBackend):
    """基于 WinRT Windows.Graphics.Capture（FramePool）的窗口捕获。

    依赖 ``windows-capture`` 包。直接抓取目标窗口的渲染输出，**窗口被遮挡、
    位于后台甚至最小化时仍可截图**（伪最小化）。需要 Windows 10 1903+。

    该库为事件驱动：在后台线程持续接收帧，本类缓存最新一帧，``grab()`` 返回缓存。
    """

    name = "framepool"
    returns_window_only = True

    def __init__(self):
        super().__init__()
        # 导入失败会抛出，交由工厂兜底回退到 DXGI
        from windows_capture import WindowsCapture
        self._WindowsCapture = WindowsCapture
        self._title: Optional[str] = None
        self._control = None
        self._latest: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._started = False

    def set_window(self, hwnd: int):
        super().set_window(hwnd)
        self._title = get_window_title(hwnd) or None
        self._restart()

    def _restart(self):
        self.close()
        try:
            self._start()
        except Exception as e:
            logging.error(f"FramePool 启动失败: {e}")

    def _start(self):
        if self._title:
            cap = self._WindowsCapture(
                cursor_capture=False, draw_border=False, window_name=self._title
            )
        else:
            # 未绑定窗口时退化为主显示器捕获
            cap = self._WindowsCapture(
                cursor_capture=False, draw_border=False, monitor_index=1
            )

        @cap.event
        def on_frame_arrived(frame, capture_control):
            try:
                buf = frame.frame_buffer  # (H, W, 4) BGRA，可能含行填充
                h, w = frame.height, frame.width
                img = np.ascontiguousarray(buf[:h, :w, :3])  # BGRA -> BGR
                with self._lock:
                    self._latest = img
            except Exception:
                pass

        @cap.event
        def on_closed():
            pass

        self._control = cap.start_free_threaded()
        self._started = True

    def grab(self) -> Optional[np.ndarray]:
        if not self._started:
            try:
                self._start()
            except Exception as e:
                logging.error(f"FramePool 启动失败: {e}")
                return None
        # 等待首帧到达（最多 1s）
        deadline = time.time() + 1.0
        while time.time() < deadline:
            with self._lock:
                if self._latest is not None:
                    return self._latest.copy()
            time.sleep(0.01)
        with self._lock:
            return self._latest.copy() if self._latest is not None else None

    def close(self):
        if self._control is not None:
            try:
                self._control.stop()
            except Exception:
                pass
        self._control = None
        self._started = False
        with self._lock:
            self._latest = None
