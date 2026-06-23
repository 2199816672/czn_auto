#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PaddleOCR 后端。

依赖第三方 ``paddleocr``；未安装时构造抛出友好错误。识别精度高但首次加载较慢。
"""
import logging
from typing import List, Optional

import numpy as np

from .base import OcrBackend, TextBox

try:
    from paddleocr import PaddleOCR
    _PADDLE_AVAILABLE = True
except ImportError:
    _PADDLE_AVAILABLE = False

logger = logging.getLogger(__name__)


class PaddleOcrBackend(OcrBackend):
    name = "paddle"

    def __init__(self, lang: str = "ch"):
        if not _PADDLE_AVAILABLE:
            raise ImportError("paddleocr 未安装，请执行: pip install paddleocr")
        self._ocr = PaddleOCR(use_angle_cls=False, lang=lang)
        self._lang = lang
        logger.info(f"PaddleOCR 已初始化: {lang}")

    def scan(self, frame: np.ndarray, region: Optional[list] = None) -> List[TextBox]:
        if region:
            x, y, w, h = region
            crop = frame[y:y + h, x:x + w]
        else:
            crop = frame
            x, y = 0, 0
        try:
            result = self._ocr.ocr(crop, cls=False)
            texts = []
            if result and result[0]:
                for line in result[0]:
                    box, (txt, conf) = line
                    pts = np.array(box, dtype=np.int32)
                    bx = int(pts[:, 0].min()) + x
                    by = int(pts[:, 1].min()) + y
                    bw = int(pts[:, 0].max()) - int(pts[:, 0].min())
                    bh = int(pts[:, 1].max()) - int(pts[:, 1].min())
                    t = txt.strip()
                    if t:
                        texts.append((t, bx, by, bw, bh))
            return texts
        except Exception as e:
            logger.error(f"PaddleOCR 识别失败: {e}")
            return []
