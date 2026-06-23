#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCR 门面（facade）。

``OcrReader`` 自身不实现识别算法，按 ``backend`` 经 ``create_backend`` 选择
``core/ocr`` 下的后端，对外提供稳定的 ``scan`` / ``find_text`` / ``set_lang`` API，
向后兼容历史 ``ocr.OcrReader`` 的所有调用方。
"""
import logging
from typing import List, Optional, Tuple

import numpy as np

from .base import TextBox
from . import create_backend

logger = logging.getLogger(__name__)


class OcrReader:
    def __init__(self, lang: str = "zh-cn", backend: str = "windows"):
        self._lang = lang
        self._backend_name = backend
        self._impl = create_backend(backend, lang)

    def scan(self, frame: np.ndarray, region: Optional[list] = None) -> List[TextBox]:
        return self._impl.scan(frame, region)

    def find_text(self, frame: np.ndarray, keyword: str,
                  region: Optional[list] = None,
                  consecutive: bool = False) -> Optional[Tuple[int, int]]:
        return self._impl.find_text(frame, keyword, region, consecutive)

    def set_lang(self, lang: str):
        self._lang = lang
        self._impl.set_lang(lang)
