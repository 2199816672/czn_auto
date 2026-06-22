import json
import logging
import sys
from pathlib import Path
from typing import List, Tuple

from .base import InputMethod, find_window_by_title
from . import create_backend


class InputSimulator:
    """输入模拟门面（facade）。

    自身不实现输入算法，按 ``backend`` 选择 ``core/input`` 下的后端：
    前台型（SendInput）直接注入系统输入，窗口型（SendMessage/PostMessage）
    需绑定目标窗口句柄。对外 API 保持与历史 ``controller.InputSimulator`` 一致，
    向后兼容所有调用方。
    """

    def __init__(self, backend: str = "sendinput", target_hwnd: int = 0):
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
        cfg_path = None
        if getattr(sys, "frozen", False):
            cfg_path = Path(sys.executable).parent / "config.json"
            if not cfg_path.exists():
                cfg_path = Path(sys._MEIPASS) / "config.json"
        else:
            cfg_path = Path(__file__).resolve().parents[2] / "config.json"
        title = "卡厄思梦境"
        if cfg_path.exists():
            try:
                with open(cfg_path, encoding="utf-8") as f:
                    cfg = json.load(f)
                title = cfg.get("game", {}).get("window_title", title)
            except Exception:
                pass
        hwnd = find_window_by_title(title)
        if hwnd:
            logging.info(f"已找到窗口 '{title}' HWND={hwnd}")
        else:
            logging.warning(f"未找到窗口 '{title}'，{self.method} 后端将无法点击")
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
