# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置 —— CZN Zero Farm GUI
# 本 spec 位于 packaging/ 子目录。入口：core/gui/__main__.py，单文件 exe。
# config.json / templates 目录 / logs 由 build.bat 放到 exe 同目录，
# 运行时从 exe 所在目录读取（见各模块 BASE_DIR 处理），保证可编辑、可采集模板。

import os

from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs, collect_data_files

# spec 在 packaging/ 下，项目根 = spec 目录的上一级；用绝对路径，使打包不依赖运行目录
ROOT = os.path.dirname(os.path.abspath(SPECPATH))
ICON_FILE = os.path.join(SPECPATH, "app_icon.ico")

# WinRT（Windows OCR）相关命名空间需要显式收集子模块
hiddenimports = []
for pkg in [
    "winrt",
    "winrt.windows.media.ocr",
    "winrt.windows.globalization",
    "winrt.windows.graphics.imaging",
    "winrt.windows.storage.streams",
    "winrt.windows.foundation",
    "winrt.windows.foundation.collections",
]:
    try:
        hiddenimports += collect_submodules(pkg)
    except Exception:
        hiddenimports.append(pkg)

hiddenimports += [
    "windows_capture",
    "dxcam",
    "keyboard",
    "mss",
]
# Fluent GUI 依赖
hiddenimports += collect_submodules("qfluentwidgets")

# qfluentwidgets 自带 QSS / 字体 / 图标资源，需随包打入
datas = []
try:
    datas += collect_data_files("qfluentwidgets")
except Exception:
    pass
# 自定义 GUI 资源（扁平主题的下拉箭头等 SVG）
datas += [(os.path.join(ROOT, "core", "gui", "assets", "*"), "core/gui/assets")]
# 应用图标（运行时窗口/任务栏图标；exe 本体图标见下方 EXE 的 icon 参数）
datas += [(ICON_FILE, ".")]

# windows_capture / winrt 含原生扩展，收集其动态库
binaries = []
for pkg in ["windows_capture", "winrt"]:
    try:
        binaries += collect_dynamic_libs(pkg)
    except Exception:
        pass

# 排除体积庞大且默认不使用的依赖（默认 OCR 后端为 Windows OCR）
excludes = [
    "paddle",
    "paddleocr",
    "paddlex",
    "paddlepaddle",
    "matplotlib",
    "scipy",
    "pandas",
    "PyQt5",
    "PySide2",
    "PIL.ImageQt",
]


a = Analysis(
    [os.path.join(ROOT, "core", "gui", "__main__.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CZN_Zero_Farm",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_FILE,
)
