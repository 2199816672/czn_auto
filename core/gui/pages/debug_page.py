#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开发调试页：用 Tab 切换各调试功能。

当前包含：
- 调试像素点：点击「捕获画面」即时抓取最新游戏画面并尽量大地显示，
  之后在图上点击多个像素点，逐条收集（相对坐标 rx/ry + RGB + hex）。
"""
import json
import logging

import cv2
import numpy as np
from PySide6.QtCore import QPoint, QRect, QSize, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QSizePolicy, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)
from qfluentwidgets import FluentIcon

from core.matcher import StateDetector, TemplateMatcher, load_pixel_checks
from core.matcher.pixel import PixelChecker

from ..config_manager import ConfigManager
from ..constants import PIXEL_DEBUGGER_PATH
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


def diagnose_frame(cfg: ConfigManager, frame: np.ndarray) -> dict:
    """对一帧做状态识别 + 逐条像素规则校验，供调试展示。

    返回 ``{"state", "checks", "rule_points"}``：
    - state: 当前识别到的 GameState 值
    - checks: 每条 pixel check 的结构化结果（state/mode/hit/points 明细）
    - rule_points: [(ix, iy, ok)]，原图坐标，供在画面上叠加标记
    """
    profile = cfg.data.get("template_profile")
    rules = load_pixel_checks(profile)
    checker = PixelChecker(rules)
    fh, fw = frame.shape[:2]

    checks: list[dict] = []
    rule_points: list[tuple[int, int, bool]] = []
    for rule in checker.rules:
        hit, _ = checker.match(frame, rule)
        pts: list[dict] = []
        hit_points: list[tuple[int, int, bool]] = []
        for p in rule.points:
            px = int(p.rx * fw)
            py = int(p.ry * fh)
            oob = not (0 <= px < fw and 0 <= py < fh)
            if oob:
                pts.append({"rx": p.rx, "ry": p.ry, "oob": True})
                continue
            b, g, r = (int(v) for v in frame[py, px][:3])
            tr, tg, tb = p.rgb
            dr, dg, db = abs(r - tr), abs(g - tg), abs(b - tb)
            ok = dr <= p.tol and dg <= p.tol and db <= p.tol
            pts.append({
                "rx": p.rx, "ry": p.ry, "oob": False, "ok": ok, "tol": p.tol,
                "expected": (tr, tg, tb), "actual": (r, g, b), "delta": (dr, dg, db),
            })
            hit_points.append((px, py, ok))
        # 仅在该规则命中时，才把它的点叠加到画面上
        if hit:
            rule_points.extend(hit_points)
        checks.append({"state": rule.state.value, "mode": rule.mode, "hit": hit, "points": pts})

    try:
        matcher = TemplateMatcher(cfg.profile_dir())
        detector = StateDetector(matcher, rules)
        state_val = detector.detect(frame).value
    except Exception as e:  # noqa: BLE001 - 调试用
        state_val = f"识别失败: {e}"

    return {"state": state_val, "checks": checks, "rule_points": rule_points}


class _FrameGrabber(QThread):
    """后台抓取一帧并做识别诊断，避免捕获后端预热阻塞 UI。"""
    captured = Signal(object, bool, dict)   # frame(BGR ndarray), 是否找到窗口, 诊断信息
    failed = Signal(str)

    def __init__(self, cfg: ConfigManager, parent=None):
        super().__init__(parent)
        self.cfg = cfg

    def run(self):
        try:
            frame, found = grab_game_frame(self.cfg)
            info = diagnose_frame(self.cfg, frame)
            self.captured.emit(frame, found, info)
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
        self._rule_points: list[tuple[int, int, bool]] = []  # 命中规则的像素点 + 是否通过
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
        self._rule_points.clear()
        self.update()

    def set_rule_points(self, points: list[tuple[int, int, bool]]):
        self._rule_points = list(points)
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

        iw, ih = self._qimg.width(), self._qimg.height()
        scale = self._draw_rect.width() / iw if iw else 1

        # 仅叠加命中规则的像素点（绿=通过 / 红=不通过）
        for ix, iy, ok in self._rule_points:
            sx = self._draw_rect.x() + int(ix * scale)
            sy = self._draw_rect.y() + int(iy * scale)
            col = QColor(Palette.RUNNING) if ok else QColor(Palette.LOG_ERROR)
            p.setPen(QPen(col, 2))
            p.drawRect(sx - 6, sy - 6, 12, 12)

        # 标记已采样的点
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
        self._samples: list[dict] = []  # 已采样点：[{rx, ry, rgb:[r,g,b]}]
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
        panel.setFixedWidth(360)
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(14, 14, 14, 14)
        pv.setSpacing(10)

        state_cap = QLabel("检测状态", panel)
        state_cap.setObjectName("statTitle")
        pv.addWidget(state_cap)
        self.state_label = QLabel("—", panel)
        self.state_label.setObjectName("statValue")
        pv.addWidget(self.state_label)

        diag_cap = QLabel("像素规则校验", panel)
        diag_cap.setObjectName("sectionTitle")
        pv.addWidget(diag_cap)
        self.diag = QTextEdit(panel)
        self.diag.setObjectName("logView")
        self.diag.setReadOnly(True)
        self.diag.setFont(QFont("Cascadia Mono, Consolas", 9))
        self.diag.setMinimumHeight(150)
        pv.addWidget(self.diag)

        cap = QLabel("采样点", panel)
        cap.setObjectName("sectionTitle")
        pv.addWidget(cap)
        self.list = QListWidget(panel)
        self.list.setIconSize(QSize(18, 18))
        pv.addWidget(self.list, 1)

        out_bar = QHBoxLayout()
        out_bar.setSpacing(8)
        self.state_input = QLineEdit(panel)
        self.state_input.setPlaceholderText("输入 state 名称")
        self.state_input.setMinimumHeight(34)
        out_bar.addWidget(self.state_input, 1)
        self.btn_export = _btn("输出", FluentIcon.SAVE, "primary", panel)
        self.btn_export.setMinimumHeight(34)
        self.btn_export.clicked.connect(self._export)
        out_bar.addWidget(self.btn_export)
        pv.addLayout(out_bar)

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

    def _on_captured(self, frame: np.ndarray, found: bool, info: dict):
        self.btn_capture.setEnabled(True)
        self.btn_capture.setText("捕获画面")
        self.view.set_frame(frame)
        self.list.clear()
        self._samples.clear()
        h, w = frame.shape[:2]
        tag = "" if found else "（未找到游戏窗口，使用整屏/空帧）"
        self.res_label.setText(f"画面 {w}x{h} {tag}")

        state = info.get("state", "—")
        self.state_label.setText(state)
        self.diag.setHtml(self._render_checks(info.get("checks", [])))
        self.view.set_rule_points(info.get("rule_points", []))
        logging.info(f"调试像素点: 已捕获画面 {w}x{h} 识别状态=[{state}] {tag}")

    def _render_checks(self, checks: list[dict]) -> str:
        """把每条 pixel check 的检测结果渲染成彩色 HTML。"""
        ok_c, bad_c, mut_c = Palette.RUNNING, Palette.LOG_ERROR, Palette.TEXT_MUTED
        if not checks:
            return f'<span style="color:{mut_c};">未加载到任何像素规则</span>'
        parts: list[str] = []
        for c in checks:
            hit = c["hit"]
            badge = "命中" if hit else "未命中"
            badge_c = ok_c if hit else bad_c
            parts.append(
                f'<div style="margin-top:6px;">'
                f'<b style="color:{Palette.TEXT_STRONG};">[{c["state"]}]</b> '
                f'<span style="color:{mut_c};">mode={c["mode"]}</span> '
                f'<b style="color:{badge_c};">{badge}</b></div>'
            )
            for p in c["points"]:
                coord = f'({p["rx"]:.4f},{p["ry"]:.4f})'
                if p.get("oob"):
                    parts.append(f'<div style="color:{bad_c};">&nbsp;&nbsp;{coord} 坐标越界</div>')
                    continue
                ok = p["ok"]
                pc = ok_c if ok else bad_c
                exp = "期望({},{},{})".format(*p["expected"])
                act = "实际({},{},{})".format(*p["actual"])
                dlt = "Δ({},{},{})".format(*p["delta"])
                parts.append(
                    f'<div style="color:{mut_c};">&nbsp;&nbsp;{coord} {exp} {act} '
                    f'<span style="color:{pc};">{dlt} tol={p["tol"]} {"OK" if ok else "X"}</span></div>'
                )
        return "".join(parts)

    def _on_failed(self, msg: str):
        self.btn_capture.setEnabled(True)
        self.btn_capture.setText("捕获画面")
        logging.error(f"调试像素点: 捕获失败 {msg}")

    def _clear(self):
        self.view.clear_points()
        self.list.clear()
        self._samples.clear()

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
        self._samples.append({"rx": round(rx, 4), "ry": round(ry, 4), "rgb": [r, g, b]})
        logging.info(f"采样#{idx}: rx={rx:.4f} ry={ry:.4f} RGB({r},{g},{b}) {hex_str}")

    def _export(self):
        """把当前采样点以 {state, points} 追加写入 pixel_debugger.json。"""
        state = self.state_input.text().strip()
        if not state:
            self.res_label.setText("请先输入 state 名称")
            logging.warning("输出像素规则: 未填写 state 名称")
            return
        if not self._samples:
            self.res_label.setText("没有可输出的采样点")
            logging.warning("输出像素规则: 采样点为空")
            return

        # 从 pixel_checks.json 加载已有规则（避免覆盖），追加新采样后再写回
        path = PIXEL_DEBUGGER_PATH
        checks_path = path.with_name("pixel_checks.json")
        data: list = []
        source = checks_path if checks_path.exists() else path
        if source.exists():
            try:
                loaded = json.loads(source.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    data = loaded
            except Exception as e:  # noqa: BLE001 - 调试用，损坏则覆盖
                logging.warning(f"读取已有规则失败，将重建: {e}")

        entry = {
            "state": state,
            "mode": "all",
            "points": [dict(p) for p in self._samples],
        }
        data.append(entry)
        # 同时写入 pixel_checks.json 和 pixel_debugger.json
        for target in (checks_path, path):
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as e:  # noqa: BLE001 - 调试用
                self.res_label.setText(f"写入 {target.name} 失败")
                logging.error(f"输出像素规则: 写入 {target.name} 失败 {e}")
                return
        self.res_label.setText(f"已输出 [{state}] {len(self._samples)} 点，总计 {len(data)} 条规则")
        logging.info(
            f"输出像素规则: 已追加 state=[{state}] {len(self._samples)} 点 -> pixel_checks.json"
        )


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
