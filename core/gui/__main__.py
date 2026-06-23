#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模块入口：python -m core.gui"""
import sys
from pathlib import Path

# 兼容直接以脚本方式运行（保证项目根目录在 sys.path 上）
if getattr(sys, "frozen", False):
    _root = Path(sys.executable).parent
else:
    _root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.gui.app import run

if __name__ == "__main__":
    run()
