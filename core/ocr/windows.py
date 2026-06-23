#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 系统 OCR 后端（WinRT Windows.Media.Ocr）。

无需额外安装第三方模型，依赖系统已装的 OCR 语言包。
"""
import logging
from typing import List, Optional

import numpy as np
import cv2

from .base import OcrBackend, TextBox

logger = logging.getLogger(__name__)


class WindowsOcrBackend(OcrBackend):
    name = "windows"

    def __init__(self, lang: str = "zh-cn"):
        import winrt.windows.media.ocr as wocr
        import winrt.windows.globalization as wgl
        import winrt.windows.graphics.imaging as wimg
        import winrt.windows.storage.streams as wss
        self._wocr = wocr
        self._wgl = wgl
        self._wimg = wimg
        self._wss = wss
        self._lang = lang
        self._engine = None
        self._init_engine()

    def _init_engine(self):
        lang = self._wgl.Language(self._lang)
        self._engine = self._wocr.OcrEngine.try_create_from_language(lang)
        if self._engine:
            logger.info(f"Windows OCR 已初始化: {self._lang}")
        else:
            logger.warning(f"Windows OCR 语言 {self._lang} 不受支持，用 zh-cn 兜底")
            self._engine = self._wocr.OcrEngine.try_create_from_language(
                self._wgl.Language("zh-cn"))

    def _frame_to_bitmap(self, frame: np.ndarray):
        ret, buf = cv2.imencode(".png", frame)
        data = buf.tobytes()
        stream = self._wss.InMemoryRandomAccessStream()
        stream.write_async(data).get()
        stream.seek(0)
        decoder = self._wimg.BitmapDecoder.create_async(stream).get()
        return decoder.get_software_bitmap_async().get()

    def scan(self, frame: np.ndarray, region: Optional[list] = None) -> List[TextBox]:
        if self._engine is None:
            return []
        if region:
            x, y, w, h = region
            frame = frame[y:y + h, x:x + w]
        else:
            x, y = 0, 0
        try:
            bitmap = self._frame_to_bitmap(frame)
            result = self._engine.recognize_async(bitmap).get()
            texts = []
            for line in result.lines:
                text = line.text.strip()
                if not text:
                    continue
                for word in line.words:
                    wt = word.text.strip()
                    if not wt:
                        continue
                    bx = int(word.bounding_rect.x) + x
                    by = int(word.bounding_rect.y) + y
                    bw = int(word.bounding_rect.width)
                    bh = int(word.bounding_rect.height)
                    texts.append((wt, bx, by, bw, bh))
            return texts
        except Exception as e:
            logger.error(f"Windows OCR 识别失败: {e}")
            return []

    def set_lang(self, lang: str):
        if lang != self._lang:
            self._lang = lang
            self._init_engine()
