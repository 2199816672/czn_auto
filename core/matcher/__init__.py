"""模板匹配 + 状态检测包。

按单一职责拆分：

- ``states``   : ``GameState`` 游戏画面状态枚举
- ``template`` : ``TemplateMatcher`` 模板匹配（不感知状态语义）
- ``pixel``    : ``load_pixel_checks`` 加载像素规则 + ``PixelChecker`` 多点 RGB 校验
- ``checks``   : ``STATE_CHECKS`` 有序检测优先级表 + 阈值数据
- ``detector`` : ``StateDetector`` 把模板/像素按优先级编排成状态识别

对外保持与原 ``detector`` 模块一致的 API：
``GameState`` / ``TemplateMatcher`` / ``StateDetector`` / ``load_pixel_checks``。
"""
from .states import GameState
from .template import TemplateMatcher
from .pixel import PixelChecker, PixelRule, PixelPoint, load_pixel_checks
from .detector import StateDetector

__all__ = [
    "GameState",
    "TemplateMatcher",
    "StateDetector",
    "load_pixel_checks",
    "PixelChecker",
    "PixelRule",
    "PixelPoint",
]
