#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# detector.py - 模板匹配 + 状态检测模块

import time
import logging
from pathlib import Path
from typing import Optional, Tuple, List
from enum import Enum

import numpy as np
import cv2

logger = logging.getLogger(__name__)


class GameState(Enum):
    MAIN_MENU = "main_menu"
    ZERO_SYSTEM_ENTRY = "zero_system_entry"
    CODEX_SELECT = "codex_select"
    TEAM_ENTER = "team_enter"
    BUFF_SELECT = "buff_select"
    ROOM_SELECT = "room_select"
    MAP_SCREEN = "map_screen"
    COMBAT = "combat"
    COMBAT_VICTORY = "combat_victory"
    CARD_REWARD = "card_reward"
    RESULT_NEXT = "result_next"
    EVENT_SCREEN = "event_screen"
    REST_SCREEN = "rest_screen"
    DEATH_SCREEN = "death_screen"
    EXTRACTION = "extraction"
    RETREAT = "retreat_btn"
    FATE_REWARD = "fate_reward"
    NEUTRAL_CARD_SKIP = "neutral_card_skip"
    SKIP_CONFIRM = "skip_confirm"
    REMOVE_CARD_EVENT = "remove_card_event"
    CONFIRM_OPTION = "confirm_option"
    CLOSE_VIEW = "close_view"
    CONTINUE_FORWARD = "continue_forward"
    CONFIRM_ACQUIRE = "confirm_acquire"
    SKIP_LEFTMOST = "skip_leftmost"
    CARD_REWARD_SKIP = "card_reward_skip"
    AUTO_BATTLE_OFF = "auto_battle_off"
    INSPIRATION_CARD = "inspiration_card"
    CARD_CONVERT = "card_convert"
    EVENT_DICE = "event_dice"
    SELECT_CHARACTER = "select_character"
    RUN_END_REWARDS = "run_end_rewards"
    WRONG_PAGE = "wrong_page"
    DELETE_SAVE = "delete_save"
    DICE_NEXT = "dice_next"
    CODEX_SYNTH = "codex_synth"
    DREAM_CONFIRM = "dream_confirm"
    CONFIRM = "confirm"
    BUG_CLOSE = "bug_close"
    SPARKLE_EVENT = "sparkle_event"
    CODEX_COMPLETE = "codex_complete"
    CLOSE_MISTOUCH = "close_mistouch"
    CARD_DUPLICATE = "card_duplicate"
    UNEXPECTED_ROOM = "unexpected_room"
    BOSS_NODE = "boss_node"
    UNKNOWN = "unknown"


