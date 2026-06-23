#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# main.py - 零式系统自动刷取脚本 主入口
import os
import sys
import json
import time
import ctypes
import logging
import threading
import datetime

from pathlib import Path
from typing import Optional

import cv2
import keyboard

# 进程级 DPI 感知：必须在任何窗口/截图调用之前设置，保证 GetWindowRect、
# GetSystemMetrics 与截图后端统一使用物理像素（否则高 DPI 屏下坐标错位）。
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from core.screencap import CaptureMethod, ScreenCapturer
from core.input import InputSimulator
from core.keepawake import KeepAwake
from core.matcher import TemplateMatcher, StateDetector, GameState, load_pixel_checks
from core.combat import CombatModule

# --- Paths ---
# 打包成 exe(冻结)后，资源/配置应位于 exe 同目录，便于用户编辑与采集模板
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
LOGS_DIR = BASE_DIR / "logs"
DEBUG_DIR = BASE_DIR / "debug"

def _get_templates_dir():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return BASE_DIR / json.load(f).get("template_profile", "templates_cn")

# --- Globals ---
running = True
paused = False
config = None
logger = None


# ======================================================================
# Config
# ======================================================================
class Config:
    def __init__(self, path: Path):
        with open(path, encoding="utf-8") as f:
            self.raw = json.load(f)
        g = self.raw["game"]
        self.window_title = g["window_title"]
        self.base_res = tuple(g["resolution"])
        self.input_backend = g.get("input_backend", "sendinput")
        self.hotkey_stop = self.raw["hotkey"].get("stop", "f8")
        self.hotkey_pause = self.raw["hotkey"].get("pause", "f9")
        self.click_points = self.raw["click_points"]
        self.card_hand = self.raw["card_hand"]
        self.combat = self.raw["combat"]
        self.map_nav = self.raw["map_navigation"]
        self.timing = self.raw["timing"]
        self.debug_screenshots = self.raw["logging"].get("debug_screenshots", False)


# ======================================================================
# Logging
# ======================================================================
def setup_logging():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"czn_zero_{ts}.log"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", datefmt="%H:%M:%S")

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    root.addHandler(console)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    logging.info(f"Log: {log_file}")
    return root


# ======================================================================
# Hotkeys
# ======================================================================
def on_stop():
    global running
    logging.info(">>> STOP hotkey pressed <<<")
    running = False


def on_pause():
    global paused
    paused = not paused
    logging.info(f"{'PAUSED' if paused else 'RESUMED'}")


def setup_hotkeys(cfg: Config):
    try:
        keyboard.add_hotkey(cfg.hotkey_stop, on_stop)
        keyboard.add_hotkey(cfg.hotkey_pause, on_pause)
        logging.info(f"Hotkeys: [{cfg.hotkey_stop}] stop, [{cfg.hotkey_pause}] pause")
    except Exception as e:
        logging.warning(f"Hotkey setup failed (may need admin): {e}")


# ======================================================================
# Debug screenshot
# ======================================================================
def save_debug(frame, prefix=""):
    if not config.debug_screenshots:
        return
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%H%M%S_%f")[:12]
    name = f"{prefix}_{ts}.png" if prefix else f"{ts}.png"
    cv2.imwrite(str(DEBUG_DIR / name), frame)


# ======================================================================
# Run stats
# ======================================================================
class RunStats:
    def __init__(self):
        self.reset()

    def reset(self):
        self.battles = 0
        self.elites = 0
        self.events = 0
        self.floors = 0
        self.runs = 0
        self.start_time = time.time()
        self.run_start = time.time()

    def new_run(self):
        self.runs += 1
        self.run_start = time.time()
        logging.info(f"=== Run #{self.runs} started ===")

    def print_status(self):
        elapsed = time.time() - self.start_time
        h, m = divmod(int(elapsed), 3600)
        m, s = divmod(m, 60)
        logging.info(
            f"[Stats] Runs:{self.runs} Battles:{self.battles} Elites:{self.elites} "
            f"Floors:{self.floors} Events:{self.events} Time:{h}h{m:02d}m{s:02d}s"
        )


