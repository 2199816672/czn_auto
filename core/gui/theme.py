#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""集中式扁平主题（简约黑夜模式：近黑中性灰画布 + 克制的单色交互）。

设计原则：深色、低饱和、少用彩色。表面/控件全部走中性灰（zinc 系），
主按钮用近白色、选中/聚焦用中性高亮；仅日志的告警/错误与状态圆点保留
功能性颜色。1px 描边、统一圆角、无渐变阴影。
"""
from pathlib import Path

_ASSETS = Path(__file__).resolve().parent / "assets"


def _asset_url(name: str) -> str:
    return (_ASSETS / name).as_posix()


class Palette:
    # 画布 / 表面（近黑中性灰，zinc 系）
    BG = "#0b0b0d"           # 内容画布（近黑）
    BG_INPUT = "#0b0b0d"     # 输入框底色
    SURFACE = "#161618"      # 卡片
    SURFACE_HOVER = "#202024"  # 悬停 / 轻微抬升
    SELECTION = "#2e2e33"    # 选中 / 选区高亮（中性）
    BORDER = "#2a2a2e"       # 描边
    BORDER_STRONG = "#3f3f46"  # 悬停描边
    BORDER_SOFT = "#1b1b1e"  # 弱描边
    FOCUS = "#52525b"        # 聚焦描边（中性，非彩色）
    # 文本
    TEXT = "#e4e4e7"         # 主文本 zinc-200
    TEXT_STRONG = "#fafafa"  # 标题 近白
    TEXT_MUTED = "#a1a1aa"   # 次要 zinc-400
    TEXT_DISABLED = "#52525b"  # zinc-600
    # 主按钮（近白，shadcn 风的高对比 primary）
    PRIMARY = "#fafafa"
    PRIMARY_HOVER = "#e4e4e7"
    PRIMARY_PRESSED = "#d4d4d8"
    PRIMARY_TEXT = "#0b0b0d"
    # 危险（停止）——克制的暗红，唯一的功能性按钮色
    DANGER = "#b91c1c"
    DANGER_HOVER = "#dc2626"
    # qfluent 开关 / 导航高亮用的“主题色”（中性浅灰，避免彩色）
    THEME = "#d4d4d8"
    # 状态圆点（小面积功能色）
    RUNNING = "#4ade80"
    PAUSED = "#eab308"
    STOPPED = "#71717a"
    # 日志（克制：普通灰、状态偏白，仅告警/错误着色）
    LOG_BG = "#0a0a0c"
    LOG_TEXT = "#a1a1aa"
    LOG_STATE = "#e4e4e7"
    LOG_WARNING = "#d4a72c"
    LOG_ERROR = "#e5635f"


FONT_FAMILIES = [
    "Noto Sans SC", "Noto Sans",
    "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI",
]
_FONT = ", ".join(f"'{f}'" for f in FONT_FAMILIES) + ", sans-serif"


def build_stylesheet() -> str:
    p = Palette
    return f"""
* {{
    font-family: {_FONT};
    outline: none;
}}
QWidget {{
    color: {p.TEXT};
    font-size: 14px;
}}
QToolTip {{
    background: {p.SURFACE};
    color: {p.TEXT};
    border: 1px solid {p.BORDER};
    padding: 4px 8px;
}}

/* ---- 内容画布 ---- */
#homePage, #settingsContainer, #debugPage {{
    background: {p.BG};
}}

/* ---- 调试页 Tab ---- */
QTabWidget#debugTabs::pane {{
    border: 1px solid {p.BORDER};
    border-radius: 10px;
    top: -1px;
    background: {p.BG};
}}
QTabWidget#debugTabs > QTabBar {{ qproperty-drawBase: 0; }}
QTabWidget#debugTabs QTabBar::tab {{
    background: transparent;
    color: {p.TEXT_MUTED};
    border: 1px solid transparent;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 8px 18px;
    margin-right: 4px;
    font-size: 13px;
}}
QTabWidget#debugTabs QTabBar::tab:hover {{ color: {p.TEXT}; }}
QTabWidget#debugTabs QTabBar::tab:selected {{
    background: {p.SURFACE};
    color: {p.TEXT_STRONG};
    border: 1px solid {p.BORDER};
    border-bottom-color: {p.SURFACE};
    font-weight: 600;
}}

/* ---- 可点击图像视图 ---- */
QWidget#imageView {{
    border: 1px solid {p.BORDER};
    border-radius: 10px;
}}

/* ---- 卡片 / 分组 ---- */
QFrame#card {{
    background: {p.SURFACE};
    border: 1px solid {p.BORDER};
    border-radius: 12px;
}}

/* ---- 文本层级 ---- */
QLabel#pageTitle {{ color: {p.TEXT_STRONG}; font-size: 22px; font-weight: 700; }}
QLabel#sectionTitle {{ color: {p.TEXT_STRONG}; font-size: 15px; font-weight: 600; }}
QLabel#fieldLabel {{ color: {p.TEXT}; font-size: 13px; }}
QLabel#statTitle {{ color: {p.TEXT_MUTED}; font-size: 12px; }}
QLabel#statValue {{ color: {p.TEXT_STRONG}; font-size: 26px; font-weight: 700; }}
QLabel#caption {{ color: {p.TEXT_MUTED}; font-size: 12px; }}

