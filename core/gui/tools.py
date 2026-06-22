#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""辅助工具：模板采集（F7 截图 / Esc 退出）与一键诊断。仅写日志，不触碰 UI。"""
import ctypes
import ctypes.wintypes
import datetime
import logging
import threading
import time
from pathlib import Path

import cv2

from core.screencap import CaptureMethod, ScreenCapturer
from core.matcher import StateDetector, TemplateMatcher, load_pixel_checks

from .config_manager import ConfigManager
from .constants import DEBUG_DIR


def _imwrite_unicode(path: Path, img) -> bool:
    ret, buf = cv2.imencode(".png", img)
    if ret:
        with open(str(path), "wb") as f:
            f.write(buf.tobytes())
        return True
    return False


def grab_game_frame(cfg_mgr: ConfigManager):
    """按当前配置抓取一帧归一化游戏画面（BGR ndarray）。供调试页即时取画面。"""
    g = cfg_mgr.data.get("game", {})
    method = g.get("capture_method", CaptureMethod.DEFAULT.value)
    title = g.get("window_title", "卡厄思梦境")

    cap = ScreenCapturer(method=method)
    hwnd = ctypes.windll.user32.FindWindowW(None, title)
    if hwnd:
        cap.set_window(hwnd)
    try:
        return cap.capture_game_area(), bool(hwnd)
    finally:
        cap.close()


class CaptureService:
    """模板采集：后台线程轮询热键，F7 保存截图，Esc 结束。"""

    def __init__(self, cfg_mgr: ConfigManager):
        self.cfg = cfg_mgr
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            logging.warning("采集已在运行")
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        g = self.cfg.data.get("game", {})
        method = g.get("capture_method", CaptureMethod.DEFAULT.value)
        title = g.get("window_title", "卡厄思梦境")
        tdir = self.cfg.profile_dir()
        tdir.mkdir(parents=True, exist_ok=True)

        cap = ScreenCapturer(method=method)
        hwnd = ctypes.windll.user32.FindWindowW(None, title)
        if hwnd:
            cap.set_window(hwnd)

        logging.info(f"=== 模板采集模式 [{self.cfg.profile}] 捕获方式={method} ===")
        logging.info(f"目录: {tdir.resolve()}")
        logging.info("F7=保存截图  Esc=退出")

        import keyboard as kb
        cnt = 0
        while True:
            if kb.is_pressed("f7"):
                cnt += 1
                frame = cap.capture()
                ts = datetime.datetime.now().strftime("%H%M%S")
                path = tdir / f"template_{cnt:02d}_{ts}.png"
                if _imwrite_unicode(path, frame):
                    logging.info(f"已保存({cnt}): {path.resolve()}")
                else:
                    logging.error(f"写入失败: {path}")
                time.sleep(0.5)
            if kb.is_pressed("esc"):
                logging.info(f"采集完成! 共 {cnt} 张 -> {tdir.name}")
                break
            time.sleep(0.1)


class DiagnoseService:
    """一键诊断：定位窗口、截图、识别当前状态并打印信息。"""

    def __init__(self, cfg_mgr: ConfigManager):
        self.cfg = cfg_mgr

    def run(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        user32 = ctypes.windll.user32
        cfg = self.cfg.data
        tdir = self.cfg.profile_dir()
        tdir.mkdir(parents=True, exist_ok=True)

        method = cfg.get("game", {}).get("capture_method", CaptureMethod.DEFAULT.value)
        cap = ScreenCapturer(method=method)
        matcher = TemplateMatcher(tdir)
        detector = StateDetector(matcher, load_pixel_checks(cfg.get("template_profile")))

        title = cfg.get("game", {}).get("window_title", "卡厄思梦境")
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            cap.set_window(hwnd)

        logging.info("=" * 40)
        logging.info(f"诊断模式 [{self.cfg.profile}] 捕获方式={method}")
        if hwnd:
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w, h = rect.right - rect.left, rect.bottom - rect.top
            logging.info("   找到游戏窗口")
            logging.info(f"      标题: {title}  句柄: {hwnd}")
            logging.info(f"      位置: ({rect.left},{rect.top})  {w}x{h}")
        else:
            logging.info(f"   未找到窗口 [{title}]，请确认窗口标题")

        frame = cap.capture()
        res = cap.get_resolution()
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H%M%S")
        diag_file = DEBUG_DIR / f"diagnose_{ts}.png"
        _imwrite_unicode(diag_file, frame)

        state = detector.detect(frame)
        logging.info(f"   分辨率 {res[0]}x{res[1]}")
        logging.info(f"   模板数: {len(matcher.templates)}")
        logging.info(f"   当前状态 [{state.value}]")
        logging.info(f"   诊断图: {diag_file.resolve()}")
        logging.info("=" * 40)
