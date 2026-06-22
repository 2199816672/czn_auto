#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设置页：服务器/平台、开关、路线优先级、坐标、延时、战斗、赛季图 OCR。

纯 Qt 控件 + 扁平分组卡片，所有字段直接读写 ConfigManager。
"""
import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)
from qfluentwidgets import FluentIcon, SwitchButton

from core.screencap import AVAILABLE_METHODS, CaptureMethod

from ..config_manager import ConfigManager
from ..constants import (
    CLICK_DESCS, CLICK_TIPS, COMBAT_FIELDS, COMBAT_LABELS, COMBAT_TIPS,
    INPUT_BACKEND_DISPLAY, MISSION_DISPLAY, MODE_DISPLAY, PROFILE_TO_SERVER,
    ROOM_NAMES, SERVER_TO_PROFILE, TIMING_FIELDS, TIMING_LABELS, TIMING_TIPS,
)

_ROOM_KEY = Qt.ItemDataRole.UserRole


def _combo(values, current, tip=None):
    cb = QComboBox()
    cb.addItems(values)
    if current in values:
        cb.setCurrentText(current)
    cb.setMinimumWidth(240)
    if tip:
        cb.setToolTip(tip)
    return cb


def _line(text, width=240, tip=None):
    le = QLineEdit()
    le.setText(str(text))
    le.setMinimumWidth(width)
    if tip:
        le.setToolTip(tip)
    return le


def _coord(text):
    le = QLineEdit()
    le.setText(str(text))
    le.setFixedWidth(78)
    le.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return le


class _Section(QFrame):
    """带标题的扁平分组卡片，内部用网格排列 标签 | 控件。"""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 18)
        outer.setSpacing(14)
        heading = QLabel(title, self)
        heading.setObjectName("sectionTitle")
        outer.addWidget(heading)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(18)
        self.grid.setVerticalSpacing(12)
        self.grid.setColumnStretch(1, 1)
        outer.addLayout(self.grid)
        self._row = 0

    def add(self, label, widget, tip=None):
        lbl = QLabel(label)
        lbl.setObjectName("fieldLabel")
        if tip:
            lbl.setToolTip(tip)
        self.grid.addWidget(lbl, self._row, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if isinstance(widget, QWidget):
            self.grid.addWidget(widget, self._row, 1, Qt.AlignmentFlag.AlignLeft)
        else:
            box = QWidget()
            box.setLayout(widget)
            self.grid.addWidget(box, self._row, 1, Qt.AlignmentFlag.AlignLeft)
        self._row += 1


class SettingsPage(QScrollArea):
    saved = Signal()

    def __init__(self, cfg_mgr: ConfigManager, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self.cfg = cfg_mgr
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._click_entries: dict = {}
        self._timing_entries: dict = {}
        self._combat_entries: dict = {}

        container = QWidget()
        container.setObjectName("settingsContainer")
        self.setWidget(container)
        self._root = QVBoxLayout(container)
        self._root.setContentsMargins(28, 24, 28, 28)
        self._root.setSpacing(18)

        title = QLabel("设置", container)
        title.setObjectName("pageTitle")
        self._root.addWidget(title)

        self._build_general()
        self._build_room_priority()
        self._build_clicks()
        self._build_timing_combat()
        self._build_ocr()
        self._build_save_bar()
        self._root.addStretch(1)

    # ---- 各分组 ----
    def _build_general(self):
        d = self.cfg.data
        g = d.get("game", {})
        sec = _Section("服务器与平台")

        self.server_combo = _combo(
            list(SERVER_TO_PROFILE.keys()),
            PROFILE_TO_SERVER.get(self.cfg.profile, "国际服"),
        )
        sec.add("当前服务器", self.server_combo)

        self.mission_combo = _combo(
            list(MISSION_DISPLAY.values()),
            MISSION_DISPLAY.get(g.get("mission", "zero_system"), "零式系统"),
            tip="零式系统：自动刷层\n赛季图初始刷取：OCR 匹配关键词直选退出",
        )
        sec.add("刷取模式", self.mission_combo, "切换零式系统 / 赛季图初始刷取")

        self.mode_combo = _combo(
            list(MODE_DISPLAY.values()),
            MODE_DISPLAY.get(g.get("mode", "pc"), "PC端/云游戏"),
        )
        sec.add("运行平台", self.mode_combo)

        self.input_combo = _combo(
            list(INPUT_BACKEND_DISPLAY.values()),
            INPUT_BACKEND_DISPLAY.get(g.get("input_backend", "sendinput"), "SendInput (前台推荐)"),
        )
        sec.add("输入方式", self.input_combo)

        self.capture_combo = _combo(
            list(AVAILABLE_METHODS.values()),
            AVAILABLE_METHODS.get(g.get("capture_method", CaptureMethod.DEFAULT.value)),
            tip="FramePool: 后台/遮挡可截 (Win10 1903+)\nPrintWindow: 后台/遮挡可截, 部分画面可能黑屏\n自动(DXGI): 最快, 仅前台",
        )
        sec.add("捕获方式", self.capture_combo, "屏幕捕获后端")

        self.sw_keep_mouse = SwitchButton()
        self.sw_keep_mouse.setChecked(d.get("debug", {}).get("keep_mouse", False))
        sec.add("调试：鼠标不归位", self.sw_keep_mouse)

        self.sw_codex = SwitchButton()
        self.sw_codex.setChecked(d.get("codex_use_btn1", True))
        sec.add("法典合成使用卡厄斯宝珠", self.sw_codex)

        self.sw_retreat = SwitchButton()
        self.sw_retreat.setChecked(g.get("retreat_on_first_floor", False))
        sec.add("仅推一层后撤退", self.sw_retreat)

        self._root.addWidget(sec)

    def _build_room_priority(self):
        sec = _Section("路线优先级（上为优先，下为兜底）")
        row = QHBoxLayout()
        row.setSpacing(12)
        self.room_list = QListWidget()
        self.room_list.setFixedHeight(180)
        self.room_list.setMaximumWidth(320)
        self.room_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        saved = self.cfg.data.get("room_priority", list(ROOM_NAMES.keys()))
        for key in saved:
            item = QListWidgetItem(f"{ROOM_NAMES.get(key, key)}   ({key})")
            item.setData(_ROOM_KEY, key)
            self.room_list.addItem(item)
        row.addWidget(self.room_list)

        btns = QVBoxLayout()
        btns.setSpacing(8)
        up = QPushButton("上移")
        up.setIcon(FluentIcon.UP.icon())
        down = QPushButton("下移")
        down.setIcon(FluentIcon.DOWN.icon())
        up.clicked.connect(lambda: self._move_room(-1))
        down.clicked.connect(lambda: self._move_room(1))
        btns.addWidget(up)
        btns.addWidget(down)
        btns.addStretch(1)
        row.addLayout(btns)
        row.addStretch(1)
        sec.grid.addLayout(row, 0, 0, 1, 2)
        self._root.addWidget(sec)

    def _build_clicks(self):
        sec = _Section("点击坐标（基于 1920×1080）")
        for key, val in self.cfg.data.get("click_points", {}).items():
            desc = CLICK_DESCS.get(key, key)
            tip = CLICK_TIPS.get(key)
            box = QHBoxLayout()
            box.setSpacing(6)
            entries = []
            n = 4 if (isinstance(val, list) and len(val) == 4) else 2
            for i in range(n):
                le = _coord(val[i] if i < len(val) else 0)
                box.addWidget(le)
                entries.append(le)
            box.addStretch(1)
            self._click_entries[key] = entries
            sec.add(desc, box, tip)
        self._root.addWidget(sec)

    def _build_timing_combat(self):
        d = self.cfg.data
        sec = _Section("延时与战斗")
        tim = d.get("timing", {})
        for k in TIMING_FIELDS:
            le = _line(tim.get(k, ""), width=130, tip=TIMING_TIPS.get(k))
            le.setMaximumWidth(150)
            self._timing_entries[k] = le
            sec.add(TIMING_LABELS.get(k, k), le, TIMING_TIPS.get(k))
        com = d.get("combat", {})
        for k in COMBAT_FIELDS:
            le = _line(com.get(k, ""), width=130, tip=COMBAT_TIPS.get(k))
            le.setMaximumWidth(150)
            self._combat_entries[k] = le
            sec.add(COMBAT_LABELS.get(k, k), le, COMBAT_TIPS.get(k))
        self._root.addWidget(sec)

    def _build_ocr(self):
        ocr = self.cfg.data.get("ocr", {})
        sec = _Section("赛季图初始刷取 (OCR)")

        self.ocr_entry_kw = _line(
            ",".join(ocr.get("entry_keywords", [])), width=280,
            tip="入口关键词，逗号分隔，命中其一即进入；留空视为手动",
        )
        sec.add("入口关键词", self.ocr_entry_kw)

        self.ocr_keyword = _line(
            ocr.get("keyword", ""), width=280,
            tip="Buff 目标关键词，识别到即停止；支持子串匹配",
        )
        sec.add("Buff 目标关键词", self.ocr_keyword)

        region = ocr.get("buff_region", [100, 300, 800, 300])
        rbox = QHBoxLayout()
        rbox.setSpacing(6)
        self.ocr_buff_region = []
        for i in range(4):
            le = _coord(region[i] if i < len(region) else 0)
            rbox.addWidget(le)
            self.ocr_buff_region.append(le)
        rbox.addStretch(1)
        sec.add("Buff 选择区域 [x,y,w,h]", rbox)

        self.ocr_exit_kw = _line(
            ",".join(ocr.get("exit_keywords", [])), width=280,
            tip="退出关键词，逗号分隔，命中其一即退出",
        )
        sec.add("退出关键词", self.ocr_exit_kw)

        offs = ocr.get("exit_keyword_offsets", [])
        off_str = ";".join(f"{o[0]},{o[1]}" for o in offs)
        self.ocr_exit_off = _line(off_str, width=280, tip="偏移格式: x,y 用 ; 分隔，如 0,-20;0,0")
        sec.add("退出关键词偏移", self.ocr_exit_off)

        self.ocr_buff_keyword = _line(
            ocr.get("buff_ocr_keyword", ""), width=320,
            tip="零式系统 Buff OCR 关键词，命中则停止循环",
        )
        sec.add("Buff OCR 关键词", self.ocr_buff_keyword)

        self.ocr_backend = _combo(
            ["windows", "paddle"], ocr.get("backend", "windows"),
            tip="windows = 系统自带 OCR(快)\npaddle = PaddleOCR 离线(更准)",
        )
        sec.add("OCR 后端", self.ocr_backend)

        self._root.addWidget(sec)

    def _build_save_bar(self):
        bar = QHBoxLayout()
        bar.addStretch(1)
        btn = QPushButton("保存配置")
        btn.setIcon(FluentIcon.SAVE.icon())
        btn.setProperty("kind", "primary")
        btn.setMinimumHeight(40)
        btn.setMinimumWidth(140)
        btn.clicked.connect(self._save)
        bar.addWidget(btn)
        self._root.addLayout(bar)

    # ---- 行为 ----
    def sync_quick(self):
        """首页切换服务器/模式后，同步设置页对应下拉框（不触发保存）。"""
        self.server_combo.setCurrentText(PROFILE_TO_SERVER.get(self.cfg.profile, "国际服"))
        mission = self.cfg.data.get("game", {}).get("mission", "zero_system")
        self.mission_combo.setCurrentText(MISSION_DISPLAY.get(mission, "零式系统"))

    def _move_room(self, delta):
        row = self.room_list.currentRow()
        if row < 0:
            return
        new = row + delta
        if new < 0 or new >= self.room_list.count():
            return
        item = self.room_list.takeItem(row)
        self.room_list.insertItem(new, item)
        self.room_list.setCurrentRow(new)

    def _save(self):
        d = self.cfg.data
        g = d.setdefault("game", {})

        d["template_profile"] = SERVER_TO_PROFILE.get(self.server_combo.currentText(), "templates_global")
        g["mission"] = self._reverse(MISSION_DISPLAY, self.mission_combo.currentText(), "zero_system")
        g["mode"] = self._reverse(MODE_DISPLAY, self.mode_combo.currentText(), "pc")
        g["input_backend"] = self._reverse(INPUT_BACKEND_DISPLAY, self.input_combo.currentText(), "sendinput")
        g["capture_method"] = self._reverse(AVAILABLE_METHODS, self.capture_combo.currentText(),
                                            CaptureMethod.DEFAULT.value)
        g["retreat_on_first_floor"] = self.sw_retreat.isChecked()
        d.setdefault("debug", {})["keep_mouse"] = self.sw_keep_mouse.isChecked()
        d["codex_use_btn1"] = self.sw_codex.isChecked()

        d["room_priority"] = [
            self.room_list.item(i).data(_ROOM_KEY) for i in range(self.room_list.count())
        ]

        cp = d.setdefault("click_points", {})
        for key, entries in self._click_entries.items():
            vals = []
            for le in entries:
                vals.append(self._to_int(le.text()))
            cp[key] = vals

        tim = d.setdefault("timing", {})
        for k, le in self._timing_entries.items():
            try:
                tim[k] = float(le.text())
            except ValueError:
                pass
        com = d.setdefault("combat", {})
        for k, le in self._combat_entries.items():
            try:
                com[k] = int(le.text()) if "max_turns" in k else float(le.text())
            except ValueError:
                pass

        ocr = d.setdefault("ocr", {})
        ocr["entry_keywords"] = [s.strip() for s in self.ocr_entry_kw.text().split(",") if s.strip()]
        ocr["keyword"] = self.ocr_keyword.text()
        ocr["exit_keywords"] = [s.strip() for s in self.ocr_exit_kw.text().split(",") if s.strip()]
        ocr["buff_region"] = [self._to_int(le.text()) for le in self.ocr_buff_region]
        ocr["buff_ocr_keyword"] = self.ocr_buff_keyword.text()
        ocr["backend"] = self.ocr_backend.currentText()
        off_arr = []
        for p in self.ocr_exit_off.text().split(";"):
            parts = p.split(",")
            if len(parts) == 2:
                try:
                    off_arr.append([int(parts[0]), int(parts[1])])
                except ValueError:
                    pass
        ocr["exit_keyword_offsets"] = off_arr

        self.cfg.save()
        logging.info("配置已保存")
        self.saved.emit()

    @staticmethod
    def _reverse(mapping: dict, display: str, default: str) -> str:
        for k, v in mapping.items():
            if v == display:
                return k
        return default

    @staticmethod
    def _to_int(text) -> int:
        try:
            return int(float(text))
        except ValueError:
            return 0
