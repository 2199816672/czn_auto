#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""游戏窗口提供者：发现《卡厄思梦境》本体窗口（国服/国际服/英文）。"""
from typing import List

from .base import WindowProvider, WindowTarget, enum_top_windows


class GameWindowProvider(WindowProvider):
    """直接运行的游戏客户端（PC 端 / 云游戏）。

    覆盖三种已知标题：简体「卡厄思梦境」、繁体「卡厄思夢境」、英文
    「Chaos Zero Nightmare」。命中规则为「已知标题作为子串出现」，以兼容
    个别带版本号/后缀的标题。
    """

    key = "game"
    label = "游戏窗口"

    TITLES = ("卡厄思梦境", "卡厄思夢境", "Chaos Zero Nightmare")

    def _matches(self, title: str) -> bool:
        low = title.lower()
        return any(known.lower() in low for known in self.TITLES)

    def discover(self) -> List[WindowTarget]:
        targets: List[WindowTarget] = []
        for hwnd, title in enum_top_windows():
            if self._matches(title):
                targets.append(WindowTarget(hwnd, title, self.key, self.label))
        return targets
