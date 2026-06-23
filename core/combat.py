#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""战斗模块（自动出牌逻辑）。

``CombatModule`` 单一职责：在战斗回合内用轮廓分析识别手牌并依次出牌、结束回合。
坐标/时序均来自传入的 ``config``，不硬编码。
"""
import time
import logging
from typing import Tuple

import numpy as np
import cv2

logger = logging.getLogger(__name__)


class CombatModule:
    def __init__(self):
        self.turn_count = 0
        self.battle_count = 0

    def reset_battle(self):
        self.turn_count = 0
        self.battle_count += 1
        logger.info(f"Battle #{self.battle_count} ended")

    def execute_turn(self, frame: np.ndarray, res: Tuple[int, int], sim, config) -> bool:
        self.turn_count += 1
        max_turns = config.combat.get("max_turns_per_battle", 50)
        if self.turn_count > max_turns:
            logger.warning(f"Exceeded {max_turns} turns, forcing end")
            return False

        ch = config.card_hand
        rx, ry, rw, rh = ch["region"]
        card_delay = config.combat.get("card_play_delay", 0.8)
        target_delay = config.combat.get("target_delay", 0.4)
        end_delay = config.combat.get("end_turn_delay", 1.5)

        # Try to detect cards using contour analysis
        hand_roi = frame[ry:ry + rh, rx:rx + rw, :]
        hand_gray = cv2.cvtColor(hand_roi, cv2.COLOR_BGR2GRAY)
        _, hand_thresh = cv2.threshold(hand_gray, 100, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(hand_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        card_centers = []
        for cnt in contours:
            x, y, cw, ch_h = cv2.boundingRect(cnt)
            area = cw * ch_h
            expected_w = rw // 7
            if area > 1500 and cw > expected_w * 0.3 and ch_h > 25:
                card_centers.append((x + rx + cw // 2, y + ry + ch_h // 2))

        if card_centers:
            card_centers.sort(key=lambda p: p[0])
            if ch.get("play_order", "left_to_right") == "right_to_left":
                card_centers.reverse()
        else:
            # Fallback: click evenly spaced positions
            slots = ch.get("num_slots", 7)
            for i in range(slots):
                cx = rx + (rw // (slots + 1)) * (i + 1)
                cy = ry + rh // 2
                card_centers.append((cx, cy))

        # Play each card
        for cx, cy in card_centers:
            sim.click_at(cx, cy, res[0], res[1])
            time.sleep(0.15)

            play_area = config.click_points.get("card_play_area", [960, 600])
            px = int(play_area[0] * res[0] / config.base_res[0])
            py = int(play_area[1] * res[1] / config.base_res[1])
            sim.click_at(px, py, res[0], res[1])
            time.sleep(0.2)

            enemy_pos = config.click_points.get("enemy_target_area", [1400, 300])
            ex = int(enemy_pos[0] * res[0] / config.base_res[0])
            ey = int(enemy_pos[1] * res[1] / config.base_res[1])
            sim.click_at(ex, ey, res[0], res[1])
            time.sleep(target_delay)

            sim.click_at(px, py, res[0], res[1])
            time.sleep(card_delay)

        # End turn
        time.sleep(end_delay)
        et_pos = config.click_points.get("end_turn", [1800, 950])
        etx = int(et_pos[0] * res[0] / config.base_res[0])
        ety = int(et_pos[1] * res[1] / config.base_res[1])
        sim.click_at(etx, ety, res[0], res[1])
        logger.debug(f"Turn {self.turn_count} ended")
        return True
