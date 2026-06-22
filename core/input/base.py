import ctypes
from abc import ABC, abstractmethod
from ctypes import wintypes
from enum import Enum
from typing import Optional, Tuple, Union

user32 = ctypes.windll.user32

# Win32 鼠标消息
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202

# SendInput 相关常量
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]


class InputMethod(str, Enum):
    """输入模拟方式。继承 ``str`` 以便直接与 JSON / 配置字符串互通。"""

    SENDINPUT = "sendinput"        # 前台：真实系统鼠标输入，发往前台窗口
    SENDMESSAGE = "sendmessage"    # 后台：窗口消息，仍移动真实光标（同步阻塞）
    POSTMESSAGE = "postmessage"    # 后台：窗口消息，完全不碰真实鼠标（异步投递）

    DEFAULT = "sendinput"          # 别名：默认方式（值与 SENDINPUT 相同）

    @classmethod
    def normalize(cls, value: "Union[str, InputMethod, None]") -> str:
        """把任意输入规整为合法的方式字符串，None/空 取默认值。"""
        if value is None:
            return cls.SENDINPUT.value
        if isinstance(value, cls):
            return value.value
        text = str(value).strip().lower()
        return text or cls.SENDINPUT.value


def find_window_by_title(title: str) -> int:
    """按窗口标题精确查找顶层窗口句柄，未找到返回 0。"""
    if not title:
        return 0
    return user32.FindWindowW(None, title) or 0


def screen_to_client(hwnd: int, x: int, y: int) -> Tuple[int, int]:
    """把屏幕坐标转换为目标窗口的客户区坐标。

    窗口消息（WM_LBUTTONDOWN 等）的 ``lParam`` 必须是客户区坐标；直接塞屏幕
    坐标会在窗口非全屏 / 带标题栏边框时产生偏移。失败时原样返回。
    """
    if not hwnd:
        return x, y
    pt = wintypes.POINT(x, y)
    if user32.ScreenToClient(hwnd, ctypes.byref(pt)):
        return pt.x, pt.y
    return x, y


def make_lparam(x: int, y: int) -> int:
    """把坐标打包成鼠标消息的 ``lParam``（低 16 位 x，高 16 位 y）。"""
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


class InputBackend(ABC):
    """输入模拟后端抽象基类。

    统一对外提供 ``click(x, y, screen_w, screen_h)``，坐标为目标分辨率下的屏幕像素。
    - 前台型后端（SendInput）直接注入系统输入队列，发往前台窗口；
    - 窗口型后端（SendMessage / PostMessage）需 ``set_window`` 绑定句柄，
      把坐标转成客户区后投递窗口消息。
    """

    name: str = "base"

    # True 表示该后端必须绑定目标窗口句柄才能工作。
    needs_window: bool = False

    def __init__(self):
        self._hwnd: Optional[int] = None
        # 点击后是否保留光标位置（不归位）。仅对会移动真实光标的后端有意义。
        self.keep_mouse: bool = False

    def set_window(self, hwnd: int):
        """绑定目标窗口句柄。"""
        self._hwnd = hwnd

    @abstractmethod
    def click(self, x: int, y: int, screen_w: int = 1920, screen_h: int = 1080):
        """在 (x, y) 处模拟一次左键单击。"""
        raise NotImplementedError

    def close(self):
        """释放后端持有的资源。"""
        pass
