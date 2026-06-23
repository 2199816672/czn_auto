#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCR 后端抽象基类。

子类只需实现 ``scan()``（识别帧内文字框）；``find_text()`` 为各后端共享的关键词
查找逻辑（精确匹配 + 可选的逐字连续匹配）。``set_lang()`` 默认空实现，按需覆写。
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# scan() 返回的单条文字框：(文本, x, y, w, h)，坐标为整帧像素
TextBox = Tuple[str, int, int, int, int]


class OcrBackend(ABC):
    """OCR 后端抽象基类。"""

    name: str = "base"

    @abstractmethod
    def scan(self, frame: np.ndarray, region: Optional[list] = None) -> List[TextBox]:
        """识别帧（或指定 region）内的文字框列表。"""
        raise NotImplementedError

    def set_lang(self, lang: str) -> None:
        """切换识别语言。无需切换的后端可保持空实现。"""

    def find_text(self, frame: np.ndarray, keyword: str,
                  region: Optional[list] = None,
                  consecutive: bool = False) -> Optional[Tuple[int, int]]:
        """在识别结果里查找关键词，命中返回中心点坐标。

        先做整词包含匹配；当 ``consecutive`` 为真且关键词多字时，再尝试把相邻的
        单字按行/列顺序拼接做连续匹配（应对 OCR 把词拆成单字的情况）。
        """
        texts = self.scan(frame, region)
        for text, bx, by, bw, bh in texts:
            if keyword in text:
                cx = bx + bw // 2
                cy = by + bh // 2
                logger.info(f"OCR 精确匹配「{keyword}」: 「{text}」 at ({cx}, {cy})")
                return (cx, cy)
        if consecutive and len(keyword) > 1:
            chars = list(keyword)
            sorted_words = sorted(texts, key=lambda t: (t[2], t[1]))
            for i in range(len(sorted_words) - len(chars) + 1):
                ok = True
                for j, ch in enumerate(chars):
                    if sorted_words[i + j][0] != ch:
                        ok = False
                        break
                if ok:
                    xs = [sorted_words[i + j][1] for j in range(len(chars))]
                    ys = [sorted_words[i + j][2] for j in range(len(chars))]
                    x_rs = [sorted_words[i + j][3] for j in range(len(chars))]
                    y_rs = [sorted_words[i + j][4] for j in range(len(chars))]
                    min_x = min(xs)
                    max_x = max(xs[j] + x_rs[j] for j in range(len(chars)))
                    min_y = min(ys)
                    max_y = max(ys[j] + y_rs[j] for j in range(len(chars)))
                    cx = (min_x + max_x) // 2
                    cy = (min_y + max_y) // 2
                    logger.info(f"OCR 连续匹配「{keyword}」 at ({cx}, {cy})")
                    return (cx, cy)
        return None