/* ---- 按钮（扁平，property kind 切换变体）---- */
QPushButton {{
    background: {p.SURFACE};
    color: {p.TEXT};
    border: 1px solid {p.BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 14px;
}}
QPushButton:hover {{ background: {p.SURFACE_HOVER}; border-color: {p.BORDER_STRONG}; }}
QPushButton:pressed {{ background: {p.BG}; }}
QPushButton:disabled {{ color: {p.TEXT_DISABLED}; background: {p.SURFACE}; border-color: {p.BORDER_SOFT}; }}

QPushButton[kind="primary"] {{ background: {p.PRIMARY}; border: 1px solid {p.PRIMARY}; color: {p.PRIMARY_TEXT}; font-weight: 600; }}
QPushButton[kind="primary"]:hover {{ background: {p.PRIMARY_HOVER}; border-color: {p.PRIMARY_HOVER}; }}
QPushButton[kind="primary"]:pressed {{ background: {p.PRIMARY_PRESSED}; border-color: {p.PRIMARY_PRESSED}; }}
QPushButton[kind="primary"]:disabled {{ background: {p.SELECTION}; border-color: {p.SELECTION}; color: {p.TEXT_DISABLED}; }}

QPushButton[kind="danger"] {{ background: {p.DANGER}; border: 1px solid {p.DANGER}; color: #ffffff; font-weight: 600; }}
QPushButton[kind="danger"]:hover {{ background: {p.DANGER_HOVER}; border-color: {p.DANGER_HOVER}; }}
QPushButton[kind="danger"]:disabled {{ background: {p.SURFACE}; border-color: {p.BORDER_SOFT}; color: {p.TEXT_DISABLED}; }}

QPushButton[kind="ghost"] {{ background: transparent; border: 1px solid {p.BORDER}; }}
QPushButton[kind="ghost"]:hover {{ background: {p.SURFACE}; border-color: {p.BORDER_STRONG}; }}

/* ---- 输入框 ---- */
QLineEdit {{
    background: {p.BG_INPUT};
    color: {p.TEXT};
    border: 1px solid {p.BORDER};
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: {p.SELECTION};
    selection-color: {p.TEXT_STRONG};
}}
QLineEdit:hover {{ border-color: {p.BORDER_STRONG}; }}
QLineEdit:focus {{ border: 1px solid {p.FOCUS}; }}
QLineEdit:disabled {{ color: {p.TEXT_DISABLED}; }}

/* ---- 下拉框 ---- */
QComboBox {{
    background: {p.BG_INPUT};
    color: {p.TEXT};
    border: 1px solid {p.BORDER};
    border-radius: 8px;
    padding: 7px 10px;
}}
QComboBox:hover {{ border-color: {p.BORDER_STRONG}; }}
QComboBox:focus, QComboBox:on {{ border-color: {p.FOCUS}; }}
QComboBox::drop-down {{ border: none; background: transparent; width: 28px; }}
QComboBox::down-arrow {{
    image: url("{_asset_url('chevron-down.svg')}");
    width: 12px; height: 12px;
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background: {p.SURFACE};
    color: {p.TEXT};
    border: 1px solid {p.BORDER};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {p.SELECTION};
    selection-color: {p.TEXT_STRONG};
}}

/* ---- 列表 ---- */
QListWidget {{
    background: {p.BG_INPUT};
    color: {p.TEXT};
    border: 1px solid {p.BORDER};
    border-radius: 8px;
    padding: 4px;
}}
QListWidget::item {{ padding: 7px 8px; border-radius: 6px; }}
QListWidget::item:hover {{ background: {p.SURFACE_HOVER}; }}
QListWidget::item:selected {{ background: {p.SELECTION}; color: {p.TEXT_STRONG}; }}

/* ---- 日志 ---- */
QTextEdit#logView {{
    background: {p.LOG_BG};
    color: {p.LOG_TEXT};
    border: 1px solid {p.BORDER_SOFT};
    border-radius: 10px;
    padding: 8px;
}}

/* ---- 分段按钮组 ---- */
QFrame#segmented {{
    background: {p.BG_INPUT};
    border: 1px solid {p.BORDER};
    border-radius: 9px;
}}
QPushButton#segment {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 6px 18px;
    color: {p.TEXT_MUTED};
    font-size: 13px;
    min-height: 22px;
}}
QPushButton#segment:hover {{ color: {p.TEXT}; }}
QPushButton#segment:checked {{ background: {p.SELECTION}; color: {p.TEXT_STRONG}; font-weight: 600; }}

/* ---- 复选 / 开关（原生）---- */
QCheckBox {{ color: {p.TEXT}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border: 1px solid {p.BORDER};
    border-radius: 5px;
    background: {p.BG_INPUT};
}}
QCheckBox::indicator:hover {{ border-color: {p.FOCUS}; }}
QCheckBox::indicator:checked {{ background: {p.THEME}; border-color: {p.THEME}; }}

/* ---- 滚动条 ---- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p.BORDER_STRONG}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p.BORDER}; border-radius: 5px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: {p.BORDER_STRONG}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
"""


def apply_theme(app, window=None) -> None:
    """设置默认字体（优先 Noto Sans）、Fluent 暗色 + 中性主题色，关闭 Mica，套用扁平 QSS。"""
    from PySide6.QtGui import QFont
    from qfluentwidgets import Theme, setTheme, setThemeColor

    font = QFont()
    font.setFamilies(FONT_FAMILIES)
    app.setFont(font)

    setTheme(Theme.DARK)
    setThemeColor(Palette.THEME)
    app.setStyleSheet(build_stylesheet())
    if window is not None:
        try:
            window.setMicaEffectEnabled(False)
        except Exception:
            pass
