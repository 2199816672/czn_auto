import ctypes
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Union

import numpy as np


class CaptureMethod(str, Enum):
    """屏幕捕获方式。继承 ``str`` 以便直接序列化到 JSON / 与配置字符串互通。"""

    AUTO = "auto"            # 自动：当前等价于 DXGI（前台）
    DXGI = "dxgi"            # DXGI 桌面复制（dxcam），前台
    FRAMEPOOL = "framepool"  # WinRT FramePool，支持后台/遮挡
    PRINTWINDOW = "printwindow"  # GDI PrintWindow，支持后台/遮挡
    ADB = "adb"              # 安卓设备：经 adb exec-out screencap 截屏

    DEFAULT = "framepool"    # 别名：默认方式（值与 FRAMEPOOL 相同）

    @classmethod
    def normalize(cls, value: "Union[str, CaptureMethod, None]") -> str:
        """把任意输入规整为合法的方式字符串，None/空 取默认值。"""
        if value is None:
            return cls.FRAMEPOOL.value
        if isinstance(value, cls):
            return value.value
        text = str(value).strip().lower()
        return text or cls.FRAMEPOOL.value


def get_window_title(hwnd: int) -> str:
    """根据窗口句柄读取标题文本。"""
    if not hwnd:
        return ""
    try:
        user32 = ctypes.windll.user32
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        return ""


class ScreencapBackend(ABC):
    """屏幕捕获后端抽象基类。

    所有后端统一返回 BGR 格式的 ``np.ndarray``（与 dxcam ``output_color="BGR"`` 一致），
    失败时返回 ``None``，由上层 ``ScreenCapturer`` 兜底。
    """

    name: str = "base"

    # True 表示 grab() 直接返回目标窗口画面（无需再按桌面坐标裁剪）；
    # False 表示返回整块桌面，需要 ScreenCapturer 按窗口矩形裁剪。
    returns_window_only: bool = False

    # True 表示该后端是「设备型」（如 ADB）：grab() 返回设备整屏，
    # 无 Win32 几何，ScreenCapturer 跳过窗口裁剪、直接缩放到基准分辨率。
    is_device: bool = False

    def __init__(self):
        self._hwnd: Optional[int] = None

    def set_window(self, hwnd: int):
        """绑定目标窗口句柄。窗口型后端可在此重建捕获会话。"""
        self._hwnd = hwnd

    @abstractmethod
    def grab(self) -> Optional[np.ndarray]:
        """抓取一帧，返回 BGR 图像或 None。"""
        raise NotImplementedError

    def close(self):
        """释放后端持有的资源。"""
        pass
