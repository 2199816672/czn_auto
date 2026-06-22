"""屏幕捕获后端。

通过 ``create_backend(method)`` 按名称获取具体实现：

- ``auto`` / ``dxgi``  : DXGI 桌面复制（dxcam），最快，前台；被遮挡/最小化会失败
- ``framepool``        : WinRT Graphics Capture，支持后台/遮挡/伪最小化（需 windows-capture）
- ``printwindow``      : GDI PrintWindow，支持后台/遮挡（部分 D3D 画面可能黑屏）
"""
import logging
from typing import Union

from .base import CaptureMethod, ScreencapBackend, get_window_title
from .dxgi import DXGIBackend

__all__ = [
    "ScreencapBackend",
    "CaptureMethod",
    "create_backend",
    "get_window_title",
    "AVAILABLE_METHODS",
    "ScreenCapturer",
]

# 供 GUI 下拉框使用：内部值 -> 显示名
AVAILABLE_METHODS = {
    CaptureMethod.FRAMEPOOL.value: "FramePool (后台/遮挡可截, 默认)",
    CaptureMethod.PRINTWINDOW.value: "PrintWindow (后台/遮挡可截)",
    CaptureMethod.AUTO.value: "自动 (DXGI 前台)",
}


def create_backend(method: "Union[str, CaptureMethod, None]") -> ScreencapBackend:
    """根据方式名创建捕获后端，失败时回退到 DXGI。"""
    method = CaptureMethod.normalize(method)

    if method == CaptureMethod.FRAMEPOOL.value:
        try:
            from .framepool import FramePoolBackend
            return FramePoolBackend()
        except Exception as e:
            logging.error(f"FramePool 后端不可用，回退到 DXGI: {e}")
            return DXGIBackend()

    if method == CaptureMethod.PRINTWINDOW.value:
        try:
            from .printwindow import PrintWindowBackend
            return PrintWindowBackend()
        except Exception as e:
            logging.error(f"PrintWindow 后端不可用，回退到 DXGI: {e}")
            return DXGIBackend()

    # auto / dxgi / 其它
    return DXGIBackend()


# 末尾导入避免与 create_backend 形成循环导入
from .capturer import ScreenCapturer  # noqa: E402
