#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ADB 调用底座：定位内置 adb.exe，封装设备枚举 / 截屏 / 点击。

输入、捕获、设备发现三条通道都复用本模块，避免在各后端里重复
``subprocess`` 逻辑。adb.exe 内置在项目 ``bin/adb/`` 目录（随打包一并分发），
开发态指向项目根，打包态优先用 ``sys._MEIPASS``。
"""
import logging
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

# CreateProcess 标志：不弹出控制台窗口
_CREATE_NO_WINDOW = 0x08000000


def _base_dirs() -> List[Path]:
    """返回查找内置 adb 的候选根目录（按优先级）。"""
    dirs: List[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            dirs.append(Path(meipass))
        dirs.append(Path(sys.executable).parent)
    else:
        # client.py -> core/adb/client.py，parents[2] 即项目根
        dirs.append(Path(__file__).resolve().parents[2])
    return dirs


def adb_path() -> str:
    """返回内置 adb.exe 的绝对路径；未内置时兜底用 PATH 上的 ``adb``。"""
    for base in _base_dirs():
        p = base / "bin" / "adb" / "adb.exe"
        if p.exists():
            return str(p)
    return "adb"


def run(args, serial: Optional[str] = None, timeout: int = 15) -> Optional[subprocess.CompletedProcess]:
    """执行一条 adb 命令，返回 ``CompletedProcess``（stdout/stderr 为 bytes）。

    出错（超时 / adb 缺失）返回 ``None``，由调用方兜底。
    """
    cmd = [adb_path()]
    if serial:
        cmd += ["-s", serial]
    cmd += [str(a) for a in args]
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
    except FileNotFoundError:
        logging.error("未找到 adb 可执行文件，请确认 bin/adb/adb.exe 存在")
        return None
    except subprocess.TimeoutExpired:
        logging.warning(f"adb 命令超时: {' '.join(map(str, args))}")
        return None
    except Exception as e:
        logging.warning(f"adb 命令执行失败({e}): {' '.join(map(str, args))}")
        return None


def list_devices() -> List[str]:
    """枚举处于 ``device`` 状态的设备 serial。"""
    cp = run(["devices"])
    if cp is None:
        return []
    out = cp.stdout.decode("utf-8", "ignore")
    devices: List[str] = []
    for line in out.splitlines()[1:]:  # 跳过 "List of devices attached"
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def screencap(serial: str) -> Optional[np.ndarray]:
    """抓取设备屏幕，返回 BGR ``np.ndarray``，失败返回 None。"""
    if not serial:
        return None
    cp = run(["exec-out", "screencap", "-p"], serial=serial, timeout=10)
    if cp is None or not cp.stdout:
        return None
    arr = np.frombuffer(cp.stdout, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        logging.debug(f"[adb] 截屏解码失败 (serial={serial})")
    return img


def tap(serial: str, x: int, y: int) -> None:
    """在设备 (x, y) 处模拟一次点击。"""
    if not serial:
        logging.warning("ADB 点击被忽略：未绑定设备")
        return
    run(["shell", "input", "tap", str(int(x)), str(int(y))], serial=serial, timeout=10)
