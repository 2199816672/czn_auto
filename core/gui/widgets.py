#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可复用的扁平自定义控件。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QPushButton, QWidget,
)


class SegmentedControl(QWidget):
    """扁平分段按钮组（Tailwind 风）：互斥选中，选中段为主色胶囊。"""

    changed = Signal(str)  # 选中项的 value-key

    def __init__(self, options, current_key=None, parent=None):
        """options: list[(key, label)]。"""
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        frame = QFrame(self)
        frame.setObjectName("segmented")
        inner = QHBoxLayout(frame)
        inner.setContentsMargins(3, 3, 3, 3)
        inner.setSpacing(3)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)

        for i, (key, label) in enumerate(options):
            b = QPushButton(label, frame)
            b.setObjectName("segment")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self._on_click(k))
            self._group.addButton(b, i)
            inner.addWidget(b)
            self._buttons[key] = b

        if current_key in self._buttons:
            self._buttons[current_key].setChecked(True)
        elif self._buttons:
            next(iter(self._buttons.values())).setChecked(True)

    def _on_click(self, key: str):
        self._buttons[key].setChecked(True)
        self.changed.emit(key)

    def set_value(self, key: str):
        """仅更新选中态，不发 changed 信号。"""
        b = self._buttons.get(key)
        if b and not b.isChecked():
            b.setChecked(True)

    def value(self):
        for k, b in self._buttons.items():
            if b.isChecked():
                return k
        return None
