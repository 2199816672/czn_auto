#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模板匹配。

``TemplateMatcher`` 负责单一职责：从模板目录加载灰度模板，并对帧做
OpenCV ``TM_CCOEFF_NORMED`` 模板匹配。不感知任何游戏状态语义。
"""
import logging
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import cv2

logger = logging.getLogger(__name__)

# 模板匹配默认相似度阈值
DEFAULT_THRESHOLD = 0.8

_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp")


class TemplateMatcher:
    """加载模板图并对帧做模板匹配。"""

    def __init__(self, templates_dir: Optional[Path]):
        self.templates: dict[str, np.ndarray] = {}
        self.threshold = DEFAULT_THRESHOLD
        self._load(templates_dir)

    def _load(self, templates_dir: Optional[Path]) -> None:
        if not (templates_dir and templates_dir.exists()):
            return
        for f in sorted(templates_dir.rglob("*")):
            if not (f.is_file() and f.suffix.lower() in _IMAGE_SUFFIXES):
                continue
            img = cv2.imread(str(f))
            if img is None:
                continue
            if len(img.shape) == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            self.templates[f.stem] = img
            logger.info(f"Loaded template [{f.stem}] {img.shape[1]}x{img.shape[0]}")
        logger.info(f"Total {len(self.templates)} templates loaded")

    @staticmethod
    def _to_gray(img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    def exists(self, name: str) -> bool:
        return name in self.templates

    def match(self, frame: np.ndarray, template_name: str,
              threshold: Optional[float] = None
              ) -> Tuple[bool, float, Optional[Tuple[int, int]]]:
        """返回 (是否命中, 最高相似度, 中心点坐标)。"""
        tpl = self.templates.get(template_name)
        if tpl is None or frame is None or frame.size == 0:
            return False, 0.0, None
        th = threshold or self.threshold
        frame_gray = self._to_gray(frame)
        tpl_gray = self._to_gray(tpl)
        h, w = tpl_gray.shape[:2]
        res = cv2.matchTemplate(frame_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val >= th:
            cx = max_loc[0] + w // 2
            cy = max_loc[1] + h // 2
            return True, float(max_val), (cx, cy)
        return False, float(max_val), None

    def match_all(self, frame: np.ndarray, template_name: str,
                  threshold: Optional[float] = None
                  ) -> List[Tuple[float, int, int]]:
        """返回所有命中点 [(相似度, cx, cy)]，按 x 从左到右排序。"""
        tpl = self.templates.get(template_name)
        if tpl is None or frame is None or frame.size == 0:
            return []
        th = threshold or self.threshold
        frame_gray = self._to_gray(frame)
        tpl_gray = self._to_gray(tpl)
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
