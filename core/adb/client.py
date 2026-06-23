#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ADB 调用底座：定位内置 adb.exe，封装设备枚举 / 截屏 / 点击。

输入、捕获、设备发现三条通道都复用本模块，避免在各后端里重复
``subprocess`` 逻辑。adb.exe 内置在项目 ``bin/adb/`` 目录（随打包一并分发），
开发态指向项目根，打包态优先用 ``sys._MEIPASS``。
"""
import logging
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

# CreateProcess 标志：不弹出控制台窗口
_CREATE_NO_WINDOW = 0x08000000

# 常见模拟器 adb 端口（需 ``adb connect`` 后才会出现在 ``adb devices``）。
# 涵盖 5550-5585 连续段（AVD/雷电/通用）+ 各家模拟器默认端口。
DEFAULT_EMULATOR_PORTS: List[int] = sorted({
    *range(5550, 5586),  # 通用：AVD(5555) / 雷电(5555,5557…) / 多开
    7555,                # MuMu / 网易
    16384,               # MuMu Pro / MuMu12
    21503,               # MEmu 逍遥
    62001, 62025, 62026,  # Nox 夜神
})


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


def _port_open(host: str, port: int, timeout: float = 0.15) -> bool:
    """快速探测 TCP 端口是否可连接（避免对关闭端口执行慢速 adb connect）。"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def connect_emulators(ports: Optional[List[int]] = None, host: str = "127.0.0.1") -> List[str]:
    """探测常见模拟器端口并 ``adb connect``，返回成功连接的地址列表。

    先并发做 TCP 探活，只对开放端口执行 ``adb connect``，避免对关闭端口逐个等待。
    """
    ports = ports or DEFAULT_EMULATOR_PORTS

    open_ports: List[int] = []
    try:
        with ThreadPoolExecutor(max_workers=16) as ex:
            for port, ok in zip(ports, ex.map(lambda p: _port_open(host, p), ports)):
                if ok:
                    open_ports.append(port)
    except Exception as e:
        logging.debug(f"[adb] 端口探测异常: {e}")
        return []

    connected: List[str] = []
    for port in open_ports:
        addr = f"{host}:{port}"
        cp = run(["connect", addr], timeout=5)
        if cp is None:
            continue
        out = (cp.stdout or b"").decode("utf-8", "ignore").lower()
        if "connected" in out:  # 命中 "connected to" / "already connected to"
            connected.append(addr)
    if connected:
        logging.info(f"[adb] 已连接模拟器: {', '.join(connected)}")
    return connected


def list_devices(connect_emulators_first: bool = False) -> List[str]:
    """枚举处于 ``device`` 状态的设备 serial。

    ``connect_emulators_first=True`` 时先探测常见模拟器端口并自动连接，
    再枚举（供首页刷新使用，让未 connect 的模拟器也能出现）。
    """
    if connect_emulators_first:
        connect_emulators()
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
