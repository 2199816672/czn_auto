#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""应用入口：高 DPI 适配、Fluent 暗色主题、创建主窗口并进入事件循环。"""
import ctypes
import sys


def _enable_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def run():
    _enable_dpi_awareness()

    from PySide6.QtWidgets import QApplication

    from .theme import apply_theme

    app = QApplication.instance() or QApplication(sys.argv)

    from .main_window import MainWindow
    window = MainWindow()
    apply_theme(app, window)
    window.show()
    sys.exit(app.exec())
