#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行页：开始/暂停/停止控制、快速切换、实时统计卡片、彩色日志面板（扁平风）。"""
import html
import logging
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)
from qfluentwidgets import FluentIcon

from ..config_manager import ConfigManager
from ..constants import MISSION_DISPLAY, PROFILE_TO_SERVER, SERVER_TO_PROFILE, STAT_ITEMS
from ..theme import Palette
from ..widgets import SegmentedControl

_LEVEL_COLORS = {
    logging.ERROR: Palette.LOG_ERROR,
    logging.WARNING: Palette.LOG_WARNING,
    logging.INFO: Palette.LOG_TEXT,
}


def _btn(text, icon=None, kind=None, parent=None):
    b = QPushButton(text, parent)
    if icon is not None:
        b.setIcon(icon.icon())
    if kind:
        b.setProperty("kind", kind)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


class StatCard(QFrame):
    """单个统计卡片：上方标题，下方大号数字。"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedHeight(92)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(4)
        self._title = QLabel(title, self)
        self._title.setObjectName("statTitle")
        self._value = QLabel("0", self)
        self._value.setObjectName("statValue")
        lay.addWidget(self._title)
        lay.addWidget(self._value)

    def set_value(self, value):
        self._value.setText(str(value))


class HomePage(QWidget):
    startRequested = Signal()
    pauseRequested = Signal()
    stopRequested = Signal()
    captureRequested = Signal()
    diagnoseRequested = Signal()
    quickChanged = Signal()  # 服务器/模式 在首页被切换

    def __init__(self, cfg_mgr: ConfigManager, parent=None):
        super().__init__(parent)
        self.setObjectName("homePage")
        self.cfg = cfg_mgr
        self._start_time = 0.0
        self._cards: dict = {}
        self._build_ui()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        title = QLabel("运行面板", self)
        title.setObjectName("pageTitle")
        root.addWidget(title)

        # 快速切换：服务器 / 刷取模式
        quick = QHBoxLayout()
        quick.setSpacing(10)
        srv_lbl = QLabel("服务器", self)
        srv_lbl.setObjectName("fieldLabel")
        self.seg_server = SegmentedControl(
            [(profile, label) for label, profile in SERVER_TO_PROFILE.items()],
            current_key=self.cfg.profile, parent=self,
        )
        self.seg_server.changed.connect(self._on_server_changed)
        mode_lbl = QLabel("模式", self)
        mode_lbl.setObjectName("fieldLabel")
        self.seg_mission = SegmentedControl(
            list(MISSION_DISPLAY.items()),
            current_key=self.cfg.data.get("game", {}).get("mission", "zero_system"),
            parent=self,
        )
        self.seg_mission.changed.connect(self._on_mission_changed)
        quick.addWidget(srv_lbl)
        quick.addWidget(self.seg_server)
        quick.addSpacing(20)
        quick.addWidget(mode_lbl)
        quick.addWidget(self.seg_mission)
        quick.addStretch(1)
        root.addLayout(quick)

        # 控制按钮
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)
        self.btn_start = _btn("开始运行 (F6)", FluentIcon.PLAY, "primary", self)
        self.btn_pause = _btn("暂停 (F9)", FluentIcon.PAUSE, None, self)
        self.btn_stop = _btn("停止 (F8)", FluentIcon.CLOSE, "danger", self)
        self.btn_capture = _btn("模板采集", FluentIcon.CAMERA, "ghost", self)
        self.btn_diagnose = _btn("诊断", FluentIcon.DEVELOPER_TOOLS, "ghost", self)
        self.btn_start.clicked.connect(self.startRequested)
        self.btn_pause.clicked.connect(self.pauseRequested)
        self.btn_stop.clicked.connect(self.stopRequested)
        self.btn_capture.clicked.connect(self.captureRequested)
        self.btn_diagnose.clicked.connect(self.diagnoseRequested)
        for b in (self.btn_start, self.btn_pause, self.btn_stop, self.btn_capture, self.btn_diagnose):
            b.setMinimumHeight(40)
        ctrl.addWidget(self.btn_start)
        ctrl.addWidget(self.btn_pause)
        ctrl.addWidget(self.btn_stop)
        ctrl.addSpacing(12)
        ctrl.addWidget(self.btn_capture)
        ctrl.addWidget(self.btn_diagnose)
        ctrl.addStretch(1)
        self.status_dot = QLabel("●", self)
        self.status_label = QLabel("已停止", self)
        self.status_label.setObjectName("fieldLabel")
        ctrl.addWidget(self.status_dot)
        ctrl.addWidget(self.status_label)
        root.addLayout(ctrl)

        # 统计卡片
        stats = QHBoxLayout()
        stats.setSpacing(14)
        for key, name in STAT_ITEMS:
            card = StatCard(name, self)
            self._cards[key] = card
            stats.addWidget(card)
        self._time_card = StatCard("耗时", self)
        self._time_card.set_value("00:00:00")
        stats.addWidget(self._time_card)
        root.addLayout(stats)

        # 日志
        log_title = QLabel("运行日志", self)
        log_title.setObjectName("caption")
        root.addWidget(log_title)
        self.log = QTextEdit(self)
        self.log.setObjectName("logView")
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Cascadia Mono, Consolas", 10))
        root.addWidget(self.log, 1)

        self.set_running_ui(False, False)

    # ---- 快速切换 ----
    def _on_server_changed(self, profile: str):
        self.cfg.data["template_profile"] = profile
        self.cfg.save()
        logging.info(f"切换服务器: {PROFILE_TO_SERVER.get(profile, profile)}")
        self.quickChanged.emit()

    def _on_mission_changed(self, mission: str):
        self.cfg.data.setdefault("game", {})["mission"] = mission
        self.cfg.save()
        logging.info(f"切换模式: {MISSION_DISPLAY.get(mission, mission)}")
        self.quickChanged.emit()

    def refresh_quick(self):
        """从配置同步分段按钮选中态（设置页保存后调用）。"""
        self.seg_server.set_value(self.cfg.profile)
        self.seg_mission.set_value(self.cfg.data.get("game", {}).get("mission", "zero_system"))

    # ---- 对外接口 ----
    def append_log(self, msg: str, levelno: int, is_state: bool):
        if levelno >= logging.ERROR:
            color = _LEVEL_COLORS[logging.ERROR]
        elif levelno >= logging.WARNING:
            color = _LEVEL_COLORS[logging.WARNING]
        elif is_state:
            color = Palette.LOG_STATE
        else:
            color = _LEVEL_COLORS.get(levelno, Palette.LOG_TEXT)
        safe = html.escape(msg)
        self.log.append(f'<span style="color:{color};">{safe}</span>')

    def set_stats(self, stats: dict):
        for key, card in self._cards.items():
            card.set_value(stats.get(key, 0))

    def set_status(self, text: str, color: str):
        self.status_label.setText(text)
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 14px;")
        self.status_label.setStyleSheet(f"color: {color};")

    def set_running_ui(self, running: bool, paused: bool):
        self.btn_start.setEnabled(not running)
        self.btn_pause.setEnabled(running)
        self.btn_stop.setEnabled(running)
        self.seg_server.setEnabled(not running)
        self.seg_mission.setEnabled(not running)
        self.btn_pause.setText("继续 (F9)" if paused else "暂停 (F9)")
        if running and paused:
            self.set_status("已暂停", Palette.PAUSED)
        elif running:
            self.set_status("运行中", Palette.RUNNING)
        else:
            self.set_status("已停止", Palette.STOPPED)

    def start_timer(self):
        self._start_time = time.time()
        self._time_card.set_value("00:00:00")
        self._timer.start()

    def stop_timer(self):
        self._timer.stop()

    def _tick(self):
        e = int(time.time() - self._start_time)
        self._time_card.set_value(f"{e // 3600:02d}:{(e % 3600) // 60:02d}:{e % 60:02d}")