class TemplateMatcher:
    def __init__(self, templates_dir: Path):
        self.templates: dict[str, np.ndarray] = {}
        self.threshold = 0.9
        if templates_dir and templates_dir.exists():
            for f in sorted(templates_dir.rglob("*")):
                if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"):
                    img = cv2.imread(str(f))
                    if img is not None:
                        if len(img.shape) == 3:
                            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                        self.templates[f.stem] = img
                        logger.info(f"Loaded template [{f.stem}] {img.shape[1]}x{img.shape[0]}")
            logger.info(f"Total {len(self.templates)} templates loaded")

    def match(self, frame: np.ndarray, template_name: str,
              threshold: Optional[float] = None) -> Tuple[bool, float, Optional[Tuple[int, int]]]:
        tpl = self.templates.get(template_name)
        if tpl is None:
            return False, 0.0, None
        th = threshold or self.threshold
        if len(frame.shape) == 3:
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            frame_gray = frame
        if len(tpl.shape) == 3:
            tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
        else:
            tpl_gray = tpl
        h, w = tpl_gray.shape[:2]
        res = cv2.matchTemplate(frame_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val >= th:
            cx = max_loc[0] + w // 2
            cy = max_loc[1] + h // 2
            return True, float(max_val), (cx, cy)
        return False, float(max_val), None

    def exists(self, name: str) -> bool:
        return name in self.templates

    def match_all(self, frame: np.ndarray, template_name: str,
                  threshold: Optional[float] = None) -> List[Tuple[float, int, int]]:
        tpl = self.templates.get(template_name)
        if tpl is None:
            return []
        th = threshold or self.threshold
        if len(frame.shape) == 3:
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            frame_gray = frame
        if len(tpl.shape) == 3:
            tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
        else:
            tpl_gray = tpl
        h, w = tpl_gray.shape[:2]
        res = cv2.matchTemplate(frame_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
        locs = np.where(res >= th)
        results = []
        for pt in zip(*locs[::-1]):
            cx = pt[0] + w // 2
            cy = pt[1] + h // 2
            results.append((float(res[pt[1], pt[0]]), cx, cy))
        results.sort(key=lambda x: x[1])  # sort by x (left to right)
        return results


class StateDetector:
    def __init__(self, matcher: TemplateMatcher):
        self.matcher = matcher
        self.last_state = GameState.UNKNOWN
        self.last_pos: Optional[Tuple[int, int]] = None
        self.last_template: Optional[str] = None
        self.last_conf: float = 0.0
        self.history: List[Tuple[float, GameState]] = []

    def detect(self, frame: np.ndarray) -> GameState:
        thresholds = {
            "auto_battle_off": 0.95,
            "wrong_page": 0.98,
            "codex_btn3": 0.95,
        }
        checks = [
            ("auto_battle_off", GameState.AUTO_BATTLE_OFF),
            ("combat_screen", GameState.COMBAT),
            ("combat_victory", GameState.COMBAT_VICTORY),
            ("confirm_option", GameState.CONFIRM_OPTION),
            ("card_reward", GameState.CARD_REWARD),
            ("wrong_page", GameState.WRONG_PAGE),
            ("select_character", GameState.SELECT_CHARACTER),
            ("strong_select", GameState.SELECT_CHARACTER),
            ("unex_select", GameState.SELECT_CHARACTER),
            ("skip_confirm", GameState.SKIP_CONFIRM),
            ("neutral_card_skip", GameState.NEUTRAL_CARD_SKIP),
            ("result_settle", GameState.RESULT_NEXT),
            ("settlement_click", GameState.RESULT_NEXT),
            ("node_settlement", GameState.RESULT_NEXT),
            ("next_step", GameState.RESULT_NEXT),
            ("dismantle_confirm", GameState.RESULT_NEXT),
            ("dismantle_equip", GameState.RESULT_NEXT),
            ("fate_reward", GameState.FATE_REWARD),
            ("event_screen", GameState.EVENT_SCREEN),
            ("event_option", GameState.EVENT_SCREEN),
            ("event_option2", GameState.EVENT_SCREEN),
            ("event_fallback", GameState.EVENT_SCREEN),
            ("event_dice", GameState.EVENT_DICE),
            ("dice_next", GameState.DICE_NEXT),
            ("rest_alt", GameState.REST_SCREEN),
            ("rest_screen", GameState.REST_SCREEN),
            ("death_screen", GameState.DEATH_SCREEN),
            ("extraction_screen", GameState.EXTRACTION),
            ("room_battle", GameState.ROOM_SELECT),
            ("room_elite", GameState.ROOM_SELECT),
            ("room_event", GameState.ROOM_SELECT),
            ("room_rest", GameState.ROOM_SELECT),
            ("room_fallback", GameState.ROOM_SELECT),  # 节点选择保底
            ("map_screen", GameState.MAP_SCREEN),
            ("boss_node", GameState.BOSS_NODE),
            ("team_enter", GameState.TEAM_ENTER),
            ("team_confirm", GameState.TEAM_ENTER),
            ("codex_select", GameState.CODEX_SELECT),
            ("codex_synth", GameState.CODEX_SYNTH),
            ("codex_btn0", GameState.CODEX_SYNTH),
            ("codex_btn1", GameState.CODEX_SYNTH),
            ("codex_btn2", GameState.CODEX_SYNTH),
            ("codex_btn3", GameState.CODEX_SYNTH),
            ("codex_btn4", GameState.CODEX_SYNTH),
            ("codex_complete", GameState.CODEX_COMPLETE),
            ("codex_complete2", GameState.CODEX_COMPLETE),
            ("zero_system_entry", GameState.ZERO_SYSTEM_ENTRY),
            ("main_menu", GameState.MAIN_MENU),
            ("retreat_btn", GameState.RETREAT),
            ("remove_card_event", GameState.REMOVE_CARD_EVENT),
            ("close_view", GameState.CLOSE_VIEW),
            ("continue_forward", GameState.CONTINUE_FORWARD),
            ("continue_forward2", GameState.CONTINUE_FORWARD),
            ("choose_fate", GameState.CONFIRM_ACQUIRE),
            ("confirm_acquire", GameState.CONFIRM_ACQUIRE),
            ("confirm", GameState.CONFIRM),
            ("skip_leftmost", GameState.SKIP_LEFTMOST),
            ("card_reward_skip", GameState.CARD_REWARD_SKIP),
            ("inspiration_card", GameState.INSPIRATION_CARD),
            ("card_convert", GameState.CARD_CONVERT),
            ("select_character", GameState.SELECT_CHARACTER),
            ("strong_select", GameState.SELECT_CHARACTER),
            ("delete_save", GameState.DELETE_SAVE),
            ("settlement_confirm", GameState.RESULT_NEXT),  # 取消选择装备
            ("dream_confirm", GameState.DREAM_CONFIRM),
            ("buff_select", GameState.BUFF_SELECT),
            ("unexpected_room", GameState.UNEXPECTED_ROOM),
            ("bug_close", GameState.BUG_CLOSE),
            ("sparkle_event", GameState.SPARKLE_EVENT),
            ("close_mistouch", GameState.CLOSE_MISTOUCH),
            ("card_duplicate", GameState.CARD_DUPLICATE),
        ]
        for tpl_name, state in checks:
            if self.matcher.exists(tpl_name):
                th = thresholds.get(tpl_name, 0.9)
                found, conf, pos = self.matcher.match(frame, tpl_name, threshold=th)
                if found:
                    logger.debug(f"State: {state.value} (conf={conf:.3f})")
                    self.last_state = state
                    self.last_pos = pos
                    self.last_conf = conf
                    self.last_template = tpl_name
                    self.history.append((time.time(), state))
                    if len(self.history) > 20:
                        self.history.pop(0)
                    return state
        fallback = self._fallback_detect(frame)
        if fallback != GameState.UNKNOWN:
            return fallback
        logger.debug("State: unknown")
        self.last_state = GameState.UNKNOWN
        return GameState.UNKNOWN

    def _fallback_detect(self, frame: np.ndarray) -> GameState:
        return GameState.UNKNOWN
