#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""应用入口：Fluent 暗色主题、创建主窗口并进入事件循环。

高 DPI 不手动设置：Qt6 默认即启用高 DPI 缩放并把进程设为
``DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2``。若在 QApplication 之前再用
ctypes 抢先设置，会与 Qt 冲突并触发 "SetProcessDpiAwarenessContext failed: 拒绝访问"，
故交由 Qt 自行处理。
"""
import sys


def run():
    from PySide6.QtWidgets import QApplication

    from .theme import apply_theme

    # 设置 AppUserModelID，使 Windows 任务栏使用窗口图标而非默认 Python 图标
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("czn.zero.farm")
    except Exception:
        pass

    app = QApplication.instance() or QApplication(sys.argv)

    from .main_window import MainWindow
    window = MainWindow()
    apply_theme(app, window)
    window.show()
    sys.exit(app.exec())
