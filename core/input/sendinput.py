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
    MOUSEEVENTF_VIRTUALDESK,
    InputBackend,
    user32,
)

# GetSystemMetrics 索引
SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


class SendInputBackend(InputBackend):
    """前台输入后端：通过 ``SendInput`` 注入真实系统鼠标事件。

    最稳，兼容性最好；但事件投递给**当前前台窗口 / 光标位置下的窗口**，
    因此要求游戏窗口处于前台，且会移动真实鼠标。
    """

    name = "sendinput"
    needs_window = False

    def move_abs(self, x: int, y: int, screen_w: int = 1920, screen_h: int = 1080):
        """把光标移动到绝对屏幕坐标 ``(x, y)``（屏幕物理像素）。

        ``MOUSEEVENTF_ABSOLUTE`` 的 0..65535 归一化空间映射的是**显示器真实尺寸**，
        而非游戏窗口。因此必须用屏幕的真实像素度量做分母，绝不能用游戏分辨率
        ``screen_w/screen_h``（后者仅为兼容旧签名而保留，已不参与计算）——否则当
        屏幕分辨率 ≠ 游戏分辨率（如 2K 屏 + 1080p 游戏）时落点会按比例偏移。

        配合 ``MOUSEEVENTF_VIRTUALDESK`` 以整个虚拟桌面为基准，支持多显示器
        （游戏在副屏也能正确落点）。
        """
        vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
        if vw <= 1 or vh <= 1:
            # 兜底：取主显示器尺寸（极少数取虚拟桌面失败的场景）
            vx = vy = 0
            vw = user32.GetSystemMetrics(SM_CXSCREEN)
            vh = user32.GetSystemMetrics(SM_CYSCREEN)
            flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        vw = max(vw, 2)
        vh = max(vh, 2)
        abs_x = int(round((x - vx) * 65535 / (vw - 1)))
        abs_y = int(round((y - vy) * 65535 / (vh - 1)))
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.union.mi.dx = abs_x
        inp.union.mi.dy = abs_y
        inp.union.mi.dwFlags = flags
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
