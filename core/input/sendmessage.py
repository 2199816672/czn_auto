import ctypes
import logging
import time
from ctypes import wintypes

from .base import (
    WM_LBUTTONDOWN,
    WM_LBUTTONUP,
    InputBackend,
    make_lparam,
    screen_to_client,
    user32,
)

MK_LBUTTON = 0x0001


class SendMessageBackend(InputBackend):
    """后台输入后端：通过 ``SendMessage`` 同步投递窗口鼠标消息。

    直接发往绑定的窗口句柄，**窗口不在前台也能点击**。``SendMessage`` 同步
    阻塞直到窗口处理完。仍会用 ``SetCursorPos`` 把真实光标移到目标点——许多
    游戏读取光标位置而非 ``lParam``，不移动会点不中；若要完全不碰鼠标用
    ``postmessage``。坐标会转成客户区坐标，兼容窗口化 / 带边框场景。
    """

    name = "sendmessage"
    needs_window = True

    def click(self, x: int, y: int, screen_w: int = 1920, screen_h: int = 1080):
        if not self._hwnd:
            logging.warning("SendMessage 后端未绑定窗口句柄，点击被忽略")
            return

        old_pos = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(old_pos))
        user32.SetCursorPos(x, y)
        time.sleep(0.01)

        cx, cy = screen_to_client(self._hwnd, x, y)
        lparam = make_lparam(cx, cy)
        user32.SendMessageW(self._hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
        time.sleep(0.02)
        user32.SendMessageW(self._hwnd, WM_LBUTTONUP, 0, lparam)

        if not self.keep_mouse:
            user32.SetCursorPos(old_pos.x, old_pos.y)
