import ctypes
import time
from ctypes import wintypes

from .base import (
    INPUT,
    INPUT_MOUSE,
    MOUSEEVENTF_ABSOLUTE,
    MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_LEFTUP,
    MOUSEEVENTF_MOVE,
    InputBackend,
    user32,
)


class SendInputBackend(InputBackend):
    """前台输入后端：通过 ``SendInput`` 注入真实系统鼠标事件。

    最稳，兼容性最好；但事件投递给**当前前台窗口 / 光标位置下的窗口**，
    因此要求游戏窗口处于前台，且会移动真实鼠标。
    """

    name = "sendinput"
    needs_window = False

    def move_abs(self, x: int, y: int, screen_w: int = 1920, screen_h: int = 1080):
        """把光标移动到归一化的绝对屏幕坐标。"""
        abs_x = int(x * 65535 / screen_w)
        abs_y = int(y * 65535 / screen_h)
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.union.mi.dx = abs_x
        inp.union.mi.dy = abs_y
        inp.union.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        inp.union.mi.time = 0
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def click(self, x: int, y: int, screen_w: int = 1920, screen_h: int = 1080):
        old_pos = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(old_pos))
        self.move_abs(x, y, screen_w, screen_h)
        time.sleep(0.03)

        down = INPUT()
        down.type = INPUT_MOUSE
        down.union.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
        user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(down))
        time.sleep(0.02)

        up = INPUT()
        up.type = INPUT_MOUSE
        up.union.mi.dwFlags = MOUSEEVENTF_LEFTUP
        user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(up))

        if not self.keep_mouse:
            user32.SetCursorPos(old_pos.x, old_pos.y)
