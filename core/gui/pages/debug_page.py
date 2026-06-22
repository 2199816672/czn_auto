#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开发调试页：用 Tab 切换各调试功能。

当前包含：
- 调试像素点：点击「捕获画面」即时抓取最新游戏画面并尽量大地显示，
  之后在图上点击多个像素点，逐条收集（相对坐标 rx/ry + RGB + hex）。
"""
import logging

import cv2
import numpy as np
from PySide6.QtCore import QPoint, QRect, QSize, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
)
from qfluentwidgets import FluentIcon

from ..config_manager import ConfigManager
from ..theme import Palette
from ..tools import grab_game_frame


def _btn(text, icon=None, kind=None, parent=None):
    b = QPushButton(text, parent)
    if icon is not None:
        b.setIcon(icon.icon())
    if kind:
        b.setProperty("kind", kind)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


class _FrameGrabber(QThread):
    """后台抓取一帧，避免捕获后端预热阻塞 UI。"""
    captured = Signal(object, bool)   # frame(BGR ndarray), 是否找到窗口
    failed = Signal(str)

    def __init__(self, cfg: ConfigManager, parent=None):
        super().__init__(parent)
        self.cfg = cfg

    def run(self):
        try:
            frame, found = grab_game_frame(self.cfg)
            self.captured.emit(frame, found)
        except Exception as e:  # noqa: BLE001 - 调试用，吞掉异常仅报告
            self.failed.emit(str(e))


class ClickableImageView(QWidget):
    """等比缩放显示一帧画面（letterbox 适配），可点击采样像素颜色。

    对外发出 ``pointClicked(rx, ry, r, g, b)``，其中 rx/ry 为相对坐标(0~1)，
    与像素点判断规则 ``templates_colors`` 的格式一致。
    """

    pointClicked = Signal(float, float, int, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("imageView")
        self.setMinimumSize(480, 270)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._frame: np.ndarray | None = None   # BGR
        self._qimg: QImage | None = None
        self._points: list[tuple[int, int, QColor]] = []  # 原图坐标 + 颜色
        self._draw_rect = QRect()  # 当前图像在控件中的绘制区域

    @property
    def has_frame(self) -> bool:
        return self._frame is not None

    def set_frame(self, frame: np.ndarray):
        self._frame = frame
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        self._qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        self._points.clear()
        self.update()

    def clear_points(self):
        self._points.clear()
        self.update()

    # ---- 绘制 ----
    def _compute_draw_rect(self) -> QRect:
        if self._qimg is None:
            return QRect()
        iw, ih = self._qimg.width(), self._qimg.height()
        aw, ah = self.width(), self.height()
        scale = min(aw / iw, ah / ih)
        dw, dh = int(iw * scale), int(ih * scale)
        x = (aw - dw) // 2
        y = (ah - dh) // 2
        return QRect(x, y, dw, dh)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(Palette.LOG_BG))
        if self._qimg is None:
            p.setPen(QColor(Palette.TEXT_MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "点击「捕获画面」获取最新游戏画面")
            return
        self._draw_rect = self._compute_draw_rect()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.drawImage(self._draw_rect, self._qimg)

        # 标记已采样的点
        iw, ih = self._qimg.width(), self._qimg.height()
        scale = self._draw_rect.width() / iw if iw else 1
        for i, (ix, iy, color) in enumerate(self._points, 1):
            sx = self._draw_rect.x() + int(ix * scale)
            sy = self._draw_rect.y() + int(iy * scale)
            p.setPen(QPen(QColor("#000000"), 3))
            p.drawLine(sx - 7, sy, sx + 7, sy)
            p.drawLine(sx, sy - 7, sx, sy + 7)
            p.setPen(QPen(QColor(Palette.PRIMARY), 1))
            p.drawLine(sx - 7, sy, sx + 7, sy)
            p.drawLine(sx, sy - 7, sx, sy + 7)
            p.setPen(QColor(Palette.PRIMARY))
            f = QFont()
            f.setBold(True)
            p.setFont(f)
            p.drawText(QPoint(sx + 8, sy - 6), str(i))

    def mousePressEvent(self, event):
        if self._frame is None or self._qimg is None:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        rect = self._compute_draw_rect()
        if not rect.contains(event.position().toPoint()):
            return
        iw, ih = self._qimg.width(), self._qimg.height()
        rx_disp = event.position().x() - rect.x()
        ry_disp = event.position().y() - rect.y()
        ix = int(rx_disp / rect.width() * iw)
        iy = int(ry_disp / rect.height() * ih)
        ix = max(0, min(iw - 1, ix))
        iy = max(0, min(ih - 1, iy))
        b, g, r = (int(v) for v in self._frame[iy, ix][:3])
        self._points.append((ix, iy, QColor(r, g, b)))
        self.update()
        self.pointClicked.emit(ix / iw, iy / ih, r, g, b)


class PixelDebugTab(QWidget):
    """调试像素点：捕获画面 -> 在图上点击 -> 收集颜色列表。"""

    def __init__(self, cfg: ConfigManager, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._grabber: _FrameGrabber | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.btn_capture = _btn("捕获画面", FluentIcon.CAMERA, "primary", self)
        self.btn_capture.setMinimumHeight(38)
        self.btn_capture.clicked.connect(self._capture)
        self.btn_clear = _btn("清空采样", FluentIcon.DELETE, "ghost", self)
        self.btn_clear.setMinimumHeight(38)
        self.btn_clear.clicked.connect(self._clear)
        self.hint = QLabel("捕获后在画面上左键点击采样像素颜色", self)
        self.hint.setObjectName("caption")
        bar.addWidget(self.btn_capture)
        bar.addWidget(self.btn_clear)
        bar.addWidget(self.hint)
        bar.addStretch(1)
        self.res_label = QLabel("", self)
        self.res_label.setObjectName("caption")
        bar.addWidget(self.res_label)
        root.addLayout(bar)

        body = QHBoxLayout()
        body.setSpacing(12)
        self.view = ClickableImageView(self)
        self.view.pointClicked.connect(self._on_point)
        body.addWidget(self.view, 1)

        panel = QFrame(self)
        panel.setObjectName("card")
        panel.setFixedWidth(320)
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(14, 14, 14, 14)
        pv.setSpacing(10)
        cap = QLabel("采样点", panel)
        cap.setObjectName("sectionTitle")
        pv.addWidget(cap)
        self.list = QListWidget(panel)
        self.list.setIconSize(QSize(18, 18))
        pv.addWidget(self.list, 1)
        body.addWidget(panel)
        root.addLayout(body, 1)

    # ---- 捕获 ----
    def _capture(self):
        if self._grabber and self._grabber.isRunning():
            return
        self.cfg.reload()
        self.btn_capture.setEnabled(False)
        self.btn_capture.setText("捕获中…")
        self._grabber = _FrameGrabber(self.cfg, self)
        self._grabber.captured.connect(self._on_captured)
        self._grabber.failed.connect(self._on_failed)
        self._grabber.start()

    def _on_captured(self, frame: np.ndarray, found: bool):
        self.btn_capture.setEnabled(True)
        self.btn_capture.setText("捕获画面")
        self.view.set_frame(frame)
        self.list.clear()
        h, w = frame.shape[:2]
        tag = "" if found else "（未找到游戏窗口，使用整屏/空帧）"
        self.res_label.setText(f"画面 {w}x{h} {tag}")
        logging.info(f"调试像素点: 已捕获画面 {w}x{h} {tag}")

    def _on_failed(self, msg: str):
        self.btn_capture.setEnabled(True)
        self.btn_capture.setText("捕获画面")
        logging.error(f"调试像素点: 捕获失败 {msg}")

    def _clear(self):
        self.view.clear_points()
        self.list.clear()

    def _on_point(self, rx: float, ry: float, r: int, g: int, b: int):
        idx = self.list.count() + 1
        hex_str = f"#{r:02X}{g:02X}{b:02X}"
        swatch = QPixmap(18, 18)
        swatch.fill(QColor(r, g, b))
        item = QListWidgetItem(
            f"#{idx}  rx={rx:.4f} ry={ry:.4f}\n      RGB({r},{g},{b})  {hex_str}"
        )
        item.setIcon(swatch)
        self.list.addItem(item)
        self.list.scrollToBottom()
        logging.info(f"采样#{idx}: rx={rx:.4f} ry={ry:.4f} RGB({r},{g},{b}) {hex_str}")


class DebugPage(QWidget):
    """开发调试页外壳：Tab 切换不同调试功能。"""

    def __init__(self, cfg_mgr: ConfigManager, parent=None):
        super().__init__(parent)
        self.setObjectName("debugPage")
        self.cfg = cfg_mgr
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        title = QLabel("开发调试", self)
        title.setObjectName("pageTitle")
        root.addWidget(title)

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("debugTabs")
        self.tabs.addTab(PixelDebugTab(self.cfg, self), "调试像素点")
        root.addWidget(self.tabs, 1)
