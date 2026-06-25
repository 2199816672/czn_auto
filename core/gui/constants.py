#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GUI 全局常量：路径、模板 profile、各类下拉显示映射。"""
import sys
from pathlib import Path

# 打包成 exe(冻结)后资源/配置位于 exe 同目录；开发态为项目根目录(core/gui 的上两级)
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parents[2]

CONFIG_PATH = BASE_DIR / "config.json"
LOGS_DIR = BASE_DIR / "logs"
DEBUG_DIR = BASE_DIR / "debug"
PIXEL_DEBUGGER_PATH = BASE_DIR / "templates" / "templates_colors" / "pixel_debugger.json"

# 应用图标：打包(冻结)后随 datas 解压到 _MEIPASS 根；开发态在 packaging/ 下
if getattr(sys, "frozen", False):
    ICON_PATH = Path(getattr(sys, "_MEIPASS", BASE_DIR)) / "app_icon.ico"
else:
    ICON_PATH = BASE_DIR / "packaging" / "app_icon.ico"

WINDOW_TITLE = "CZN Zero Farm v2.2 - 零式系统自动刷取"

PROFILES = ["templates_cn", "templates_global"]

# 服务器 <-> profile
SERVER_TO_PROFILE = {"国服": "templates_cn", "国际服": "templates_global"}
PROFILE_TO_SERVER = {v: k for k, v in SERVER_TO_PROFILE.items()}

# 运行模式
MISSION_DISPLAY = {"zero_system": "零式系统", "season_reroll": "赛季图初始刷取"}
MODE_DISPLAY = {"pc": "PC端/云游戏", "emulator": "模拟器"}
INPUT_BACKEND_DISPLAY = {
    "sendinput": "SendInput (前台)",
    "sendmessage": "SendMessage (后台)",
    "postmessage": "PostMessage (后台推荐)",
    "adb": "ADB (安卓设备)",
}

# 房间路线优先级显示名
ROOM_NAMES = {
    "room_event": "事件",
    "room_rest": "篝火",
    "room_battle": "战斗",
    "room_elite": "精英",
}
DEFAULT_ROOM_PRIORITY = ["room_event", "room_rest", "room_battle", "room_elite"]

# 点击坐标中文描述
CLICK_DESCS = {
    "main_menu_zero_entry": "零式系统入口",
    "codex_first": "选择法典",
    "difficulty_confirm": "难度确认",
    "enter_confirm": "确认进入",
    "team_enter": "配队进入",
    "buff_first": "Buff 首选",
    "map_node_default": "地图默认节点",
    "end_turn": "结束回合",
    "card_play_area": "出牌区域",
    "enemy_target_area": "敌方目标区域",
    "reward_confirm": "奖励确认",
    "result_next": "结算下一步",
    "event_choice_first": "事件默认选项",
    "rest_heal": "休息/治疗",
    "shop_skip": "商店跳过",
    "run_exit_confirm": "退出确认",
    "extraction_confirm": "提取确认",
    "next_floor": "下一层",
    "retreat_btn": "撤退按钮",
    "buff_first_region": "Buff 选择区域",
    "event_first_region": "事件默认选项区域",
}

# 点击坐标提示
CLICK_TIPS = {
    "main_menu_zero_entry": "主界面零式系统按钮，推荐约 (960, 850)",
    "codex_first": "选择法典，推荐约 (400, 500)",
    "enter_confirm": "确认按钮，推荐约 (960, 800)",
    "map_node_default": "地图默认节点，推荐约 (1100, 500)",
    "end_turn": "战斗结束回合按钮，推荐约 (1700, 950)",
    "buff_first_region": "Buff 选择区域 [x, y, 宽, 高]，推荐约 [300, 300, 400, 200]",
    "event_first_region": "事件默认选项区域 [x, y, 宽, 高]，推荐约 [300, 500, 600, 100]",
}

# 延时字段
TIMING_FIELDS = ["screenshot_interval", "post_click_wait", "state_check_retries"]
TIMING_LABELS = {
    "screenshot_interval": "截图间隔 (秒)",
    "post_click_wait": "点击后等待 (秒)",
    "state_check_retries": "状态检查重试",
}
TIMING_TIPS = {
    "screenshot_interval": "每次截图之间的等待，越小检测越快但 CPU 越高，推荐 0.3~1.0",
    "post_click_wait": "点击后等待响应，网络延迟高可调大，推荐 0.3~1.0",
    "state_check_retries": "状态检测失败重试次数，超过则跳过，推荐 3~5",
}

# 战斗字段
COMBAT_FIELDS = ["max_turns_per_battle", "card_play_delay", "target_delay", "end_turn_delay"]
COMBAT_LABELS = {
    "max_turns_per_battle": "每局最大回合",
    "card_play_delay": "出牌延时 (秒)",
    "target_delay": "选目标延时 (秒)",
    "end_turn_delay": "结束回合延时 (秒)",
}
COMBAT_TIPS = {
    "max_turns_per_battle": "超过回合数则结束战斗，防止死循环，推荐 5~30",
    "card_play_delay": "每张牌等待时间，太快游戏可能不响应，推荐 0.3~0.8",
    "target_delay": "选择敌方目标等待时间，推荐 0.2~0.5",
    "end_turn_delay": "回合结束后等待下一回合，推荐 0.5~1.5",
}

# 统计项 (key -> 显示名)
STAT_ITEMS = [
    ("runs", "局"),
    ("battles", "战"),
    ("events", "事件"),
]