# ======================================================================
# State machine - handle each game state
# ======================================================================
def handle_state(state: GameState, frame, res, sim, combat_mod: CombatModule, stats: RunStats):
    timing = config.timing

    if state == GameState.MAIN_MENU:
        logging.info("State: MAIN_MENU -> entering Zero System")
        sim.click_config("main_menu_zero_entry", res, config)
        time.sleep(timing["post_click_wait"])

    elif state == GameState.ZERO_SYSTEM_ENTRY:
        logging.info("State: ZERO_SYSTEM_ENTRY -> selecting codex")
        sim.click_config("codex_first", res, config)
        time.sleep(timing["post_click_wait"])

    elif state == GameState.CODEX_SELECT:
        logging.info("State: CODEX_SELECT -> entering dungeon")
        sim.click_config("enter_confirm", res, config)
        time.sleep(timing["post_click_wait"])
        stats.new_run()

    elif state == GameState.MAP_SCREEN:
        logging.info("State: MAP -> navigating to node")
        sim.click_config("map_node_default", res, config)
        time.sleep(timing["post_click_wait"])

    elif state == GameState.COMBAT:
        logging.info(f"State: COMBAT (turn {combat_mod.turn_count + 1})")
        combat_mod.execute_turn(frame, res, sim, config)
        time.sleep(timing.get("screenshot_interval", 0.5))

    elif state == GameState.COMBAT_VICTORY:
        logging.info("State: COMBAT_VICTORY")
        stats.battles += 1
        combat_mod.reset_battle()
        time.sleep(timing["post_click_wait"])
        sim.click_config("reward_confirm", res, config)
        time.sleep(1.0)

    elif state == GameState.CARD_REWARD:
        logging.info("State: CARD_REWARD -> selecting")
        sim.click_config("reward_confirm", res, config)
        time.sleep(timing["post_click_wait"])

    elif state == GameState.EVENT_SCREEN:
        logging.info("State: EVENT -> choosing first option")
        stats.events += 1
        sim.click_config("event_choice_first", res, config)
        time.sleep(timing["post_click_wait"])

    elif state == GameState.REST_SCREEN:
        logging.info("State: REST -> healing")
        sim.click_config("rest_heal", res, config)
        time.sleep(timing["post_click_wait"])

    elif state == GameState.DEATH_SCREEN:
        logging.info("State: DEATH -> exiting run")
        combat_mod.reset_battle()
        stats.print_status()
        sim.click_config("run_exit_confirm", res, config)
        time.sleep(timing["post_click_wait"])
        sim.click_config("extraction_confirm", res, config)
        time.sleep(timing.get("between_runs_delay", 3.0))

    elif state == GameState.EXTRACTION:
        logging.info("State: EXTRACTION -> confirming rewards")
        sim.click_config("extraction_confirm", res, config)
        time.sleep(timing["post_click_wait"])

    elif state == GameState.RUN_END_REWARDS:
        logging.info("State: RUN_END -> confirming")
        sim.click_config("extraction_confirm", res, config)
        time.sleep(timing["post_click_wait"])

    elif state == GameState.UNKNOWN:
        pass  # Re-check on next cycle

    else:
        logging.warning(f"Unhandled state: {state}")


# ======================================================================
# Collect templates by pressing F6
# ======================================================================
def template_capture_loop(capturer):
    logging.info("=== TEMPLATE CAPTURE MODE ===")
    logging.info("Press F6 to save current screen as template")
    logging.info("Press Esc to exit capture mode")
    tdir = _get_templates_dir()
    tdir.mkdir(parents=True, exist_ok=True)
    counter = 0
    while True:
        if keyboard.is_pressed("f6"):
            counter += 1
            frame = capturer.capture()
            ts = datetime.datetime.now().strftime("%H%M%S")
            name = f"template_{counter:02d}_{ts}.png"
            path = tdir / name
            cv2.imwrite(str(path), frame)
            logging.info(f"Saved template to {tdir.name}: {name}")
            time.sleep(0.5)
        if keyboard.is_pressed("esc"):
            logging.info(f"Template capture done. {counter} templates saved.")
            break
        time.sleep(0.1)


