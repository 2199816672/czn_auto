#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主窗口：Fluent 导航 + 运行页/设置页，统筹工作线程、日志、热键。"""
import logging

from PySide6.QtCore import QObject, Signal
from qfluentwidgets import FluentIcon, FluentWindow, InfoBar, InfoBarPosition

from .config_manager import ConfigManager
from .constants import WINDOW_TITLE
from .logging_bridge import QtLogHandler, install_logging
from .pages import DebugPage, HomePage, SettingsPage
from .tools import CaptureService, DiagnoseService
from .worker import AutomationWorker


class _HotkeyBridge(QObject):
    """把 keyboard 线程的热键回调安全转发到主线程槽。"""
    start = Signal()
    stop = Signal()
    pause = Signal()


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager()
        self.worker: AutomationWorker | None = None
        self._capture = CaptureService(self.cfg)
        self._diagnose = DiagnoseService(self.cfg)

        self.home = HomePage(self.cfg, self)
        self.settings = SettingsPage(self.cfg, self)
        self.debug = DebugPage(self.cfg, self)

        self.addSubInterface(self.home, FluentIcon.PLAY, "运行")
        self.addSubInterface(self.debug, FluentIcon.DEVELOPER_TOOLS, "调试")
        self.addSubInterface(self.settings, FluentIcon.SETTING, "设置")

        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1180, 820)

        self._wire()
        self._setup_logging()
        self._setup_hotkeys()

    def _wire(self):
        self.home.startRequested.connect(self.start_run)
        self.home.pauseRequested.connect(self.toggle_pause)
        self.home.stopRequested.connect(self.stop_run)
        self.home.captureRequested.connect(self.start_capture)
        self.home.diagnoseRequested.connect(self.start_diagnose)
        self.home.quickChanged.connect(self.settings.sync_quick)
        self.settings.saved.connect(self._on_settings_saved)

    def _setup_logging(self):
        handler = QtLogHandler()
        handler.signals.message.connect(self.home.append_log)
        log_path = install_logging(handler)
        n = self.cfg.template_count()
        logging.info(f"GUI 启动完成 | 配置: [{self.cfg.profile}] ({n} 个模板)")
        logging.info(f"日志文件: {log_path}")

    def _setup_hotkeys(self):
        self._hk = _HotkeyBridge()
        self._hk.start.connect(self.start_run)
        self._hk.stop.connect(self.stop_run)
        self._hk.pause.connect(self.toggle_pause)
        try:
            import keyboard as kb
            kb.add_hotkey("f6", lambda: self._hk.start.emit(), suppress=True)
            kb.add_hotkey("f8", lambda: self._hk.stop.emit(), suppress=True)
            kb.add_hotkey("f9", lambda: self._hk.pause.emit(), suppress=True)
            logging.info("热键已注册 F6=开始 F8=停止 F9=暂停")
        except Exception as e:
            logging.warning(f"热键注册失败({e})，请以管理员身份运行")

    # ---- 运行控制 ----
    def start_run(self):
        if self.worker and self.worker.isRunning():
            return
        self.cfg.reload()
        tdir = self.cfg.profile_dir()
        if not tdir.exists() or not any(tdir.iterdir()):
            InfoBar.warning("模板缺失", f"[{self.cfg.profile}] 模板目录为空，仍尝试运行",
                            duration=4000, position=InfoBarPosition.TOP, parent=self)
        self.worker = AutomationWorker(self.cfg)
        self.worker.stats_changed.connect(self.home.set_stats)
        self.worker.finished.connect(self._on_worker_finished)
        self.home.set_stats({})
        self.home.set_running_ui(True, False)
        self.home.start_timer()
        self.worker.start()

    def stop_run(self):
        if self.worker and self.worker.isRunning():
            self.home.set_status("停止中…", "#f39c12")
            self.worker.request_stop()

    def toggle_pause(self):
        if not (self.worker and self.worker.isRunning()):
            return
        paused = not self.worker.is_paused
        self.worker.set_paused(paused)
        self.home.set_running_ui(True, paused)
        logging.warning("用户暂停" if paused else "继续运行")

    def _on_worker_finished(self):
        self.home.stop_timer()
        self.home.set_running_ui(False, False)

    # ---- 工具 ----
    def start_capture(self):
        self.cfg.reload()
        self._capture.start()

    def start_diagnose(self):
        self.cfg.reload()
        self._diagnose.run()

    def _on_settings_saved(self):
        self.home.refresh_quick()
        InfoBar.success("已保存", "配置已写入 config.json",
                        duration=2500, position=InfoBarPosition.TOP, parent=self)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.request_stop()
            self.worker.wait(3000)
        super().closeEvent(event)
