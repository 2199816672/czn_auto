import ctypes
import logging
import time
from ctypes import wintypes

from .base import (
    WM_LBUTTONDOWN,
    WM_LBUTTONUP,
    WM_MOUSEMOVE,
    InputBackend,
    make_lparam,
    user32,
)

MK_LBUTTON = 0x0001

# ChildWindowFromPointEx 跳过不可见/禁用/透明子窗口
CWP_SKIPINVISIBLE = 0x0001
CWP_SKIPDISABLED = 0x0002
CWP_SKIPTRANSPARENT = 0x0004


def _setup_signatures():
    """显式声明 ctypes 函数签名，避免 64 位句柄被截断为 32 位。"""
    user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.ScreenToClient.restype = wintypes.BOOL
    user32.ChildWindowFromPointEx.argtypes = [wintypes.HWND, wintypes.POINT, wintypes.UINT]
    user32.ChildWindowFromPointEx.restype = wintypes.HWND
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL


_setup_signatures()


class PostMessageBackend(InputBackend):
    """后台输入后端：通过 ``PostMessage`` 异步投递窗口鼠标消息。

    **完全不移动真实鼠标**，把消息异步投入目标窗口的消息队列后立即返回。
    适合挂机时继续使用电脑。注意：
    - ``lParam`` 使用**客户区坐标**（相对接收消息的那个窗口）。
    - 很多游戏（Unity/UE 等）真正接收输入的是渲染**子窗口**，故先用
      ``ChildWindowFromPointEx`` 解析坐标命中的子窗口，再发给它，避免消息
      被顶层窗口忽略或「发到别的窗口」。
    - 部分游戏只认真实硬件输入（忽略合成消息），此时本后端可能无效，请改用
      ``sendinput`` / ``sendmessage``。
    """

    name = "postmessage"
    needs_window = True

    def __init__(self, resolve_child: bool = True):
        super().__init__()
        # 是否解析坐标命中的子窗口（关闭则直接发给顶层窗口）。
        self.resolve_child = resolve_child

    def _resolve_target(self, x: int, y: int):
        """返回 (目标窗口句柄, 该窗口客户区坐标)。"""
        parent = self._hwnd
        ppt = wintypes.POINT(x, y)
        user32.ScreenToClient(parent, ctypes.byref(ppt))

        if not self.resolve_child:
            return parent, ppt.x, ppt.y

        flags = CWP_SKIPINVISIBLE | CWP_SKIPDISABLED | CWP_SKIPTRANSPARENT
        child = user32.ChildWindowFromPointEx(parent, wintypes.POINT(ppt.x, ppt.y), flags)
        if child and child != parent:
            cpt = wintypes.POINT(x, y)
            user32.ScreenToClient(child, ctypes.byref(cpt))
            return child, cpt.x, cpt.y
        return parent, ppt.x, ppt.y

    def click(self, x: int, y: int, screen_w: int = 1920, screen_h: int = 1080):
        if not self._hwnd:
            logging.warning("PostMessage 后端未绑定窗口句柄，点击被忽略")
            return

        target, cx, cy = self._resolve_target(x, y)
        lparam = make_lparam(cx, cy)

        # 先发一次移动，帮助依赖 hover/最近指针位置的界面更新状态
        user32.PostMessageW(target, WM_MOUSEMOVE, 0, lparam)
        user32.PostMessageW(target, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
        time.sleep(0.02)
        user32.PostMessageW(target, WM_LBUTTONUP, 0, lparam)
