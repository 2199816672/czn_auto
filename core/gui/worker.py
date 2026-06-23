#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动化状态机线程：把截屏->识别->分发点击的主循环封装为 QThread。

通过 Qt 信号把统计数据回传主线程，UI 不直接被工作线程触碰。
"""
import logging
import threading
import time

from PySide6.QtCore import QThread, Signal

from core.combat import CombatModule
from core.input import InputSimulator
from core.keepawake import KeepAwake
from core.screencap import CaptureMethod, ScreenCapturer
from core.matcher import GameState, StateDetector, TemplateMatcher, load_pixel_checks
from core.window import get_selected_device, resolve_hwnd

from .config_manager import ConfigManager
from .constants import BASE_DIR, DEBUG_DIR
from .tools import _imwrite_unicode


class _SC:
    """战斗模块所需的轻量配置载体（兼容旧 _worker 的鸭子类型）。"""
    base_res = (1920, 1080)
    click_points = {}
    card_hand = {}
    combat = {}
    timing = {}


class AutomationWorker(QThread):
    """运行零式系统 / 赛季图刷取的状态机主循环。"""

    stats_changed = Signal(dict)

    def __init__(self, cfg_mgr: ConfigManager, parent=None):
        super().__init__(parent)
        self.cfg = cfg_mgr.data
        self._stop_evt = threading.Event()
        self._pause_evt = threading.Event()
        # 运行期状态标志
        self._prev_state = None
        self._codex_active = False
        self._buff_active = False
        self._buff_done = False
        self._buff_cooldown = 0.0
        self._retreat_cooldown = 0.0
        self._retreat_toggle = 0

    # ---- 外部控制 ----
    def request_stop(self):
        self._stop_evt.set()

    def set_paused(self, paused: bool):
        if paused:
            self._pause_evt.set()
        else:
            self._pause_evt.clear()

    @property
    def is_paused(self) -> bool:
        return self._pause_evt.is_set()

    # ---- 主循环 ----
    def run(self):
        cfg = self.cfg
        g = cfg["game"]
        sc = _SC()
        sc.base_res = tuple(g["resolution"])
        sc.click_points = cfg["click_points"]
        sc.card_hand = cfg["card_hand"]
        sc.combat = cfg["combat"]
        sc.timing = cfg["timing"]

        tdir = BASE_DIR / "templates" / cfg.get("template_profile", "templates_cn")
        capturer = ScreenCapturer(method=g.get("capture_method", CaptureMethod.DEFAULT.value))
        serial = get_selected_device()
        if serial:
            # ADB 设备：用 serial 绑定截屏/点击，无 Win32 句柄
            capturer.set_device(serial)
            logging.info(f"锁定 ADB 设备: {serial} 捕获方式={capturer.method}")
        else:
            hwnd = resolve_hwnd()
            if hwnd:
                capturer.set_window(hwnd)
                logging.info(f"锁定游戏窗口: 句柄={hwnd} 捕获方式={capturer.method}")
            else:
                logging.warning("未选择目标窗口，请在首页选择窗口后再运行")
        matcher = TemplateMatcher(tdir)
        detector = StateDetector(matcher, load_pixel_checks(cfg.get("template_profile")))
        sim = InputSimulator(backend=g.get("input_backend", "postmessage"))
        sim.keep_mouse = cfg.get("debug", {}).get("keep_mouse", False)

        # 坐标变换：点击自动从游戏坐标转屏幕坐标
        _orig_click_at = sim.click_at

        def _click_at_wrapper(x, y, sw=1920, sh=1080):
            sx, sy = capturer.game_to_screen(x, y)
            _orig_click_at(sx, sy, sw, sh)

        sim.click_at = _click_at_wrapper

        mission = g.get("mission", "zero_system")
        combat_mod = CombatModule()
        stats = {"runs": 0, "battles": 0, "elites": 0, "floors": 0, "events": 0}
        unknown_cnt = 0
        offsets = cfg.get("click_offsets", {})
        res = sc.base_res

        ocr_state = _OcrState()

        self._codex_active = False
        self._buff_active = False
        self._buff_done = False
        self._buff_cooldown = 0.0

        def _click(tpl_name=None, default_pos=None):
            pos = default_pos or detector.last_pos
            if tpl_name and tpl_name in offsets:
                pos = (pos[0] + offsets[tpl_name][0], pos[1] + offsets[tpl_name][1])
            sim.click_at(pos[0], pos[1], res[0], res[1])

        retreat_on_first = g.get("retreat_on_first_floor", False)
        skip_templates = set()
        if not retreat_on_first:
            skip_templates.add("retreat")

        logging.info(f"=== 开始运行 [配置: {tdir.name}] ===")

        keep_awake = KeepAwake()
        if g.get("prevent_lock", True):
            keep_awake.enable()

        while not self._stop_evt.is_set():
            if self._pause_evt.is_set():
                time.sleep(0.3)
                continue
            try:
                frame = capturer.capture_game_area()
                res = capturer.get_resolution()
                state = detector.detect(frame, skip_templates)
                if state != self._prev_state:
                    prev_name = self._prev_state.value if self._prev_state else "无"
                    logging.info(f"状态 {prev_name} -> {state.value}")
                    self._prev_state = state

                sr_delay = 0.05
                if mission == "season_reroll":
                    self._handle_season_reroll(
                        cfg, frame, state, detector, sim, res, sr_delay, ocr_state,
                    )
                    continue

                if state == GameState.UNKNOWN:
                    unknown_cnt += 1
                    if unknown_cnt >= 50:
                        logging.warning(f"{unknown_cnt}次未知状态")
                        unknown_cnt = 0
                    time.sleep(sr_delay)
                    continue
                unknown_cnt = 0
                t = sc.timing

                settlement_tpls = [
                    "settlement_click", "dismantle_confirm", "settlement_confirm",
                    "dismantle_equip", "node_settlement", "next_step",
                ]

                # Buff 模式只匹配 event_option2 状态
                if self._buff_active:
                    found, conf, pos = detector.matcher.match(frame, "event_option2", 0.8)
                    if found:
                        logging.info(f"Buff event_option2 点击2次 ({conf:.2f})")
                        for _ in range(2):
                            sim.click_at(588, pos[1], res[0], res[1])
                            time.sleep(0.2)
                        self._buff_active = False
                        self._buff_done = True
                        self._buff_cooldown = time.time() + 5
                    elif state != GameState.BUFF_SELECT:
                        self._buff_active = False
                    else:
                        time.sleep(0.5)
                    continue

                # 法典合成模式
                if self._codex_active or state == GameState.CODEX_SYNTH:
                    self._codex_active = True
                    clicked = False
                    if state == GameState.CODEX_SYNTH and detector.last_template == "codex_synth":
                        logging.info("合成点击codex_synth")
                        sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                        clicked = True
                    if not clicked:
                        for tpl in ("codex_btn0", "codex_btn1", "codex_btn2", "codex_btn3", "codex_btn4"):
                            if tpl == "codex_btn1" and not cfg.get("codex_use_btn1", True):
                                continue
                            found, conf, pos = detector.matcher.match(frame, tpl, 0.8)
                            if found:
                                if tpl in ("codex_btn3", "codex_btn4"):
                                    logging.info(f"合成 {tpl} ({conf:.2f}) 往上300像素点击")
                                    sim.click_at(pos[0], pos[1] - 300, res[0], res[1])
                                    time.sleep(0.2)
                                else:
                                    logging.info(f"合成 {tpl} ({conf:.2f})")
                                sim.click_at(pos[0], pos[1], res[0], res[1])
                                clicked = True
                                break
                    if not clicked:
                        for tpl in ("settle_done_1", "settle_done_2"):
                            if detector.matcher.match(frame, tpl, 0.98)[0]:
                                logging.info("法典合成完成")
                                self._codex_active = False
                                clicked = True
                                break
                    time.sleep(t.get("post_click_wait", 1.0) if clicked else 0.5)
                    continue

                self._dispatch_state(
                    state, cfg, frame, detector, sim, combat_mod, sc, res, t,
                    stats, offsets, settlement_tpls, _click, sr_delay,
                )
                time.sleep(t.get("post_click_wait", 1.0))
            except Exception as e:
                logging.error(f"运行错误: {e}")
                time.sleep(2.0)

        keep_awake.disable()
        logging.info("=== 运行结束 ===")

    # ---- 状态分发（零式系统）----
    def _dispatch_state(self, state, cfg, frame, detector, sim, combat_mod, sc, res, t,
                        stats, offsets, settlement_tpls, _click, sr_delay):
        GS = GameState

        def click_last(dx=0, dy=0):
            sim.click_at(detector.last_pos[0] + dx, detector.last_pos[1] + dy, res[0], res[1])

        if state == GS.MAIN_MENU:
            self._buff_done = False
            self._buff_cooldown = 0.0
            self._retreat_cooldown = 0.0
            logging.info("主界面→零式系统")
            click_last()
        elif state == GS.ZERO_SYSTEM_ENTRY:
            logging.info("零式系统→选法典")
            click_last()
        elif state == GS.CODEX_SELECT:
            logging.info("选法典→确认进入")
            click_last()
            stats["runs"] += 1
            self.stats_changed.emit(stats.copy())
        elif state == GS.TEAM_ENTER:
            logging.info("配队→进入")
            click_last()
        elif state == GS.BUFF_SELECT:
            if self._buff_done or time.time() < self._buff_cooldown:
                time.sleep(t["screenshot_interval"])
                return
            self._buff_done = True
            self._buff_cooldown = time.time() + 300
            logging.info("Buff模式 首次选择")
            if "buff_first_region" in cfg.get("click_points", {}):
                rx, ry, rw, rh = cfg["click_points"]["buff_first_region"]
                sim.click_at(rx + rw // 2, ry + rh // 2, res[0], res[1])
            else:
                click_last()
            self._buff_active = True
        elif state == GS.UNEXPECTED_ROOM:
            found, conf, pos = detector.matcher.match(frame, "unex_leave", 0.8)
            if found:
                logging.info(f"意外房间 离开 ({conf:.2f})")
                for _ in range(2):
                    sim.click_at(pos[0], pos[1], res[0], res[1])
                    time.sleep(0.2)
            else:
                time.sleep(0.5)
        elif state == GS.ROOM_SELECT:
            room_order = cfg.get("room_priority", ["room_event", "room_rest", "room_battle", "room_elite"])
            rooms = [(r, i) for i, r in enumerate(room_order)] + [("boss_node", 99), ("room_fallback", 100)]
            clicked = False
            for name, _ in rooms:
                found, conf, pos = detector.matcher.match(frame, name, threshold=0.8)
                if found:
                    logging.info(f"{name} ({conf:.2f})")
                    if name == "room_fallback":
                        sim.click_at(pos[0] + 300, pos[1], res[0], res[1])
                    else:
                        sim.click_at(pos[0], pos[1], res[0], res[1])
                    if name in ("room_rest", "room_battle", "room_elite", "boss_node", "room_fallback"):
                        time.sleep(1.0)
                    clicked = True
                    break
            if not clicked:
                logging.warning("所有房间没匹配到，点击默认节点")
                click_last()
        elif state == GS.BOSS_NODE:
            logging.info("Boss节点 左偏移150")
            for _ in range(2):
                click_last(-150, 50)
                time.sleep(0.2)
        elif state == GS.MAP_SCREEN:
            logging.info("地图点击默认节点")
            click_last()
        elif state == GS.COMBAT:
            time.sleep(2)
        elif state == GS.COMBAT_VICTORY:
            logging.info("战斗胜利")
            stats["battles"] += 1
            combat_mod.reset_battle()
            self.stats_changed.emit(stats.copy())
            time.sleep(t["post_click_wait"])
            click_last()
        elif state == GS.CARD_REWARD:
            logging.info("选卡奖励")
            _click("card_reward")
        elif state == GS.NEUTRAL_CARD_SKIP:
            logging.info("中立卡片跳过")
            _click("neutral_card_skip")
        elif state == GS.SKIP_CONFIRM:
            logging.info("跳过确认")
            _click("skip_confirm")
        elif state == GS.RESULT_NEXT:
            self._handle_result_next(frame, detector, sim, res, settlement_tpls)
        elif state == GS.FATE_REWARD:
            logging.info("获取命运→确定")
            click_last()
        elif state == GS.REST_SCREEN:
            logging.info("休息")
            click_last()
        elif state == GS.EVENT_SCREEN:
            stats["events"] += 1
            if detector.last_template in ("event_fallback", "event_fallback2"):
                logging.info("事件保底")
                for _ in range(2):
                    click_last(0, -80)
                    time.sleep(0.2)
            else:
                y = detector.last_pos[1]
                for x in (1350, 990, 600):
                    for _ in range(2):
                        sim.click_at(x, y, res[0], res[1])
                        time.sleep(0.2)
        elif state == GS.DEATH_SCREEN:
            logging.info("死亡")
            combat_mod.reset_battle()
            click_last()
        elif state == GS.EXTRACTION:
            logging.info("提取奖励")
            click_last()
        elif state == GS.RETREAT:
            if time.time() < self._retreat_cooldown:
                time.sleep(0.5)
                return
            time.sleep(1.0)
            if detector.last_template in ("retreat", "pixel:retreat", "pixel:retreat_btn"):
                cx, cy = detector.last_pos
                if self._retreat_toggle % 2 == 0:
                    logging.info("撤退 右边 右455")
                    sim.click_at(cx + 455, cy, res[0], res[1])
                else:
                    logging.info("撤退 右上角 右596上915")
                    sim.click_at(cx + 596, cy - 915, res[0], res[1])
                self._retreat_toggle += 1
                self._retreat_cooldown = time.time() + 5.0
                time.sleep(sr_delay)
            else:
                logging.info("设置→脱离")
                click_last()
        elif state == GS.REMOVE_CARD_EVENT:
            logging.info("移除卡牌")
            _click("remove_card_event")
        elif state == GS.CONFIRM_OPTION:
            logging.info("确认弹窗")
            _click("confirm_option")
        elif state == GS.CHAOS_CENTER:
            logging.info("前往混沌中心")
            _click("chaos_center")
        elif state == GS.CONFIRM_PURPLE:
            logging.info("紫色确认")
            click_last()
        elif state == GS.CONFIRM_ORANGE:
            logging.info("橙色确认")
            click_last()
        elif state == GS.GAME_SETTLED:
            logging.info("游戏完成弹窗")
            click_last()
        elif state == GS.CONFIRM_EXTRACT:
            logging.info("提炼")
            click_last()
        elif state == GS.BOSS_ROOM:
            logging.info("Boss房")
            click_last()
        elif state == GS.CONTINUE_ORANGE:
            logging.info("橙色继续")
            click_last()
        elif state == GS.EVENT_SKIP:
            logging.info("跳过事件")
            click_last()
        elif state == GS.COPY_CARD_CHOICE:
            logging.info("复制卡牌选择")
            for rx in (0.25, 0.5, 0.75):
                sim.click_at(int(rx * res[0]), int(0.5 * res[1]), res[0], res[1])
                time.sleep(0.2)
        elif state == GS.CLOSE_VIEW:
            logging.info("关闭视图")
            _click("close_view")
        elif state == GS.CONTINUE_FORWARD:
            logging.info("继续前进")
            _click("continue_forward")
        elif state == GS.CONFIRM_ACQUIRE:
            logging.info("确认获得")
            if detector.last_template == "choose_fate":
                bx, by = detector.last_pos
                for dx, dy in [(-500, -250), (0, -250), (500, -250), (750, 0)]:
                    sim.click_at(bx + dx, by + dy, res[0], res[1])
                    time.sleep(0.2)
            else:
                _click("confirm_acquire")
                time.sleep(0.5)
                tpl = detector.last_template
                if tpl and tpl in detector.matcher.templates:
                    h, w = detector.matcher.templates[tpl].shape[:2]
                    left_x = detector.last_pos[0] - w // 2
                    sim.click_at(left_x, detector.last_pos[1], res[0], res[1])
        elif state == GS.CONFIRM:
            logging.info("确认")
            click_last()
        elif state == GS.BUG_CLOSE:
            logging.info("国服bug关闭")
            click_last()
        elif state == GS.CLOSE_MISTOUCH:
            logging.info("关闭误触界面")
            click_last(0, -300)
        elif state == GS.SPARKLE_EVENT:
            logging.info("闪光事件")
            bx, by = detector.last_pos
            for dx, dy in [(-1205, -200), (-1025, -700), (0, 0)]:
                sim.click_at(bx + dx, by + dy, res[0], res[1])
                time.sleep(0.2)
        elif state == GS.CODEX_COMPLETE:
            logging.info("完成法典")
            click_last(0, 210)
        elif state == GS.CODEX_OBTAIN:
            logging.info("获得法典")
            cx, cy = detector.last_pos
            sim.click_at(cx, cy + 430, res[0], res[1])
            time.sleep(sr_delay)
            sim.click_at(cx + 690, cy + 870, res[0], res[1])
        elif state == GS.CODEX_CONFIRM:
            logging.info("确认图鉴")
            click_last()
        elif state == GS.SKIP_LEFTMOST:
            matches = detector.matcher.match_all(frame, "skip_leftmost", threshold=0.8)
            if matches:
                _, cx, cy = matches[0]
                detector.last_pos = (cx, cy)
                logging.info(f"跳过最左 ({cx},{cy})")
                _click("skip_leftmost")
        elif state == GS.CARD_REWARD_SKIP:
            logging.info("卡牌跳过")
            _click("card_reward_skip")
        elif state == GS.COMBAT_WITHOUT_AUTO:
            logging.info("战斗未开自动 → 点击开启自动")
            sim.click_at(int(0.8792 * res[0]), int(0.0519 * res[1]), res[0], res[1])
        elif state == GS.WRONG_PAGE:
            logging.info("误入其他页面")
            _click("wrong_page")
        elif state == GS.DELETE_SAVE:
            logging.info("删除存档")
            click_last()
        elif state == GS.DREAM_CONFIRM:
            logging.info("梦境确认")
            click_last()
        elif state == GS.INSPIRATION_CARD:
            logging.info("灵感卡")
            _click("inspiration_card")
        elif state == GS.CARD_DUPLICATE:
            logging.info("复制卡牌")
            _click("card_duplicate")
        elif state == GS.CARD_CONVERT:
            logging.info("卡牌转换")
            _click("card_convert")
        elif state == GS.EVENT_DICE:
            logging.info("事件骰子")
            click_last()
        elif state == GS.DICE_NEXT:
            logging.info("骰子下一步")
            click_last()
        elif state == GS.SELECT_CHARACTER:
            logging.info("选择角色")
            bx, by = detector.last_pos
            for px, py in [(bx - 500, by - 250), (bx, by - 250), (bx + 500, by - 250), (bx + 750, by)]:
                sim.click_at(px, py, res[0], res[1])
                time.sleep(0.2)
        else:
            time.sleep(t["screenshot_interval"])

    def _handle_result_next(self, frame, detector, sim, res, settlement_tpls):
        clicked = False
        for tpl in settlement_tpls:
            found, conf, pos = detector.matcher.match(frame, tpl, 0.8)
            if found:
                logging.info(f"{tpl} ({conf:.2f})")
                if tpl == "settlement_confirm":  # 取消选择装备
                    sim.click_at(pos[0], pos[1], res[0], res[1])
                    time.sleep(0.2)
                    sim.click_at(pos[0] - 420, pos[1], res[0], res[1])
                else:
                    sim.click_at(pos[0], pos[1], res[0], res[1])
                clicked = True
                break
        if not clicked:
            for tpl in ("settle_done_1", "settle_done_2"):
                if detector.matcher.exists(tpl) and detector.matcher.match(frame, tpl, 0.8)[0]:
                    clicked = True
                    break
        if not clicked:
            found, conf, pos = detector.matcher.match(frame, "codex_btn3", 0.95)
            if found:
                logging.info(f"合成 codex_btn3 ({conf:.2f}) 往上300像素点击")
                sim.click_at(pos[0], pos[1] - 300, res[0], res[1])
                time.sleep(0.2)
                sim.click_at(pos[0], pos[1], res[0], res[1])
                clicked = True
        if not clicked:
            time.sleep(0.5)

    # ---- 赛季图初始刷取 ----
    def _handle_season_reroll(self, cfg, frame, state, detector, sim, res, sr_delay, ocr_state):
        ocr_cfg = cfg.get("ocr", {})
        if ocr_state.ocr is None:
            from core.ocr import OcrReader
            lang = "zh-hk" if cfg.get("template_profile") == "templates_global" else "zh-cn"
            ocr_state.ocr = OcrReader(lang, ocr_cfg.get("backend", "windows"))
        ocr = ocr_state.ocr

        is_global = cfg.get("template_profile") == "templates_global"
        kw_default = "退出2x" if is_global else "退出2选"
        entry_default = ["M"] if is_global else [""]
        exit_default = ["ESC", "退出", "_J"] if is_global else ["ESC", "返回", "关闭"]

        if ocr_state.exiting:
            exit_kws = ocr_cfg.get("exit_keywords", exit_default)
            exit_offsets = ocr_cfg.get("exit_keyword_offsets", [])
            if ocr_state.exit_idx < len(exit_kws):
                kw = exit_kws[ocr_state.exit_idx]
                offset = exit_offsets[ocr_state.exit_idx] if ocr_state.exit_idx < len(exit_offsets) else [0, 0]
                target_state = None
                if ocr_state.exit_idx == 1:
                    target_state = GameState.RETREAT
                elif ocr_state.exit_idx >= 2:
                    target_state = GameState.SKIP_CONFIRM
                if target_state is not None and state == target_state:
                    cx, cy = detector.last_pos[0] + offset[0], detector.last_pos[1] + offset[1]
                    logging.info(f"模板匹配 {kw} ({cx},{cy}) conf={detector.last_conf:.3f}")
                    sim.click_at(cx, cy, res[0], res[1])
                    ocr_state.exit_idx += 1
                else:
                    pos = ocr.find_text(frame, kw, None, consecutive=True)
                    if pos:
                        cx, cy = pos[0] + offset[0], pos[1] + offset[1]
                        logging.info(f"找到 {kw} ({cx},{cy})")
                        sim.click_at(cx, cy, res[0], res[1])
                        ocr_state.exit_idx += 1
                    elif state == GameState.RETREAT:
                        cx, cy = detector.last_pos[0] + offset[0], detector.last_pos[1] + offset[1]
                        logging.info(f"模板已到 {kw} ({cx},{cy})")
                        sim.click_at(cx, cy, res[0], res[1])
                        ocr_state.exit_idx += 1
                    else:
                        logging.info(f"等待 {kw}")
                time.sleep(sr_delay)
            else:
                ocr_state.reset_round()
                logging.info("退出完成准备下一轮")
            return True

        entry_kws = ocr_cfg.get("entry_keywords", entry_default)
        if ocr_state.entry_idx < len(entry_kws):
            kw = entry_kws[ocr_state.entry_idx]
            pos = ocr.find_text(frame, kw, None, consecutive=True)
            if pos:
                logging.info(f"入口找到 {kw} ({ocr_state.entry_idx + 1}/{len(entry_kws)})")
                sim.click_at(pos[0], pos[1], res[0], res[1])
                ocr_state.entry_idx += 1
                time.sleep(5.0)
            else:
                logging.info(f"入口等待 {kw}")
            time.sleep(sr_delay)
            return True

        kw = ocr_cfg.get("keyword", kw_default)
        all_texts = ocr.scan(frame)
        pos = None
        chars = list(kw)
        sorted_w = sorted(all_texts, key=lambda t: (t[2], t[1]))
        # 整词匹配
        for t, bx, by, bw, bh in all_texts:
            if kw in t:
                pos = (bx + bw // 2, by + bh // 2)
                break
        # 逐字符匹配兜底
        if not pos and len(kw) > 1:
            for i in range(len(sorted_w) - len(chars) + 1):
                if all(sorted_w[i + j][0] == ch for j, ch in enumerate(chars)):
                    _, bx, by, bw, bh = sorted_w[i]
                    pos = (bx + bw // 2, by + bh // 2)
                    break
        # OCR 失败截图兜底
        if not pos:
            all_text = "".join(t[0] for t in all_texts)
            if kw in all_text:
                first_ch = kw[0]
                for t, bx, by, bw, bh in all_texts:
                    if first_ch in t:
                        pos = (bx + bw // 2, by + bh // 2)
                        break
                if pos:
                    logging.info(f"找到关键词: {kw} (OCR: {all_text[:120]!r}) 坐标 ({pos[0]},{pos[1]})")
                    sim.click_at(pos[0], pos[1], res[0], res[1])
                    self.request_stop()
                    time.sleep(sr_delay)
                    return True
                else:
                    logging.info(f"OCR原文: {all_text[:120]!r}")
                    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
                    _imwrite_unicode(DEBUG_DIR / "buff_scan_fail.png", frame)
                    logging.info(f"已保存 {DEBUG_DIR / 'buff_scan_fail.png'}")
        if pos:
            logging.info(f"找到目标Buff: {kw}")
            sim.click_at(pos[0], pos[1], res[0], res[1])
            self.request_stop()
        else:
            ocr_state.buff_miss += 1
            if ocr_state.buff_miss >= 2:
                logging.info(f"{ocr_state.buff_miss}次未找到，退出")
                ocr_state.exiting = True
                ocr_state.exit_idx = 0
                ocr_state.buff_miss = 0
            else:
                logging.info(f"未找到目标Buff({ocr_state.buff_miss}次，继续)")
        time.sleep(sr_delay)
        return True


class _OcrState:
    """赛季图刷取的循环状态（取代旧版散落的局部变量）。"""

    def __init__(self):
        self.ocr = None
        self.exiting = False
        self.entry_idx = 0
        self.exit_idx = 0
        self.buff_miss = 0

    def reset_round(self):
        self.exiting = False
        self.entry_idx = 0
        self.exit_idx = 0
        self.buff_miss = 0
