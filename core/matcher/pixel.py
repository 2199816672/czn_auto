#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""像素点判断。

负责单一职责：加载 ``templates_colors/`` 里的像素规则，并对帧做相对坐标多点
RGB 校验。规则不写进 ``config.json``，坐标用相对值天然适配各分辨率。
"""
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from .states import GameState

logger = logging.getLogger(__name__)

# 每个通道允许上下浮动的固定容差（RGB 各 ±DEFAULT_PIXEL_TOL）
DEFAULT_PIXEL_TOL = 10

# 项目根目录：core/matcher/pixel.py -> parents[2]
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_pixel_checks(profile: Optional[str] = None,
                      base_dir: Optional[Path] = None) -> List[dict]:
    """从 templates_colors/ 加载像素点判断规则（原始 dict 列表）。

    优先读取 templates_colors/<profile>.json（按 template_profile 区分国服/国际服），
    缺失时回退 templates_colors/pixel_checks.json。文件内容可为规则数组，
    或含 "pixel_checks" 键的对象。读取失败/不存在均返回空列表。
    """
    base = Path(base_dir) if base_dir else _PROJECT_ROOT
    color_dir = base / "templates_colors"
    candidates: List[Path] = []
    if profile:
        candidates.append(color_dir / f"{profile}.json")
    candidates.append(color_dir / "pixel_checks.json")
    for f in candidates:
        try:
            if f.exists():
                with open(f, encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    data = data.get("pixel_checks", [])
                logger.info(f"Loaded pixel checks from templates_colors/{f.name}")
                return data or []
        except (OSError, ValueError) as e:
            logger.warning(f"读取像素规则 {f} 失败: {e}")
    return []


@dataclass
class PixelPoint:
    """单个像素采样点：相对坐标 + 目标 RGB + 容差。"""
    rx: float
    ry: float
    rgb: List[int]
    tol: int = DEFAULT_PIXEL_TOL


@dataclass
class PixelRule:
    """一条像素判断规则。``points`` 多点按 ``mode`` 做 all/any 组合。"""
    state: GameState
    name: str
    mode: str  # "all" | "any"
    points: List[PixelPoint]
    click: Optional[list] = None    # [rx, ry] 相对坐标，可选
    before: Optional[str] = None    # 插到某模板检查之前，可选


class PixelChecker:
    """解析像素规则并对帧做多点 RGB 校验。"""

    def __init__(self, rules: Optional[List[dict]] = None):
        self.rules: List[PixelRule] = self._parse(rules or [])

    @property
    def enabled(self) -> bool:
        return bool(self.rules)

    @staticmethod
    def _parse(rules: List[dict]) -> List[PixelRule]:
        """校验并规整像素规则。无效规则跳过并告警。"""
        state_by_value = {gs.value: gs for gs in GameState}
        parsed: List[PixelRule] = []
        for i, rule in enumerate(rules):
            try:
                state_val = rule.get("state")
                state = state_by_value.get(state_val)
                if state is None:
                    logger.warning(f"pixel_checks[{i}] 未知 state='{state_val}'，已跳过")
                    continue
                points = [
                    PixelPoint(
                        rx=float(p["rx"]),
                        ry=float(p["ry"]),
                        rgb=[int(c) for c in p["rgb"]],
                        tol=int(p.get("tol", DEFAULT_PIXEL_TOL)),
                    )
                    for p in (rule.get("points") or [])
                ]
                if not points:
                    logger.warning(f"pixel_checks[{i}] 没有 points，已跳过")
                    continue
                parsed.append(PixelRule(
                    state=state,
                    name=rule.get("name") or f"pixel:{state_val}",
                    mode="any" if str(rule.get("mode", "all")).lower() == "any" else "all",
                    points=points,
                    click=rule.get("click"),
                    before=rule.get("before"),
                ))
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"pixel_checks[{i}] 解析失败({e})，已跳过")
        if parsed:
            logger.info(f"Loaded {len(parsed)} pixel check rule(s)")
        return parsed

    @staticmethod
    def match(frame: np.ndarray, rule: PixelRule
              ) -> Tuple[bool, Optional[Tuple[int, int]]]:
        """对单条像素规则做多点校验。命中返回 (True, 点击坐标[frame坐标])。"""
        if frame is None or frame.size == 0:
            return False, None
        fh, fw = frame.shape[:2]
        first_pt: Optional[Tuple[int, int]] = None
        results: List[bool] = []
        for p in rule.points:
            px = int(p.rx * fw)
            py = int(p.ry * fh)
            if first_pt is None:
                first_pt = (px, py)
            if not (0 <= px < fw and 0 <= py < fh):
                results.append(False)
                continue
            px_val = frame[py, px]
            # OpenCV 为 BGR；配置里 rgb 为 RGB
            b, g, r = int(px_val[0]), int(px_val[1]), int(px_val[2])
            tr, tg, tb = p.rgb
            tol = p.tol
            ok = (abs(r - tr) <= tol and abs(g - tg) <= tol and abs(b - tb) <= tol)
            results.append(ok)
        hit = all(results) if rule.mode == "all" else any(results)
        if not hit:
            return False, None
        if rule.click:
            click_pt = (int(float(rule.click[0]) * fw), int(float(rule.click[1]) * fh))
        else:
            click_pt = first_pt
        return True, click_pt
