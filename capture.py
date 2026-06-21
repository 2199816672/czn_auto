import numpy as np
import cv2
import dxcam
import ctypes
import logging
from typing import Tuple, Optional


class ScreenCapturer:
    BASE_W, BASE_H = 1920, 1080

    def __init__(self, method: str = "auto"):
        self.camera = self._create_camera()
        self.method = method
        self.last_resolution = (self.BASE_W, self.BASE_H)
        self._hwnd = None
        self._win_rect = None

    def _create_camera(self):
        try:
            return dxcam.create(output_color="BGR")
        except Exception as e:
            logging.error(f"创建dxcam失败: {e}")
            return None

    def set_window(self, hwnd: int):
        self._hwnd = hwnd
        self._update_rect()

    def _update_rect(self):
        if self._hwnd:
            try:
                rect = ctypes.wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(self._hwnd, ctypes.byref(rect))
                self._win_rect = (rect.left, rect.top, rect.right, rect.bottom)
            except Exception:
                self._win_rect = None

    def capture(self) -> np.ndarray:
        if self.camera is None:
            self.camera = self._create_camera()
            if self.camera is None:
                return np.zeros((self.BASE_H, self.BASE_W, 3), dtype=np.uint8)
        img = self.camera.grab()
        if img is None:
            img = self.camera.grab()
        if img is None:
            logging.warning("截图失败，重建dxcam实例")
            try:
                self.camera.stop()
                del self.camera
            except Exception:
                pass
            self.camera = None
            return np.zeros((self.BASE_H, self.BASE_W, 3), dtype=np.uint8)
        return img

    def capture_game_area(self) -> np.ndarray:
        frame = self.capture()
        if self._win_rect is None:
            self.last_resolution = (self.BASE_W, self.BASE_H)
            if frame.shape[1] != self.BASE_W or frame.shape[0] != self.BASE_H:
                frame = cv2.resize(frame, (self.BASE_W, self.BASE_H))
            return frame
        l, t, r, b = self._win_rect
        crop = frame[t:b, l:r]
        if crop.shape[1] != self.BASE_W or crop.shape[0] != self.BASE_H:
            crop = cv2.resize(crop, (self.BASE_W, self.BASE_H))
        self.last_resolution = (self.BASE_W, self.BASE_H)
        return crop

    def game_to_screen(self, gx: int, gy: int) -> Tuple[int, int]:
        if self._win_rect is None:
            return gx, gy
        l, t, r, b = self._win_rect
        w, h = r - l, b - t
        sx = l + gx * w // self.BASE_W
        sy = t + gy * h // self.BASE_H
        return sx, sy

    def get_resolution(self) -> Tuple[int, int]:
        return self.last_resolution
