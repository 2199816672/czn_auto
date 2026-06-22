import ctypes
import logging
from ctypes import wintypes
from typing import Optional

import numpy as np

from .base import ScreencapBackend

PW_RENDERFULLCONTENT = 0x00000002
BI_RGB = 0
DIB_RGB_COLORS = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def _setup_gdi():
    """配置 ctypes 函数签名，避免 64 位句柄被截断为 32 位。"""
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    user32.GetWindowDC.restype = wintypes.HDC
    user32.GetWindowDC.argtypes = [wintypes.HWND]
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    user32.PrintWindow.restype = wintypes.BOOL

    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.GetDIBits.argtypes = [
        wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
        ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT,
    ]
    gdi32.GetDIBits.restype = ctypes.c_int
    return user32, gdi32


class PrintWindowBackend(ScreencapBackend):
    """基于 GDI ``PrintWindow`` 的窗口捕获。

    让窗口把自身内容绘制到离屏 DC，**窗口被遮挡 / 后台时仍可截图**。
    使用 ``PW_RENDERFULLCONTENT`` 标志以兼容 DWM/DirectComposition 渲染；
    但部分纯 D3D 全屏渲染的画面可能截到黑屏。
    """

    name = "printwindow"
    returns_window_only = True

    def __init__(self):
        super().__init__()
        self._user32, self._gdi32 = _setup_gdi()

    def grab(self) -> Optional[np.ndarray]:
        hwnd = self._hwnd
        if not hwnd:
            return None
        user32, gdi32 = self._user32, self._gdi32

        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w <= 0 or h <= 0:
            return None

        hwnd_dc = user32.GetWindowDC(hwnd)
        mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
        bmp = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
        old = gdi32.SelectObject(mem_dc, bmp)
        try:
            ok = user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)

            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = w
            bmi.bmiHeader.biHeight = -h  # 负值 = 自上而下
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = BI_RGB

            buffer = (ctypes.c_ubyte * (w * h * 4))()
            scanned = gdi32.GetDIBits(
                mem_dc, bmp, 0, h, buffer, ctypes.byref(bmi), DIB_RGB_COLORS
            )
            if not scanned:
                logging.warning("PrintWindow: GetDIBits 失败")
                return None
            if not ok:
                logging.debug("PrintWindow 返回 0（部分窗口仍可得到画面）")

            img = np.frombuffer(buffer, dtype=np.uint8).reshape((h, w, 4))
            return np.ascontiguousarray(img[:, :, :3])  # BGRA -> BGR
        finally:
            gdi32.SelectObject(mem_dc, old)
            gdi32.DeleteObject(bmp)
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(hwnd, hwnd_dc)
