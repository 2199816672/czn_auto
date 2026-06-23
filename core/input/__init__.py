"""输入模拟后端。

通过 ``create_backend(method)`` 按名称获取具体实现：

- ``sendinput``   : SendInput 注入真实系统鼠标，发往前台窗口；最稳但需游戏在前台、会动鼠标
- ``sendmessage`` : SendMessage 同步投递窗口消息，后台可点；仍移动真实光标
- ``postmessage`` : PostMessage 异步投递窗口消息，后台可点且完全不碰鼠标
"""
import logging
from typing import Union

from .base import InputBackend, InputMethod, find_window_by_title

__all__ = [
    "InputBackend",
    "InputMethod",
    "create_backend",
    "find_window_by_title",
    "AVAILABLE_METHODS",
    "InputSimulator",
]

# 供 GUI 下拉框使用：内部值 -> 显示名
AVAILABLE_METHODS = {
    InputMethod.SENDINPUT.value: "SendInput (前台)",
    InputMethod.SENDMESSAGE.value: "SendMessage (后台)",
    InputMethod.POSTMESSAGE.value: "PostMessage (后台/不碰鼠标，推荐)",
}


def create_backend(method: "Union[str, InputMethod, None]") -> InputBackend:
    """根据方式名创建输入后端，未知方式回退到 PostMessage。"""
    method = InputMethod.normalize(method)

    if method == InputMethod.SENDINPUT.value:
        from .sendinput import SendInputBackend
        return SendInputBackend()

    if method == InputMethod.SENDMESSAGE.value:
        from .sendmessage import SendMessageBackend
        return SendMessageBackend()

    if method != InputMethod.POSTMESSAGE.value:
        logging.warning(f"未知输入方式 '{method}'，回退到 postmessage")

    from .postmessage import PostMessageBackend
    return PostMessageBackend()


# 末尾导入避免与 create_backend 形成循环导入
from .simulator import InputSimulator  # noqa: E402
