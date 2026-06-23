import ctypes
import ctypes.wintypes
import logging
from typing import Tuple

import cv2
import numpy as np

from .base import CaptureMethod
from . import create_backend


class ScreenCapturer:
    """屏幕捕获门面（facade）。

    自身不实现截图算法，按 ``method`` 选择 ``core/screencap`` 下的后端：
    桌面型后端（DXGI）抓整屏后按窗口矩形裁剪；窗口型后端（FramePool/PrintWindow）
    直接返回窗口画面。对外 API 保持不变，向后兼容历史调用方。
    """

    BASE_W, BASE_H = 1920, 1080

    def __init__(self, method=CaptureMethod.DEFAULT):
        self.method = CaptureMethod.normalize(method)
        self.backend = create_backend(self.method)
        self.last_resolution = (self.BASE_W, self.BASE_H)
        self._hwnd = None

        actual = self.backend.name
        fell_back = (
            self.method in (CaptureMethod.FRAMEPOOL.value, CaptureMethod.PRINTWINDOW.value)
            and actual != self.method
        )
        if fell_back:
            logging.warning(f"屏幕捕获: 请求方式 '{self.method}' 不可用，已回退到 '{actual}'")
        else:
            logging.info(f"屏幕捕获方式: {self.method} (后端: {actual})")

    def set_window(self, hwnd: int):
        self._hwnd = hwnd
        self.backend.set_window(hwnd)

    def _query_geometry(self):
        """实时查询窗口几何，不缓存（拖动/缩放后立即生效）。

        返回 ``(win_rect, client_rect, client_size)``；无窗口或查询失败时返回
        ``(None, None, None)``。``win_rect``/``client_rect`` 为屏幕坐标的
        ``(left, top, right, bottom)``，``client_size`` 为 ``(w, h)``。
        """
        if not self._hwnd:
            return None, None, None
        try:
            user32 = ctypes.windll.user32
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(self._hwnd, ctypes.byref(rect))
            win_rect = (rect.left, rect.top, rect.right, rect.bottom)

            crect = ctypes.wintypes.RECT()
            user32.GetClientRect(self._hwnd, ctypes.byref(crect))
            cw, ch = crect.right - crect.left, crect.bottom - crect.top
            pt = ctypes.wintypes.POINT(0, 0)
            user32.ClientToScreen(self._hwnd, ctypes.byref(pt))
            client_rect = (pt.x, pt.y, pt.x + cw, pt.y + ch)
            return win_rect, client_rect, (cw, ch)
        except Exception:
            return None, None, None

    def _crop_client(self, frame: np.ndarray, client_size) -> np.ndarray:
        """从「整窗口」画面里裁出客户区（去掉标题栏/边框），不缩放。

        借助「左右/底部边框等宽、顶部为标题栏」的对称假设，仅凭帧尺寸与客户区
        尺寸推算偏移，因此对是否含隐藏 resize 边框都成立。
        """
        if client_size is None:
            return frame
        cw, ch = client_size
        fh, fw = frame.shape[0], frame.shape[1]
        if fw == cw and fh == ch:
            return frame  # 已经正好是客户区
        if fw < cw or fh < ch:
            return frame  # 抓到的比客户区还小，无法裁剪
        side = max(0, (fw - cw) // 2)       # 左右边框等宽
        top = max(0, (fh - ch) - side)      # 顶部 = 总高差 - 底部边框(=side)
        return frame[top:top + ch, side:side + cw]

    def capture(self) -> np.ndarray:
        """抓取原始帧。桌面型后端返回整屏，窗口型后端返回窗口画面。"""
        frame = self.backend.grab()
        if frame is None:
            logging.debug(f"[{self.backend.name}] 截图失败，返回空白帧")
            return np.zeros((self.BASE_H, self.BASE_W, 3), dtype=np.uint8)
        return frame

    def capture_game_area(self) -> np.ndarray:
        """返回归一化到 1920x1080 的游戏画面。"""
        frame = self.capture()
        win_rect, _, client_size = self._query_geometry()

        # 窗口型后端：grab() 已是整窗口画面，裁剪出客户区（不缩放）
        if getattr(self.backend, "returns_window_only", False):
            crop = self._crop_client(frame, client_size)
            # 窗口最小化时客户区为 0x0，裁剪结果可能为空帧；兜底返回空白基准帧，
            # 避免空图传给 cv2.cvtColor 触发 (-215:Assertion failed) !_src.empty()
            if crop is None or crop.size == 0 or crop.shape[0] == 0 or crop.shape[1] == 0:
                logging.debug(f"[{self.backend.name}] 客户区为空（窗口可能已最小化），返回空白帧")
                self.last_resolution = (self.BASE_W, self.BASE_H)
                return np.zeros((self.BASE_H, self.BASE_W, 3), dtype=np.uint8)
            self.last_resolution = (crop.shape[1], crop.shape[0])
            logging.debug(f"[{self.backend.name}] 裁剪客户区 {frame.shape[1]}x{frame.shape[0]} -> {crop.shape[1]}x{crop.shape[0]}")
            return crop

        # 桌面型后端：按窗口矩形裁剪
        if win_rect is None:
            logging.debug(f"[{self.backend.name}] 未绑定窗口，使用整屏")
            self.last_resolution = (self.BASE_W, self.BASE_H)
            if frame.shape[1] != self.BASE_W or frame.shape[0] != self.BASE_H:
                frame = cv2.resize(frame, (self.BASE_W, self.BASE_H))
            return frame
        l, t, r, b = win_rect
        crop = frame[max(0, t):max(0, b), max(0, l):max(0, r)]
        # 窗口最小化时坐标离屏（如 -32000），裁剪结果为空；兜底返回空白基准帧
        if crop is None or crop.size == 0 or crop.shape[0] == 0 or crop.shape[1] == 0:
            logging.debug(f"[{self.backend.name}] 裁剪为空（窗口可能已最小化），返回空白帧")
            self.last_resolution = (self.BASE_W, self.BASE_H)
            return np.zeros((self.BASE_H, self.BASE_W, 3), dtype=np.uint8)
        logging.debug(f"[{self.backend.name}] 按窗口裁剪 {win_rect} -> {crop.shape[1]}x{crop.shape[0]}")
        if crop.shape[1] != self.BASE_W or crop.shape[0] != self.BASE_H:
            crop = cv2.resize(crop, (self.BASE_W, self.BASE_H))
        self.last_resolution = (self.BASE_W, self.BASE_H)
        return crop

    def game_to_screen(self, gx: int, gy: int) -> Tuple[int, int]:
        win_rect, client_rect, _ = self._query_geometry()
        # 窗口型后端：游戏坐标基于客户区，直接映射到客户区在屏幕上的位置
        if getattr(self.backend, "returns_window_only", False) and client_rect is not None:
            cl, ct, cr, cb = client_rect
            cw, ch = cr - cl, cb - ct
            bw, bh = self.last_resolution
            sx = cl + gx * cw // bw
            sy = ct + gy * ch // bh
            return sx, sy
        # 桌面型后端：基于整窗口矩形映射
        if win_rect is None:
            return gx, gy
        l, t, r, b = win_rect
        w, h = r - l, b - t
        sx = l + gx * w // self.BASE_W
        sy = t + gy * h // self.BASE_H
        return sx, sy

    def get_resolution(self) -> Tuple[int, int]:
        return self.last_resolution

    def close(self):
        try:
            self.backend.close()
        except Exception:
            pass
