import logging
from typing import List, Tuple

from .base import InputMethod
from . import create_backend


class InputSimulator:
    """输入模拟门面（facade）。

    自身不实现输入算法，按 ``backend`` 选择 ``core/input`` 下的后端：
    前台型（SendInput）直接注入系统输入，窗口型（SendMessage/PostMessage）
    需绑定目标窗口句柄。对外 API 保持与历史 ``controller.InputSimulator`` 一致，
    向后兼容所有调用方。
    """

    def __init__(self, backend: str = "postmessage", target_hwnd: int = 0):
        self.method = InputMethod.normalize(backend)
        self.backend = create_backend(self.method)
        self._keep_mouse = False

        hwnd = target_hwnd
        if self.backend.needs_window and not hwnd:
            hwnd = self._find_window()
        if hwnd:
            self.backend.set_window(hwnd)

        logging.info(f"输入模拟方式: {self.method} (后端: {self.backend.name})")

    @property
    def keep_mouse(self) -> bool:
        return self._keep_mouse

    @keep_mouse.setter
    def keep_mouse(self, value: bool):
        self._keep_mouse = bool(value)
        self.backend.keep_mouse = bool(value)

    def set_window(self, hwnd: int):
        self.backend.set_window(hwnd)

    def _find_window(self) -> int:
        from core.window import resolve_hwnd

        hwnd = resolve_hwnd()
        if hwnd:
            logging.info(f"已绑定目标窗口 HWND={hwnd}")
        else:
            logging.warning(f"未选择目标窗口，{self.method} 后端将无法点击")
        return hwnd

    # ------------------------------------------------------------------
    # 对外点击 API（坐标均为目标分辨率下的屏幕像素）
    # ------------------------------------------------------------------
    def click_at(self, x: int, y: int, screen_w: int = 1920, screen_h: int = 1080):
        self.backend.click(x, y, screen_w, screen_h)

    def move_mouse_abs(self, x: int, y: int, screen_w: int = 1920, screen_h: int = 1080):
        """移动真实光标（仅 SendInput 后端支持，其它后端忽略）。"""
        mover = getattr(self.backend, "move_abs", None)
        if callable(mover):
            mover(x, y, screen_w, screen_h)

    def click_config(self, key: str, res: Tuple[int, int], config):
        pts = config.click_points.get(key)
        if not pts:
            return
        x, y = pts
        cx = int(x * res[0] / config.base_res[0])
        cy = int(y * res[1] / config.base_res[1])
        self.click_at(cx, cy, res[0], res[1])

    def click_coord(self, x: int, y: int, res: Tuple[int, int]):
        self.click_at(x, y, res[0], res[1])

    def click_region_center(self, region: List[int], res: Tuple[int, int]):
        x, y, w, h = region
        self.click_at(x + w // 2, y + h // 2, res[0], res[1])

    def close(self):
        try:
            self.backend.close()
        except Exception:
            pass
