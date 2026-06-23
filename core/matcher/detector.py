#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""状态检测编排。

``StateDetector`` 不实现匹配算法，只负责把 ``TemplateMatcher``（模板匹配）与
``PixelChecker``（像素判断）按优先级编排起来：以有序模板匹配为主，像素规则按
``before`` 混入序列，第一个命中即返回对应 ``GameState`` 并记录 last_* 现场。
"""
import time
import logging
from typing import List, Optional, Tuple

import numpy as np

from .states import GameState
from .template import TemplateMatcher
from .pixel import PixelChecker, PixelRule
from .checks import STATE_CHECKS, TEMPLATE_THRESHOLDS, DEFAULT_THRESHOLD

logger = logging.getLogger(__name__)


class StateDetector:
    HISTORY_LIMIT = 20

    def __init__(self, matcher: TemplateMatcher,
                 pixel_checks: Optional[List[dict]] = None):
        self.matcher = matcher
        self.pixel_checker = PixelChecker(pixel_checks or [])
        self.last_state = GameState.UNKNOWN
        self.last_pos: Optional[Tuple[int, int]] = None
        self.last_template: Optional[str] = None
        self.last_conf: float = 0.0
        self.history: List[Tuple[float, GameState]] = []

    @property
    def pixel_checks(self) -> List[PixelRule]:
        """兼容旧访问方式，返回已解析的像素规则。"""
        return self.pixel_checker.rules

    def _build_ordered(self) -> List[Tuple[str, object, GameState]]:
        """将像素规则按 before 混入模板优先级序列。

        - 指定 before="模板名" 的像素规则，插到该模板检查之前；
        - 未指定 before 的，统一放到所有模板最前（优先级最高）。
        """
        if not self.pixel_checker.enabled:
            return [("tpl", name, state) for name, state in STATE_CHECKS]

        ordered: List[Tuple[str, object, GameState]] = []
        before_map: dict = {}
        for rule in self.pixel_checker.rules:
            if rule.before:
                before_map.setdefault(rule.before, []).append(rule)
            else:
                ordered.append(("pixel", rule, rule.state))
        for tpl_name, state in STATE_CHECKS:
            for rule in before_map.get(tpl_name, []):
                ordered.append(("pixel", rule, rule.state))
            ordered.append(("tpl", tpl_name, state))
        return ordered

    def _record(self, state: GameState, pos: Optional[Tuple[int, int]],
                conf: float, template: Optional[str]) -> None:
        self.last_state = state
        self.last_pos = pos
        self.last_conf = conf
        self.last_template = template
        self.history.append((time.time(), state))
        if len(self.history) > self.HISTORY_LIMIT:
            self.history.pop(0)

    def detect(self, frame: np.ndarray,
               skip_templates: Optional[set] = None,
               skip_pixel: bool = False) -> GameState:
        for kind, key, state in self._build_ordered():
            if kind == "pixel":
                if skip_pixel:
                    continue
                rule: PixelRule = key
                hit, pos = self.pixel_checker.match(frame, rule)
                if hit:
                    logger.debug(f"State: {state.value} (pixel {rule.name})")
                    self._record(state, pos, 1.0, rule.name)
                    return state
                continue

            tpl_name = key
            if skip_templates and tpl_name in skip_templates:
                continue
            if self.matcher.exists(tpl_name):
                th = TEMPLATE_THRESHOLDS.get(tpl_name, DEFAULT_THRESHOLD)
                found, conf, pos = self.matcher.match(frame, tpl_name, threshold=th)
                if found:
                    logger.debug(f"State: {state.value} (conf={conf:.3f})")
                    self._record(state, pos, conf, tpl_name)
                    return state

        fallback = self._fallback_detect(frame)
        if fallback != GameState.UNKNOWN:
            return fallback
        logger.debug("State: unknown")
        self.last_state = GameState.UNKNOWN
        return GameState.UNKNOWN

    def _fallback_detect(self, frame: np.ndarray) -> GameState:
        return GameState.UNKNOWN
