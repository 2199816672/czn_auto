#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""状态检测的有序规则表。

把「检测哪些模板、按什么优先级、用什么阈值」这一份数据从 ``StateDetector``
的控制逻辑里独立出来。列表越靠前优先级越高，第一个命中即返回。
新增画面识别时在 ``STATE_CHECKS`` 合适位置插入 (模板名, GameState)。
"""
from typing import List, Tuple

from .states import GameState

# 模板匹配默认阈值（与 TemplateMatcher.DEFAULT_THRESHOLD 一致）
DEFAULT_THRESHOLD = 0.8

# 特定模板的自定义阈值（默认 0.8）
TEMPLATE_THRESHOLDS: dict[str, float] = {
    "wrong_page": 0.98,
    "codex_btn3": 0.95,
}

# 有序模板检查：靠前优先级更高
STATE_CHECKS: List[Tuple[str, GameState]] = [
    ("retreat", GameState.RETREAT),
    ("combat_screen", GameState.COMBAT),
    ("combat_victory", GameState.COMBAT_VICTORY),
    ("codex_obtain", GameState.CODEX_OBTAIN),
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
    ("event_fallback2", GameState.EVENT_SCREEN),
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
    ("team_enter2", GameState.TEAM_ENTER),
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
    ("codex_confirm", GameState.CODEX_CONFIRM),
    ("zero_system_entry", GameState.ZERO_SYSTEM_ENTRY),
    ("main_menu", GameState.MAIN_MENU),
    ("chaos_center", GameState.CHAOS_CENTER),
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
    ("retreat_btn", GameState.RETREAT),  # 脱逃按钮，优先级低于confirm/dream
    ("buff_select", GameState.BUFF_SELECT),
    ("unexpected_room", GameState.UNEXPECTED_ROOM),
    ("bug_close", GameState.BUG_CLOSE),
    ("sparkle_event", GameState.SPARKLE_EVENT),
    ("close_mistouch", GameState.CLOSE_MISTOUCH),
    ("card_duplicate", GameState.CARD_DUPLICATE),
]