# ======================================================================
# Main loop
# ======================================================================
def main_loop(capturer, detector, sim, combat_mod, stats):
    global running, paused
    logger = logging.getLogger()
    consecutive_unknown = 0
    max_unknown = 20

    logger.info("=== Zero System Farm started ===")
    logger.info(f"Press [{config.hotkey_stop}] to stop, [{config.hotkey_pause}] to pause")

    keep_awake = KeepAwake()
    if config.raw.get("game", {}).get("prevent_lock", True):
        keep_awake.enable()

    while running:
        try:
            if paused:
                time.sleep(0.5)
                continue

            frame = capturer.capture()
            res = capturer.get_resolution()
            save_debug(frame, "live")

            state = detector.detect(frame)

            if state == GameState.UNKNOWN:
                consecutive_unknown += 1
                if consecutive_unknown >= max_unknown:
                    logger.warning(f"Unknown state for {max_unknown} consecutive checks, clicking default")
                    sim.click_config("map_node_default", res, config)
                    time.sleep(1.0)
                    consecutive_unknown = 0
                else:
                    time.sleep(config.timing["screenshot_interval"])
                continue
            else:
                consecutive_unknown = 0

            handle_state(state, frame, res, sim, combat_mod, stats)

            time.sleep(config.timing["screenshot_interval"])

            # Status every 5 minutes
            if int(time.time()) % 300 == 0:
                stats.print_status()

        except KeyboardInterrupt:
            running = False
            break
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            time.sleep(2.0)

    keep_awake.disable()
    stats.print_status()
    logger.info("=== Zero System Farm stopped ===")


# ======================================================================
# Entry point
# ======================================================================
def main():
    global config, logger

    # Check --capture flag
    if "--capture" in sys.argv:
        setup_logging()
        config = Config(CONFIG_PATH)
        cap = ScreenCapturer(method=config.raw.get("game", {}).get("capture_method", CaptureMethod.DEFAULT.value))
        hwnd = ctypes.windll.user32.FindWindowW(None, config.window_title)
        if hwnd:
            cap.set_window(hwnd)
        template_capture_loop(cap)
        return

    # Check --help
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: python main.py [options]")
        print("  (no args)   Run the bot")
        print("  --capture   Template capture mode (F6=save template, Esc=exit)")
        print("  --help      Show this help")
        return

    # Normal startup
    config = Config(CONFIG_PATH)
    logger = setup_logging()
    logger.info("CZN Zero Farm v1.0")

    tdir = _get_templates_dir()
    capturer = ScreenCapturer(method=config.raw.get("game", {}).get("capture_method", CaptureMethod.DEFAULT.value))
    hwnd = ctypes.windll.user32.FindWindowW(None, config.window_title)
    if hwnd:
        capturer.set_window(hwnd)
        logger.info(f"锁定游戏窗口: {config.window_title} 句柄={hwnd} 捕获方式={capturer.method}")
    matcher = TemplateMatcher(tdir)
    detector = StateDetector(matcher, load_pixel_checks(config.raw.get("template_profile")))
    sim = InputSimulator(backend=config.raw.get("game", {}).get("input_backend", "sendinput"))
    combat_mod = CombatModule()
    stats = RunStats()

    setup_hotkeys(config)

    if not tdir.exists() or not any(tdir.iterdir()):
        logger.warning(f"No templates found in {tdir.name}/")
        logger.warning("Run 'python main.py --capture' to capture templates first")

    try:
        main_loop(capturer, detector, sim, combat_mod, stats)
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
    finally:
        stats.print_status()
        logging.info("Bye!")


if __name__ == "__main__":
    main()

