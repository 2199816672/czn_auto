#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行页：开始/暂停/停止控制、快速切换、实时统计卡片、彩色日志面板（扁平风）。"""
import html
import logging
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)
from qfluentwidgets import FluentIcon

from core.window import discover_windows, get_selected, select_window

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
        if kind == "primary":
            icon_color = QColor(Palette.PRIMARY_TEXT)   # 近白底 → 深色图标
        elif kind == "danger":
            icon_color = QColor("#ffffff")
        else:
            icon_color = QColor(Palette.TEXT)           # 深色底 → 浅色图标
        b.setIcon(icon.icon(color=icon_color))
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
    quickChanged = Signal()  # 服务器/模式 在首页被切换
    methodsChanged = Signal()  # 选 ADB/PC 设备后自动改了输入/捕获方式

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

        # 顶部：标题 + 运行状态
        header = QHBoxLayout()
        header.setSpacing(10)
        title = QLabel("运行面板", self)
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.status_dot = QLabel("●", self)
        self.status_label = QLabel("已停止", self)
        self.status_label.setObjectName("fieldLabel")
        header.addWidget(self.status_dot)
        header.addWidget(self.status_label)
        root.addLayout(header)

        root.addWidget(self._build_control_card())
        root.addLayout(self._build_stats_row())

        # 日志
        log_title = QLabel("运行日志", self)
        log_title.setObjectName("caption")
        root.addWidget(log_title)
        self.log = QTextEdit(self)
        self.log.setObjectName("logView")
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Cascadia Mono, Consolas", 10))
        root.addWidget(self.log, 1)

        self._refresh_windows()
        self.set_running_ui(False, False)

    def _build_control_card(self) -> QFrame:
        """控制卡片：快速切换（服务器/模式）+ 开始/暂停/停止按钮。"""
        card = QFrame(self)
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(16)

        # 选择目标窗口（游戏 / 后续模拟器）
        win_row = QHBoxLayout()
        win_row.setSpacing(10)
        win_lbl = QLabel("目标窗口", card)
        win_lbl.setObjectName("fieldLabel")
        self.cb_window = QComboBox(card)
        self.cb_window.setMinimumWidth(320)
        self.cb_window.currentIndexChanged.connect(self._on_window_changed)
        self.btn_refresh_win = _btn("刷新", FluentIcon.SYNC, "ghost", card)
        self.btn_refresh_win.clicked.connect(self._refresh_windows)
        win_row.addWidget(win_lbl)
        win_row.addWidget(self.cb_window, 1)
        win_row.addWidget(self.btn_refresh_win)
        lay.addLayout(win_row)

        # 快速切换：服务器 / 刷取模式
        quick = QHBoxLayout()
        quick.setSpacing(10)
        srv_lbl = QLabel("服务器", card)
        srv_lbl.setObjectName("fieldLabel")
        self.seg_server = SegmentedControl(
            [(profile, label) for label, profile in SERVER_TO_PROFILE.items()],
            current_key=self.cfg.profile, parent=card,
        )
        self.seg_server.changed.connect(self._on_server_changed)
        mode_lbl = QLabel("模式", card)
        mode_lbl.setObjectName("fieldLabel")
        self.seg_mission = SegmentedControl(
            list(MISSION_DISPLAY.items()),
            current_key=self.cfg.data.get("game", {}).get("mission", "zero_system"),
            parent=card,
        )
        self.seg_mission.changed.connect(self._on_mission_changed)
        quick.addWidget(srv_lbl)
        quick.addWidget(self.seg_server)
        quick.addSpacing(20)
        quick.addWidget(mode_lbl)
        quick.addWidget(self.seg_mission)
        quick.addStretch(1)
        lay.addLayout(quick)

        # 控制按钮
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)
        self.btn_start = _btn("开始运行 (F6)", FluentIcon.PLAY, "primary", card)
        self.btn_pause = _btn("暂停 (F9)", FluentIcon.PAUSE, None, card)
        self.btn_stop = _btn("停止 (F8)", FluentIcon.CLOSE, "danger", card)
        self.btn_start.clicked.connect(self.startRequested)
        self.btn_pause.clicked.connect(self.pauseRequested)
        self.btn_stop.clicked.connect(self.stopRequested)
        for b in (self.btn_start, self.btn_pause, self.btn_stop):
            b.setMinimumHeight(40)
        ctrl.addWidget(self.btn_start, 2)
        ctrl.addWidget(self.btn_pause, 1)
        ctrl.addWidget(self.btn_stop, 1)
        lay.addLayout(ctrl)
        return card

    def _build_stats_row(self) -> QHBoxLayout:
        """统计卡片行：局 / 战 / 事件 / 耗时，等宽铺满。"""
        stats = QHBoxLayout()
        stats.setSpacing(14)
        for key, name in STAT_ITEMS:
            card = StatCard(name, self)
            self._cards[key] = card
            stats.addWidget(card, 1)
        self._time_card = StatCard("耗时", self)
        self._time_card.set_value("00:00:00")
        stats.addWidget(self._time_card, 1)
        return stats

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

    # ---- 目标窗口选择（进程全局，不入 config）----
    def _refresh_windows(self):
        """枚举候选窗口填充下拉，并尽量沿用当前已选中的窗口。"""
        prev = get_selected()

        self.cb_window.blockSignals(True)
        self.cb_window.clear()

        targets = discover_windows()
        sel_index = -1
        for t in targets:
            self.cb_window.addItem(t.display, t)
            if prev is not None and sel_index < 0 and (
                t.hwnd == prev.hwnd
                or (t.title == prev.title and t.provider_key == prev.provider_key)
            ):
                sel_index = self.cb_window.count() - 1

        if not targets:
            self.cb_window.addItem("未找到游戏窗口，请先启动游戏后点刷新", None)
            sel_index = 0
        elif sel_index < 0:
            sel_index = 0

        self.cb_window.setCurrentIndex(sel_index)
        self.cb_window.blockSignals(False)
        # 同步全局选择到下拉当前项（即使没有用户交互）
        chosen = self.cb_window.itemData(sel_index)
        select_window(chosen)
        self._apply_methods_for_target(chosen)
        logging.info(f"发现 {len(targets)} 个候选窗口/设备")

    def _on_window_changed(self, index: int):
        target = self.cb_window.itemData(index)
        select_window(target)
        if target is not None:
            logging.info(f"选择目标窗口: {target.title} (句柄={target.hwnd})")
        self._apply_methods_for_target(target)

    def _apply_methods_for_target(self, target):
        """根据所选目标来源自动切换输入/捕获方式。

        - 选 ADB 设备：记忆当前 PC 方式后切到 adb；
        - 选回 PC 窗口：从记忆值恢复（缺省回退 postmessage/framepool）。
        变更写入 config 并保存，发 ``methodsChanged`` 让设置页刷新下拉。
        """
        g = self.cfg.data.setdefault("game", {})
        is_adb = target is not None and getattr(target, "provider_key", "") == "adb"
        changed = False

        if is_adb:
            if g.get("input_backend") != "adb":
                g["prev_input_backend"] = g.get("input_backend", "postmessage")
                g["input_backend"] = "adb"
                changed = True
            if g.get("capture_method") != "adb":
                g["prev_capture_method"] = g.get("capture_method", "framepool")
                g["capture_method"] = "adb"
                changed = True
            if changed:
                logging.info("已切换输入/捕获方式为 ADB")
        else:
            if g.get("input_backend") == "adb":
                g["input_backend"] = g.get("prev_input_backend", "postmessage")
                changed = True
            if g.get("capture_method") == "adb":
                g["capture_method"] = g.get("prev_capture_method", "framepool")
                changed = True
            if changed:
                logging.info(
                    f"已恢复输入/捕获方式为 {g.get('input_backend')}/{g.get('capture_method')}"
                )

        if changed:
            self.cfg.save()
            self.methodsChanged.emit()

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
        self.cb_window.setEnabled(not running)
        self.btn_refresh_win.setEnabled(not running)
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
