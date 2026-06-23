#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日志桥接：把 logging 记录通过 Qt 信号送到主线程的日志控件，保证线程安全。"""
import datetime
import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .constants import LOGS_DIR


class _LogSignals(QObject):
    # message: 已格式化文本, levelno, 是否状态行
    message = Signal(str, int, bool)


class QtLogHandler(logging.Handler):
    """logging.Handler 子类，emit 时仅发射信号（不直接碰 UI）。"""

    def __init__(self):
        super().__init__()
        self.signals = _LogSignals()

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            is_state = "状态" in msg or "State:" in msg
            self.signals.message.emit(msg, record.levelno, is_state)
        except Exception:
            self.handleError(record)


def install_logging(log_widget_handler: QtLogHandler) -> Path:
    """挂载 Qt 日志处理器 + 文件处理器，返回日志文件路径。"""
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", datefmt="%H:%M:%S")
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)

    log_widget_handler.setFormatter(fmt)
    root.addHandler(log_widget_handler)
    root.setLevel(logging.DEBUG)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOGS_DIR / f"czn_zero_{ts}.log"
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)
    return log_path
