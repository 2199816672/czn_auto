#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置读写：封装 config.json 的加载、保存与 profile 目录解析。

打包(冻结)后首次运行自动从内置资源复制 config.json 到 EXE 同目录。
"""
import json
import sys
from pathlib import Path

from .constants import BASE_DIR, CONFIG_PATH


class ConfigManager:
    """config.json 的面向对象封装。所有页面共享同一实例。"""

    def __init__(self, path: Path = CONFIG_PATH):
        self.path = Path(path)
        self.data: dict = {}
        self.load()

    def load(self) -> dict:
        if not self.path.exists() and getattr(sys, "frozen", False):
            built_in = Path(sys._MEIPASS) / "config.json"
            if built_in.exists():
                self.path.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy2(str(built_in), str(self.path))
        with open(self.path, encoding="utf-8") as f:
            self.data = json.load(f)
        return self.data

    def save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def reload(self) -> dict:
        return self.load()

    # ---- 便捷访问 ----
    def section(self, name: str) -> dict:
        return self.data.setdefault(name, {})

    @property
    def profile(self) -> str:
        return self.data.get("template_profile", "templates_global")

    @profile.setter
    def profile(self, value: str) -> None:
        self.data["template_profile"] = value

    def profile_dir(self, name: str | None = None) -> Path:
        return BASE_DIR / "templates" / (name or self.profile)

    def template_count(self, name: str | None = None) -> int:
        d = self.profile_dir(name)
        return len(list(d.glob("*"))) if d.exists() else 0
