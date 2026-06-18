#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# gui.py - 卡厄思梦境自动刷取 GUI (MAA 风格)
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass

import os, sys, json, time, threading, datetime, logging
from pathlib import Path
from tkinter import ttk, scrolledtext, font
import tkinter as tk
from tkinter import messagebox

import cv2

BASE_DIR = Path(__file__).parent


def imwrite_unicode(path, img):
    ret, buf = cv2.imencode(".png", img)
    if ret:
        with open(str(path), "wb") as f:
            f.write(buf.tobytes())
        return True
    return False
sys.path.insert(0, str(BASE_DIR))

from capture import ScreenCapturer
from controller import InputSimulator
from detector import TemplateMatcher, StateDetector, GameState
from combat import CombatModule

CONFIG_PATH = BASE_DIR / "config.json"
LOGS_DIR = BASE_DIR / "logs"

PROFILES = ["templates_cn", "templates_global"]

# MAA k??k
COLOR_BG = "#1c1c1c"
COLOR_SIDEBAR = "#252526"
COLOR_CARD = "#2d2d30"
COLOR_ACCENT = "#326CF3"
COLOR_ACCENT_HOVER = "#4a9eff"
COLOR_TEXT = "#e6e6e6"
COLOR_TEXT_SEC = "#969696"
COLOR_LOG_BG = "#1e1e1e"
COLOR_GREEN = "#4ec9b0"
COLOR_RED = "#f44747"
COLOR_YELLOW = "#f39c12"
COLOR_BORDER = "#3e3e42"


def get_profile_dir(name=None):
    if name:
        return BASE_DIR / name
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    return BASE_DIR / cfg.get("template_profile", "templates_global")


class TextHandler(logging.Handler):
    def __init__(self, widget):
        super().__init__()
        self.widget = widget
        self.widget.tag_configure("INFO", foreground=COLOR_GREEN)
        self.widget.tag_configure("WARNING", foreground=COLOR_YELLOW)
        self.widget.tag_configure("ERROR", foreground=COLOR_RED)
        self.widget.tag_configure("STATS", foreground=COLOR_ACCENT)

    def emit(self, record):
        msg = self.format(record) + "\n"
        tag = "INFO"
        if record.levelno >= logging.ERROR:
            tag = "ERROR"
        elif record.levelno >= logging.WARNING:
            tag = "WARNING"
        if "State:" in msg:
            tag = "STATS"
        self.widget.after(0, lambda: (self.widget.insert(tk.END, msg, tag), self.widget.see(tk.END)))


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._enter)
        widget.bind("<Leave>", self._leave)

    def _enter(self, event):
        if self.tip:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip = tk.Toplevel(self.widget, bg="#fffde7", bd=1, relief="solid")
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg="#fffde7", fg="#333", font=("Microsoft YaHei", 9),
                 wraplength=350, justify="left", padx=8, pady=4).pack()

    def _leave(self, event):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class ConfigDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("")
        self.geometry("720x600")
        self.configure(bg=COLOR_BG)
        self.transient(parent)
        self.grab_set()
        self.entries = {}
        with open(CONFIG_PATH, encoding="utf-8") as f:
            self.cfg = json.load(f)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=(10, 10), side=tk.BOTTOM)
        ttk.Button(btn_frame, text="保存", style="Accent.TButton", command=self.save).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.RIGHT, padx=(5, 0))

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

        cf = ttk.Frame(nb)
        nb.add(cf, text="")
        canvas = tk.Canvas(cf, bg=COLOR_BG, highlightthickness=0)
        sb = ttk.Scrollbar(cf, orient="vertical", command=canvas.yview)
        sf = tk.Frame(canvas, bg=COLOR_BG)
        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        click_tips = {
            "main_menu_zero_entry": "点击主界面零式系统按钮\n推荐 1920x1080 约 (960, 850)",
            "codex_first": "点击选择法典\n推荐 1920x1080 约 (400, 500)",
            "enter_confirm": "点击确认按钮\n推荐 1920x1080 约 (960, 800)",
            "map_node_default": "地图默认节点位置\n推荐 1920x1080 约 (1100, 500)",
            "end_turn": "战斗结束回合按钮\n推荐 1920x1080 约 (1700, 950)",
            "card_play_area": "出牌区域\n推荐 1920x1080 约 (960, 600)",
            "enemy_target_area": "选择敌方目标\n推荐 1920x1080 约 (1200, 400)",
            "reward_confirm": "奖励/获取按钮\n推荐 1920x1080 约 (960, 750)",
            "event_choice_first": "事件默认选项位置\n推荐 1920x1080 约 (960, 600)",
            "rest_heal": "休息/治疗按钮\n推荐 1920x1080 约 (960, 700)",
            "run_exit_confirm": "退出确认按钮\n推荐 1920x1080 约 (960, 650)",
            "extraction_confirm": "提取确认按钮\n推荐 1920x1080 约 (960, 700)",
        }
        region_tips = {
            "buff_first_region": "Buff选择区域\n格式 [x, y, 宽, 高]\n推荐 1920x1080 约 [300, 300, 400, 200]",
            "event_first_region": "事件默认选项区域\n格式 [x, y, 宽, 高]\n推荐 1920x1080 约 [300, 500, 600, 100]",
        }
        descs = {
            "main_menu_zero_entry": "零式系统", "codex_first": "选择法典",
            "enter_confirm": "确认", "map_node_default": "地图默认节点",
            "end_turn": "结束回合", "card_play_area": "", "enemy_target_area": "敌方目标",
            "reward_confirm": "奖励", "event_choice_first": "事件默认选项",
            "rest_heal": "休息/治疗", "run_exit_confirm": "确认退出", "extraction_confirm": "提取确认",
        }
        for i, (key, val) in enumerate(self.cfg.get("click_points", {}).items()):
            if isinstance(val, list) and len(val) == 4:
                desc = region_tips.get(key, key)
                lbl = ttk.Label(sf, text=f"配置: {desc}", width=32, anchor="w")
                lbl.grid(row=i, column=0, sticky="w", padx=5, pady=2)
                if key in region_tips:
                    ToolTip(lbl, region_tips[key])
                f = ttk.Frame(sf)
                f.grid(row=i, column=1, sticky="w")
                ex = tk.StringVar(value=str(val[0]))
                ey = tk.StringVar(value=str(val[1]))
                ew = tk.StringVar(value=str(val[2]))
                eh = tk.StringVar(value=str(val[3]))
                ttk.Entry(f, textvariable=ex, width=5).pack(side=tk.LEFT)
                ttk.Label(f, text=",").pack(side=tk.LEFT)
                ttk.Entry(f, textvariable=ey, width=5).pack(side=tk.LEFT)
                ttk.Label(f, text=",").pack(side=tk.LEFT)
                ttk.Entry(f, textvariable=ew, width=5).pack(side=tk.LEFT)
                ttk.Label(f, text=",").pack(side=tk.LEFT)
                ttk.Entry(f, textvariable=eh, width=5).pack(side=tk.LEFT)
                self.entries[f"c_{key}_x"] = ex; self.entries[f"c_{key}_y"] = ey
                self.entries[f"c_{key}_w"] = ew; self.entries[f"c_{key}_h"] = eh
            else:
                desc = descs.get(key, key)
                lbl = ttk.Label(sf, text=desc, width=28, anchor="w")
                lbl.grid(row=i, column=0, sticky="w", padx=5, pady=2)
                if key in click_tips:
                    ToolTip(lbl, click_tips[key])
                f = ttk.Frame(sf)
                f.grid(row=i, column=1, sticky="w")
                ex = tk.StringVar(value=str(val[0]))
                ey = tk.StringVar(value=str(val[1]))
                ttk.Entry(f, textvariable=ex, width=6).pack(side=tk.LEFT)
                ttk.Label(f, text=",").pack(side=tk.LEFT)
                ttk.Entry(f, textvariable=ey, width=6).pack(side=tk.LEFT)
                self.entries[f"c_{key}_x"] = ex; self.entries[f"c_{key}_y"] = ey

        tf = ttk.Frame(nb); nb.add(tf, text="延时")
        tim = self.cfg.get("timing", {})
        timing_labels = {"screenshot_interval": "截图间隔(秒)", "post_click_wait": "点击后等待", "state_check_retries": "状态检查重试"}
        timing_tips = {
            "screenshot_interval": "每次截图之间的等待时间\n越小检测越快，CPU占用越高\n推荐 0.3~1.0",
            "post_click_wait": "点击后等待响应时间\n网络延迟高可调大\n推荐 0.3~1.0",
            "state_check_retries": "状态检测失败时重试次数\n超过则跳过当前状态\n推荐 3~5",
        }
        for i, k in enumerate(["screenshot_interval", "post_click_wait", "state_check_retries"]):
            lbl = ttk.Label(tf, text=timing_labels.get(k, k), width=25, anchor="w")
            lbl.grid(row=i, column=0, padx=5, pady=2, sticky="w")
            if k in timing_tips:
                ToolTip(lbl, timing_tips[k])
            v = tk.StringVar(value=str(tim.get(k, ""))); ttk.Entry(tf, textvariable=v, width=10).grid(row=i, column=1)
            self.entries[f"t_{k}"] = v

        bf = ttk.Frame(nb); nb.add(bf, text="战斗")
        com = self.cfg.get("combat", {})
        combat_labels = {"max_turns_per_battle": "每局最大回合", "card_play_delay": "出牌延时(秒)", "target_delay": "选目标延时", "end_turn_delay": "结束回合延时(秒)"}
        combat_tips = {
            "max_turns_per_battle": "超过回合数则结束战斗\n防止死循环\n推荐 5~30",
            "card_play_delay": "每张牌的等待时间\n太快游戏可能不响应\n推荐 0.3~0.8",
            "target_delay": "选择敌方目标等待时间\n推荐 0.2~0.5",
            "end_turn_delay": "回合结束后等待下一回合时间\n推荐 0.5~1.5",
        }
        for i, k in enumerate(["max_turns_per_battle", "card_play_delay", "target_delay", "end_turn_delay"]):
            lbl = ttk.Label(bf, text=combat_labels.get(k, k), width=25, anchor="w")
            lbl.grid(row=i, column=0, padx=5, pady=2, sticky="w")
            if k in combat_tips:
                ToolTip(lbl, combat_tips[k])
            v = tk.StringVar(value=str(com.get(k, ""))); ttk.Entry(bf, textvariable=v, width=10).grid(row=i, column=1)
            self.entries[f"b_{k}"] = v

        sf = ttk.Frame(nb); nb.add(sf, text="服务器")
        ttk.Label(sf, text="当前服务器:", width=20, anchor="w").grid(row=0, column=0, padx=5, pady=10, sticky="w")
        self.server_var = tk.StringVar(value="" if self.cfg.get("template_profile") == "templates_cn" else "国际服")
        server_cb = ttk.Combobox(sf, textvariable=self.server_var,
                                  values=["国际服", "国服"],
                                  width=12, state="readonly")
        server_cb.grid(row=0, column=1, padx=5, pady=10, sticky="w")
        def _check_server(event):
            if self.server_var.get() == "国服":
                messagebox.showwarning("国服暂不支持", "国服模板尚未完善，目前仅支持国际服。\n请选择「国际服」继续使用。")
                self.server_var.set("国际服")
        server_cb.bind("<<ComboboxSelected>>", _check_server)
        ttk.Label(sf, text="开发中...", foreground="#888").grid(row=0, column=2, padx=5, pady=10, sticky="w")

        mf = ttk.Frame(nb); nb.add(mf, text="运行模式")
        ttk.Label(mf, text="刷取目标:", foreground=COLOR_ACCENT).grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        self.mission_var = tk.StringVar(value=self.cfg.get("game", {}).get("mission", "zero_system"))
        mission_display = {"zero_system": "零式系统", "season_reroll": "赛季图初始刷取"}
        mission_reverse = {v: k for k, v in mission_display.items()}
        self.mission_display_var = tk.StringVar(value=mission_display.get(self.mission_var.get(), "零式系统"))
        mission_cb = ttk.Combobox(mf, textvariable=self.mission_display_var,
                                   values=list(mission_display.values()), width=18, state="readonly")
        mission_cb.grid(row=0, column=1, padx=5, pady=(10, 5), sticky="w")
        def _sync_mission(event):
            self.mission_var.set(mission_reverse.get(self.mission_display_var.get(), "zero_system"))
        mission_cb.bind("<<ComboboxSelected>>", _sync_mission)
        ToolTip(mission_cb, "选择要刷取的模式\n零式系统自动刷取\n赛季图初始刷取OCR匹配赛季图初始Buff直选退出")

        ttk.Separator(mf, orient="horizontal").grid(row=1, column=0, columnspan=2, sticky="ew", pady=10, padx=10)

        ttk.Label(mf, text="运行平台:", foreground=COLOR_ACCENT).grid(row=2, column=0, padx=10, pady=(5, 2), sticky="w")
        self.mode_var = tk.StringVar(value=self.cfg.get("game", {}).get("mode", "pc"))
        mode_display_map = {"pc": "PC端/云游戏", "emulator": "模拟器"}
        mode_reverse_map = {v: k for k, v in mode_display_map.items()}
        self.mode_display_var = tk.StringVar(value=mode_display_map.get(self.mode_var.get(), "PC端/云游戏"))
        mode_cb = ttk.Combobox(mf, textvariable=self.mode_display_var,
                                values=list(mode_display_map.values()),
                                width=20, state="readonly")
        mode_cb.grid(row=2, column=1, padx=5, pady=(5, 2), sticky="w")
        def _sync_mode(event):
            self.mode_var.set(mode_reverse_map.get(self.mode_display_var.get(), "pc"))
        mode_cb.bind("<<ComboboxSelected>>", _sync_mode)

        ttk.Label(mf, text="输入方式:", foreground=COLOR_ACCENT).grid(row=3, column=0, padx=10, pady=(15, 2), sticky="w")
        self.input_backend_var = tk.StringVar(value=self.cfg.get("game", {}).get("input_backend", "sendinput"))
        backend_display = {"sendinput": "SendInput(前台推荐)", "sendmessage": "SendMessage(后台)", "postmessage": "PostMessage(后台)"}
        backend_reverse = {v: k for k, v in backend_display.items()}
        self.input_backend_display = tk.StringVar(value=backend_display.get(self.input_backend_var.get(), "SendInput(前台推荐)"))
        input_cb = ttk.Combobox(mf, textvariable=self.input_backend_display,
                                 values=list(backend_display.values()),
                                 width=30, state="readonly")
        input_cb.grid(row=3, column=1, padx=5, pady=(15, 2), sticky="w")
        def _sync_backend(event):
            self.input_backend_var.set(backend_reverse.get(self.input_backend_display.get(), "sendmessage"))
        input_cb.bind("<<ComboboxSelected>>", _sync_backend)

        self.keep_mouse_var = tk.BooleanVar(value=self.cfg.get("debug", {}).get("keep_mouse", False))
        ttk.Label(mf, text="调试模式:", foreground=COLOR_ACCENT).grid(row=4, column=0, padx=10, pady=(15, 2), sticky="w")
        tk.Checkbutton(mf, text="鼠标不归位", variable=self.keep_mouse_var, bg=COLOR_CARD, fg=COLOR_TEXT, selectcolor=COLOR_CARD, activebackground=COLOR_CARD, activeforeground=COLOR_TEXT).grid(row=4, column=1, padx=5, pady=(15, 2), sticky="w")

        zf = ttk.Frame(nb); nb.add(zf, text="赛季图初始刷取")
        zf_canvas = tk.Canvas(zf, bg=COLOR_BG, highlightthickness=0)
        zf_sb = ttk.Scrollbar(zf, orient="vertical", command=zf_canvas.yview)
        sf = tk.Frame(zf_canvas, bg=COLOR_BG)
        sf.bind("<Configure>", lambda e: zf_canvas.configure(scrollregion=zf_canvas.bbox("all")))
        zf_canvas.create_window((0, 0), window=sf, anchor="nw")
        zf_canvas.configure(yscrollcommand=zf_sb.set)
        zf_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        zf_sb.pack(side=tk.RIGHT, fill=tk.Y)
        def _on_mw(event):
            zf_canvas.yview_scroll(-1 * (event.delta // 120), "units")
        zf_canvas.bind("<MouseWheel>", _on_mw)
        sf.bind("<MouseWheel>", _on_mw)

        ocr_cfg = self.cfg.get("ocr", {})
        is_global = self.server_var.get() == "国际服"
        entry_kw_default = ["M"] if is_global else [""]
        exit_kw_default = ["ESC", "退出", "_J"] if is_global else ["ESC", "返回", "关闭"]
        keyword_default = "退出2x" if is_global else "退出2选"
        row = 0

        ttk.Label(sf, text="入口关键词:", foreground=COLOR_ACCENT).grid(row=row, column=0, padx=10, pady=(10, 2), sticky="w")
        ek = ocr_cfg.get("entry_keywords", entry_kw_default)
        self.ocr_entry_kw = tk.StringVar(value=",".join(ek))
        e1 = ttk.Entry(sf, textvariable=self.ocr_entry_kw, width=24)
        e1.grid(row=row, column=1, padx=5, pady=(10, 2), sticky="w")
        ToolTip(e1, "赛季图入口关键词，逗号分隔\n用于OCR匹配，找到其中一个即进入\n留空则视为手动，不自动开始\n国际服通常为 M")
        row += 1

        ttk.Label(sf, text="Buff目标关键词:", foreground=COLOR_ACCENT).grid(row=row, column=0, padx=10, pady=(8, 2), sticky="w")
        self.ocr_keyword = tk.StringVar(value=ocr_cfg.get("keyword", keyword_default))
        e2 = ttk.Entry(sf, textvariable=self.ocr_keyword, width=28)
        e2.grid(row=row, column=1, padx=5, pady=(8, 2), sticky="w")
        ToolTip(e2, "Buff 目标关键词\n识别到即停止循环\n支持正则: 退出|离开 ")
        row += 1

        ttk.Label(sf, text="Buff选择区域:", foreground=COLOR_ACCENT).grid(row=row, column=0, padx=10, pady=(8, 2), sticky="w")
        ocr_region = ocr_cfg.get("buff_region", [100, 300, 800, 300])
        f = ttk.Frame(sf); f.grid(row=row, column=1, padx=5, pady=(8, 2), sticky="w")
        ovs = []
        for idx, label in enumerate(["x", "y", "w", "h"]):
            v = tk.StringVar(value=str(ocr_region[idx]))
            ttk.Entry(f, textvariable=v, width=5).pack(side=tk.LEFT)
            if idx < 3: ttk.Label(f, text=",").pack(side=tk.LEFT)
            ovs.append(v)
        self.ocr_buff_region = ovs
        ToolTip(f, "Buff 选择区域坐标\nOCR 扫描识别关键词的区域")
        row += 1

        ttk.Label(sf, text="退出关键词", foreground=COLOR_ACCENT).grid(row=row, column=0, padx=10, pady=(8, 2), sticky="w")
        exit_kws = ocr_cfg.get("exit_keywords", exit_kw_default)
        self.ocr_exit_kw = tk.StringVar(value=",".join(exit_kws))
        e3 = ttk.Entry(sf, textvariable=self.ocr_exit_kw, width=24)
        e3.grid(row=row, column=1, padx=5, pady=(8, 2), sticky="w")
        ToolTip(e3, "退出时所需关键词，逗号分隔\n用于OCR匹配，找到其中一个即退出\n默认ESC,退出\n国际服通常为 ESC,退出,_J")
        row += 1

        ttk.Label(sf, text="退出关键词偏移", foreground=COLOR_ACCENT).grid(row=row, column=0, padx=10, pady=(8, 2), sticky="w")
        exit_offs = ocr_cfg.get("exit_keyword_offsets", [[0, -20], [0, 0], [0, 0]])
        off_strs = [f"{o[0]},{o[1]}" for o in exit_offs]
        self.ocr_exit_off = tk.StringVar(value=";".join(off_strs))
        e4 = ttk.Entry(sf, textvariable=self.ocr_exit_off, width=24)
        e4.grid(row=row, column=1, padx=5, pady=(8, 2), sticky="w")
        ToolTip(e4, "偏移格式: 文字,x,y 用;分隔\n按ESC取消: 0,-20")
        row += 1

        ttk.Label(sf, text="Buff OCR设置", foreground=COLOR_ACCENT).grid(row=row, column=0, padx=10, pady=(8, 2), sticky="w")
        buff_ocr_kw_default = "一回合内Yg减少HP变化" if is_global else "一回合内格挡HP减少"
        self.ocr_buff_keyword = tk.StringVar(value=ocr_cfg.get("buff_ocr_keyword", buff_ocr_kw_default))
        eb = ttk.Entry(sf, textvariable=self.ocr_buff_keyword, width=30)
        eb.grid(row=row, column=1, padx=5, pady=(8, 2), sticky="w")
        ToolTip(eb, "零式系统Buff OCR关键词\n模板匹配到Buff OCR位置\n找到则停止循环自动响应\n默认为英文关键词")
        row += 1

        ttk.Label(sf, text="OCR :", foreground=COLOR_ACCENT).grid(row=row, column=0, padx=10, pady=(8, 2), sticky="w")
        self.ocr_backend = tk.StringVar(value=ocr_cfg.get("backend", "windows"))
        cb = ttk.Combobox(sf, textvariable=self.ocr_backend, values=["windows", "paddle"], width=12, state="readonly")
        cb.grid(row=row, column=1, padx=5, pady=(8, 2), sticky="w")
        ToolTip(cb, "OCR 识别后端\nwindows = 系统自带OCR(快速)\npaddle = PaddleOCR离线识别(更强准确)")

    def _on_mode_change(self):
        pass

    def save(self):
        for k, var in self.entries.items():
            parts = k.split("_", 1)
            sec, rest = parts[0], parts[1]
            try:
                if sec == "c":
                    suffix = rest[-1]
                    ck = rest[:-2]
                    if ck not in self.cfg.setdefault("click_points", {}):
                        self.cfg["click_points"][ck] = [0, 0, 0, 0] if suffix in ("w", "h") else [0, 0]
                    idx = {"x": 0, "y": 1, "w": 2, "h": 3}.get(suffix)
                    if idx is not None:
                        self.cfg["click_points"][ck][idx] = int(var.get())
                elif sec == "t":
                    self.cfg.setdefault("timing", {})[rest] = float(var.get())
                elif sec == "b":
                    self.cfg.setdefault("combat", {})[rest] = int(var.get()) if "max_turns" in rest else float(var.get())
            except ValueError:
                pass
        self.cfg["template_profile"] = "templates_global"
        self.cfg.setdefault("game", {})["mode"] = self.mode_var.get()
        self.cfg["game"]["mission"] = self.mission_var.get()
        self.cfg["game"]["input_backend"] = self.input_backend_var.get()
        self.cfg.setdefault("ocr", {})["entry_keywords"] = [s.strip() for s in self.ocr_entry_kw.get().split(",") if s.strip()]
        self.cfg["ocr"]["keyword"] = self.ocr_keyword.get()
        self.cfg["ocr"]["exit_keywords"] = [s.strip() for s in self.ocr_exit_kw.get().split(",") if s.strip()]
        self.cfg["ocr"]["backend"] = self.ocr_backend.get()
        off_parts = [s.strip() for s in self.ocr_exit_off.get().split(";") if s.strip()]
        off_arr = []
        for p in off_parts:
            parts = p.split(",")
            if len(parts) == 2:
                off_arr.append([int(parts[0]), int(parts[1])])
        self.cfg["ocr"]["exit_keyword_offsets"] = off_arr
        self.cfg["ocr"]["buff_region"] = [int(v.get()) for v in self.ocr_buff_region]
        self.cfg["ocr"]["buff_ocr_keyword"] = self.ocr_buff_keyword.get()
        self.cfg.setdefault("debug", {})["keep_mouse"] = self.keep_mouse_var.get()
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.cfg, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("成功", "已保存")
        self.destroy()


class CznZeroFarmGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("CZN Zero Farm - 零式系统自动刷取")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 680)
        self.root.configure(bg=COLOR_BG)
        self._running = False
        self._paused = False
        self._stop_evt = threading.Event()
        self._pause_evt = threading.Event()
        self._log_font_size = 10
        self._setup_styles()
        self._setup_ui()
        self._setup_logging()
        self._update_timer()

    def _setup_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=COLOR_BG, foreground=COLOR_TEXT, fieldbackground=COLOR_CARD,
                     bordercolor=COLOR_BORDER, darkcolor=COLOR_BG, lightcolor=COLOR_BG,
                     arrowcolor=COLOR_TEXT, troughcolor=COLOR_BG, selectbackground=COLOR_ACCENT,
                     selectforeground=COLOR_TEXT)
        s.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT)
        s.configure("Sidebar.TFrame", background=COLOR_SIDEBAR)
        s.configure("Card.TFrame", background=COLOR_CARD, relief="solid", borderwidth=1)
        s.configure("Accent.TButton", background=COLOR_ACCENT, foreground=COLOR_TEXT, borderwidth=0,
                     focusthickness=0, padding=(16, 8))
        s.configure("Tool.TButton", background=COLOR_CARD, foreground=COLOR_TEXT, borderwidth=0,
                     focusthickness=0, padding=(12, 6))
        s.configure("Stop.TButton", background="#c72e2e", foreground=COLOR_TEXT, borderwidth=0,
                     focusthickness=0, padding=(12, 6))
        s.configure("Title.TLabel", background=COLOR_BG, foreground=COLOR_ACCENT, font=("Segoe UI", 14, "bold"))
        s.configure("Stat.TLabel", background=COLOR_BG, foreground=COLOR_TEXT, font=("Segoe UI", 22, "bold"))
        s.configure("StatLabel.TLabel", background=COLOR_BG, foreground=COLOR_TEXT_SEC, font=("Segoe UI", 9))
        s.configure("Status.TLabel", background=COLOR_BG, foreground=COLOR_TEXT_SEC, font=("Segoe UI", 10))
        s.configure("Log.TFrame", background=COLOR_LOG_BG)
        s.configure("TCombobox", fieldbackground=COLOR_CARD, foreground=COLOR_TEXT, background=COLOR_BG,
                     arrowcolor=COLOR_TEXT)
        s.configure("TNotebook", background=COLOR_BG, foreground=COLOR_TEXT)
        s.configure("TNotebook.Tab", background=COLOR_CARD, foreground=COLOR_TEXT, padding=(10, 4))
        s.map("TNotebook.Tab", background=[("selected", COLOR_ACCENT)])
        s.map("Accent.TButton", background=[("active", COLOR_ACCENT_HOVER), ("disabled", COLOR_CARD)])
        s.map("Tool.TButton", background=[("active", COLOR_ACCENT), ("disabled", COLOR_CARD)])
        s.map("Stop.TButton", background=[("active", "#d64545"), ("disabled", COLOR_CARD)])
        s.map("TCombobox", fieldbackground=[("readonly", COLOR_CARD)], foreground=[("readonly", COLOR_TEXT)])
        s.map("TEntry", fieldbackground=[("!disabled", COLOR_CARD)], foreground=[("!disabled", COLOR_TEXT)])

    def _get_templates_dir(self):
        return get_profile_dir(self.profile_var.get())

    def _make_sidebar_button(self, parent, text, command, style="Tool.TButton", width=14):
        btn = tk.Button(parent, text=text, command=command, bg=COLOR_CARD, fg=COLOR_TEXT,
                         activebackground=COLOR_ACCENT, activeforeground=COLOR_TEXT,
                         bd=0, padx=14, pady=8, anchor="w", width=width,
                         font=("Segoe UI", 10), cursor="hand2", highlightthickness=0, takefocus=0)
        btn.pack(fill=tk.X, padx=8, pady=2)
        return btn

    def _setup_ui(self):
        # 主框架
        main = tk.Frame(self.root, bg=COLOR_BG)
        main.pack(fill=tk.BOTH, expand=True)
        main.pack_propagate(False)

        # ============ ????============
        top = tk.Frame(main, bg=COLOR_BG, height=48)
        top.pack(fill=tk.X, padx=16, pady=(10, 0))
        top.pack_propagate(False)

        tk.Label(top, text="CZN ZERO FARM", fg=COLOR_ACCENT, bg=COLOR_BG,
                 font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT)

        self.status_lbl = tk.Label(top, text="已停止", fg=COLOR_TEXT_SEC, bg=COLOR_BG,
                                    font=("Segoe UI", 11))
        self.status_lbl.pack(side=tk.LEFT, padx=(16, 0))

        self.profile_var = tk.StringVar()
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        self.profile_var.set(cfg.get("template_profile", "templates_global"))

        # ============ ????============
        content = tk.Frame(main, bg=COLOR_BG)
        content.pack(fill=tk.BOTH, expand=True, padx=16, pady=(10, 0))
        content.pack_propagate(False)

        # ----- ??-----
        sidebar = tk.Frame(content, bg=COLOR_SIDEBAR, width=180)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # 按钮区域
        tk.Label(sidebar, text="操作", fg=COLOR_ACCENT, bg=COLOR_SIDEBAR,
                 font=("Segoe UI", 9, "bold")).pack(pady=(12, 6))

        self.btn_start = self._make_sidebar_button(sidebar, "▶ 开始运行", self.start)
        self.btn_pause = self._make_sidebar_button(sidebar, "⏸ 暂停", self.pause)
        self.btn_stop = self._make_sidebar_button(sidebar, "⏹ 停止运行", self.stop)

        tk.Label(sidebar, text="", fg=COLOR_ACCENT, bg=COLOR_SIDEBAR,
                 font=("Segoe UI", 9, "bold")).pack(pady=(16, 6))

        self._make_sidebar_button(sidebar, "📷 模板采集", self.capture_mode)
        self._make_sidebar_button(sidebar, "🔧 诊断", self.diagnose)
        self._make_sidebar_button(sidebar, "设置", lambda: ConfigDialog(self.root))

        # ----- 右侧主区域 -----
        right = tk.Frame(content, bg=COLOR_BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))

        # s???
        stat_card = tk.Frame(right, bg=COLOR_CARD, bd=1, relief="solid", highlightbackground=COLOR_BORDER,
                              highlightthickness=1)
        stat_card.pack(fill=tk.X)

        stat_row = tk.Frame(stat_card, bg=COLOR_CARD)
        stat_row.pack(fill=tk.X, padx=16, pady=(12, 12))

        self.sv = {}
        stat_items = [
            ("局", "runs"), ("战", "battles"),
            ("精", "elites"), ("层", "floors"), ("事", "events")
        ]
        for label, key in stat_items:
            sf = tk.Frame(stat_row, bg=COLOR_CARD)
            sf.pack(side=tk.LEFT, padx=(0, 28))
            tk.Label(sf, text=label, fg=COLOR_TEXT_SEC, bg=COLOR_CARD,
                     font=("Segoe UI", 9)).pack()
            v = tk.StringVar(value="0")
            tk.Label(sf, textvariable=v, fg=COLOR_TEXT, bg=COLOR_CARD,
                     font=("Segoe UI", 22, "bold")).pack()
            self.sv[key] = v

        self.time_var = tk.StringVar(value="00:00:00")
        tk.Label(stat_row, textvariable=self.time_var, fg=COLOR_ACCENT, bg=COLOR_CARD,
                 font=("Segoe UI", 22, "bold")).pack(side=tk.RIGHT, padx=(10, 0))
        tk.Label(stat_row, text="耗时", fg=COLOR_TEXT_SEC, bg=COLOR_CARD,
                 font=("Segoe UI", 9)).pack(side=tk.RIGHT)

        # 日志面板
        log_card = tk.Frame(right, bg=COLOR_CARD, bd=1, relief="solid",
                             highlightbackground=COLOR_BORDER, highlightthickness=1)
        log_card.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        log_header = tk.Frame(log_card, bg=COLOR_CARD)
        log_header.pack(fill=tk.X, padx=12, pady=(8, 0))
        tk.Label(log_header, text="日志", fg=COLOR_TEXT_SEC, bg=COLOR_CARD,
                 font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)

        self._log_font = font.Font(family="Consolas", size=self._log_font_size)
        self.log = scrolledtext.ScrolledText(log_card, wrap=tk.WORD, font=self._log_font, height=20,
                                              bg=COLOR_LOG_BG, fg=COLOR_TEXT, bd=0,
                                              insertbackground=COLOR_TEXT, highlightthickness=0)
        self.log.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 10))
        log_card.pack_propagate(False)

        # Ctrl+滚轮缩放
        def _zoom(event):
            size = self._log_font.cget("size")
            if event.delta > 0:
                size = min(24, size + 1)
            else:
                size = max(8, size - 1)
            self._log_font.configure(size=size)
        self.log.bind("<Control-MouseWheel>", _zoom)

        # ============ 底部状态栏 ============
        bottom = tk.Frame(main, bg=COLOR_SIDEBAR, height=32)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)
        bottom.pack_propagate(False)

        self.status_text = tk.Label(bottom, text="  |  F6=开始 F8=停止 F9=暂停", fg=COLOR_TEXT_SEC,
                                     bg=COLOR_SIDEBAR, font=("Segoe UI", 9), anchor="w")
        self.status_text.pack(side=tk.LEFT, padx=12)

        # 初始化按钮状态
        self.btn_pause.config(state=tk.DISABLED, bg=COLOR_CARD, fg=COLOR_TEXT_SEC)
        self.btn_stop.config(state=tk.DISABLED, bg=COLOR_CARD, fg=COLOR_TEXT_SEC)

        self._setup_hotkeys()

        self.root.update_idletasks()
        self.root.minsize(self.root.winfo_width(), self.root.winfo_height())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_profile_change(self, event=None):
        profile = self.profile_var.get()
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        cfg["template_profile"] = profile
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        tdir = self._get_templates_dir()
        n = len(list(tdir.glob("*"))) if tdir.exists() else 0
        logging.info(f"已加载 [{profile}] ({n} 个模板)")

    def _setup_hotkeys(self):
        self.root.bind("<F6>", lambda e: self.start())
        self.root.bind("<F8>", lambda e: self.stop())
        self.root.bind("<F9>", lambda e: self.pause())
        try:
            import keyboard as kb
            kb.add_hotkey("f6", self.start, suppress=True)
            kb.add_hotkey("f8", self.stop, suppress=True)
            kb.add_hotkey("f9", self.pause, suppress=True)
            logging.info("热键已注册 F6=开始 F8=停止 F9=暂停")
        except Exception as e:
            logging.warning(f"热键注册失败(原因: {e})")
            logging.info("使用备用热键 F6=开始 F8=停止 F9=暂停")

    def _setup_logging(self):
        handler = TextHandler(self.log)
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", datefmt="%H:%M:%S"))
        for h in logging.getLogger().handlers[:]:
            logging.getLogger().removeHandler(h)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.DEBUG)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fh = logging.FileHandler(LOGS_DIR / f"czn_zero_{ts}.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", datefmt="%H:%M:%S"))
        logging.getLogger().addHandler(fh)
        tdir = self._get_templates_dir()
        n = len(list(tdir.glob("*"))) if tdir.exists() else 0
        logging.info(f"GUI 启动完成 | 配置: [{self.profile_var.get()}] ({n} 个模板)")

    def _update_timer(self):
        if self._running and hasattr(self, '_start_time'):
            e = int(time.time() - self._start_time)
            self.time_var.set(f"{e//3600:02d}:{(e%3600)//60:02d}:{e%60:02d}")
        self.root.after(1000, self._update_timer)

    def _set_ui_running(self, running):
        state_normal = tk.NORMAL
        state_disabled = tk.DISABLED
        if running:
            self.btn_start.config(state=state_disabled, bg=COLOR_CARD, fg=COLOR_TEXT_SEC)
            self.btn_pause.config(state=state_normal, bg=COLOR_CARD, fg=COLOR_TEXT,
                                   text="暂停" if not self._paused else "继续")
            self.btn_stop.config(state=state_normal, bg="#c72e2e", fg=COLOR_TEXT)
        else:
            self.btn_start.config(state=state_normal, bg=COLOR_CARD, fg=COLOR_TEXT)
            self.btn_pause.config(state=state_disabled, bg=COLOR_CARD, fg=COLOR_TEXT_SEC, text="⏸ 暂停")
            self.btn_stop.config(state=state_disabled, bg=COLOR_CARD, fg=COLOR_TEXT_SEC)
        self.status_lbl.config(text="运行中" if running else "已停止",
                               fg=COLOR_GREEN if running else COLOR_TEXT_SEC)

    def start(self):
        if self._running:
            return
        tdir = self._get_templates_dir()
        if not tdir.exists() or not any(tdir.iterdir()):
            if not messagebox.askyesno("模板缺失", f"[{self.profile_var.get()}] 模板图片目录为空\n是否继续?"):
                return
        self._running = True
        self._paused = False
        self._stop_evt.clear()
        self._pause_evt.clear()
        self._start_time = time.time()
        self._set_ui_running(True)
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        t = threading.Thread(target=self._worker, args=(cfg,), daemon=True)
        t.start()

    def stop(self):
        if not self._running:
            return
        self._stop_evt.set()
        self._running = False
        self._set_ui_running(False)

    def pause(self):
        if not self._running:
            return
        self._paused = not self._paused
        if self._paused:
            self._pause_evt.set()
            self.btn_pause.config(text="▶ 继续")
            self.status_lbl.config(text="已暂停", fg=COLOR_YELLOW)
            logging.warning("用户暂停")
        else:
            self._pause_evt.clear()
            self.btn_pause.config(text="⏸ 暂停")
            self.status_lbl.config(text="运行中", fg=COLOR_GREEN)
            logging.info("已暂停")

    def capture_mode(self):
        tdir = self._get_templates_dir()
        tdir.mkdir(parents=True, exist_ok=True)
        cap = ScreenCapturer()
        logging.info(f"=== 模板采集模式 [{self.profile_var.get()}] ===")
        logging.info(f"目录 {tdir}")
        logging.info("F7=保存截图  Esc=退出")
        cnt = [0]
        logging.info(f"保存至: {tdir.resolve()}")
        def check_keys():
            import keyboard as kb
            while True:
                if kb.is_pressed("f7"):
                    cnt[0] += 1
                    frame = cap.capture()
                    ts = datetime.datetime.now().strftime("%H%M%S")
                    name = f"template_{cnt[0]:02d}_{ts}.png"
                    path = tdir / name
                    ok = imwrite_unicode(path, frame)
                    if not ok:
                        logging.error(f"写入失败: {path}")
                    logging.info(f"已保存({cnt[0]}): {path.resolve()}")
                    time.sleep(0.5)
                if kb.is_pressed("esc"):
                    logging.info(f"采集完成! 共{cnt[0]}张截图 -> {tdir.name}")
                    logging.info("参考命名规范参考 AGENTS.md")
                    break
                time.sleep(0.1)
        t = threading.Thread(target=check_keys, daemon=True)
        t.start()

    def diagnose(self):
        import ctypes
        user32 = ctypes.windll.user32

        tdir = self._get_templates_dir()
        tdir.mkdir(parents=True, exist_ok=True)
        cap = ScreenCapturer()
        matcher = TemplateMatcher(tdir)
        detector = StateDetector(matcher)

        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        title = cfg.get("game", {}).get("window_title", "卡厄思梦境")
        hwnd = user32.FindWindowW(None, title)

        logging.info("=" * 40)
        logging.info(f"诊断模式 [{self.profile_var.get()}]")

        if hwnd:
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w, h = rect.right - rect.left, rect.bottom - rect.top
            logging.info(f"   找到游戏窗口")
            logging.info(f"      标题: {title}  句柄: {hwnd}")
            logging.info(f"      位置: ({rect.left},{rect.top})  {w}x{h}")
        else:
            logging.info(f"   未找到窗口 [{title}]")
            logging.info(f"      请确认游戏窗口标题为 {title}")

        frame = cap.capture()
        res = cap.get_resolution()
        ts = datetime.datetime.now().strftime("%H%M%S")
        debug_path = Path("debug")
        debug_path.mkdir(parents=True, exist_ok=True)
        diag_file = debug_path / f"diagnose_{ts}.png"
        imwrite_unicode(diag_file, frame)

        state = detector.detect(frame)
        n_templates = len(matcher.templates)

        logging.info(f"   分辨率 {res[0]}x{res[1]}")
        logging.info(f"   模板: {n_templates}")
        logging.info(f"   当前状态 [{state.value}]")
        logging.info(f"   诊断图: {diag_file.resolve()}")
        logging.info("=" * 40)

    def _worker(self, cfg):
        g = cfg["game"]
        class SC: pass
        sc = SC()
        sc.base_res = tuple(g["resolution"])
        sc.click_points = cfg["click_points"]
        sc.card_hand = cfg["card_hand"]
        sc.combat = cfg["combat"]
        sc.timing = cfg["timing"]

        tdir = get_profile_dir(cfg.get("template_profile", "templates_cn"))
        capturer = ScreenCapturer()
        matcher = TemplateMatcher(tdir)
        detector = StateDetector(matcher)
        sim = InputSimulator(backend=cfg.get("game", {}).get("input_backend", "sendinput"))
        sim.keep_mouse = cfg.get("debug", {}).get("keep_mouse", False)
        mission = cfg.get("game", {}).get("mission", "zero_system")
        combat_mod = CombatModule()
        stats = {"runs": 0, "battles": 0, "elites": 0, "floors": 0, "events": 0}
        unknown_cnt = 0
        offsets = cfg.get("click_offsets", {})
        season_reroll_exiting = False
        season_reroll_ocr = None
        season_reroll_entry_idx = 0
        season_reroll_exit_idx = 0
        season_reroll_buff_miss = 0
        # 重置状态标志
        self._codex_active = False
        self._buff_active = False
        self._buff_done = False
        self._buff_cooldown = 0.0
        self._unex_active = False
        self._unex_done = False
        self._unex_cooldown = 0.0
        self._once = set()

        def _click(tpl_name=None, default_pos=None):
            pos = default_pos or detector.last_pos
            if tpl_name and tpl_name in offsets:
                pos = (pos[0] + offsets[tpl_name][0], pos[1] + offsets[tpl_name][1])
            sim.click_at(pos[0], pos[1], res[0], res[1])

        logging.info(f"=== 开始运行 [配置: {tdir.name}] ===")

        while not self._stop_evt.is_set():
            if self._pause_evt.is_set():
                time.sleep(0.3); continue
            try:
                frame = capturer.capture()
                res = capturer.get_resolution()
                state = detector.detect(frame)
                # 状态变化检测
                if not hasattr(self, '_prev_state'):
                    self._prev_state = None
                if state != self._prev_state:
                    prev_name = self._prev_state.value if self._prev_state else '无'
                    logging.info(f"状态 {prev_name} -> {state.value}")
                    self._prev_state = state

                sr_delay = 0.05
                if mission == "season_reroll":

                    ocr_cfg = cfg.get("ocr", {})
                    if season_reroll_ocr is None:
                        from ocr import OcrReader
                        lang = "zh-hk" if cfg.get("template_profile") == "templates_global" else "zh-cn"
                        backend = ocr_cfg.get("backend", "windows")
                        season_reroll_ocr = OcrReader(lang, backend)
                    is_global = cfg.get("template_profile") == "templates_global"
                    kw_default = "退出2x" if is_global else "退出2选"
                    entry_default = ["M"] if is_global else [""]
                    exit_default = ["ESC", "退出", "_J"] if is_global else ["ESC", "返回", "关闭"]
                    if season_reroll_exiting:
                        exit_kws = ocr_cfg.get("exit_keywords", exit_default)
                        exit_offsets = ocr_cfg.get("exit_keyword_offsets", [])
                        if season_reroll_exit_idx < len(exit_kws):
                            kw = exit_kws[season_reroll_exit_idx]
                            offset = exit_offsets[season_reroll_exit_idx] if season_reroll_exit_idx < len(exit_offsets) else [0, 0]
                            # 0: OCR精确匹配ESC模板；1: 点击RETREAT；2+: 点击SKIP_CONFIRM
                            target_state = None
                            if season_reroll_exit_idx == 1:
                                target_state = GameState.RETREAT
                            elif season_reroll_exit_idx >= 2:
                                target_state = GameState.SKIP_CONFIRM
                            if target_state is not None and state == target_state:
                                cx, cy = detector.last_pos[0] + offset[0], detector.last_pos[1] + offset[1]
                                logging.info(f"模板匹配 {kw} ({cx},{cy}) conf={detector.last_conf:.3f}")
                                sim.click_at(cx, cy, res[0], res[1])
                                season_reroll_exit_idx += 1
                            else:
                                pos = season_reroll_ocr.find_text(frame, kw, None, consecutive=True)
                                if pos:
                                    cx, cy = pos[0] + offset[0], pos[1] + offset[1]
                                    logging.info(f"找到 {kw} ({cx},{cy})")
                                    sim.click_at(cx, cy, res[0], res[1])
                                    season_reroll_exit_idx += 1
                                elif state == GameState.RETREAT:
                                    cx, cy = detector.last_pos[0] + offset[0], detector.last_pos[1] + offset[1]
                                    logging.info(f"模板已到 {kw} ({cx},{cy})")
                                    sim.click_at(cx, cy, res[0], res[1])
                                    season_reroll_exit_idx += 1
                                else:
                                    logging.info(f"等待 {kw}")
                            time.sleep(sr_delay)
                        else:
                            season_reroll_exiting = False
                            season_reroll_entry_idx = 0
                            season_reroll_exit_idx = 0
                            season_reroll_buff_miss = 0
                            logging.info("退出完成准备下一轮")
                        continue
                    entry_kws = ocr_cfg.get("entry_keywords", entry_default)
                    if season_reroll_entry_idx < len(entry_kws):
                        kw = entry_kws[season_reroll_entry_idx]
                        pos = season_reroll_ocr.find_text(frame, kw, None, consecutive=True)
                        if pos:
                            logging.info(f"入口找到 {kw} ({season_reroll_entry_idx+1}/{len(entry_kws)})")
                            sim.click_at(pos[0], pos[1], res[0], res[1])
                            season_reroll_entry_idx += 1
                            time.sleep(5.0)
                        else:
                            logging.info(f"入口等待 {kw}")
                        time.sleep(sr_delay)
                        continue
                    kw = ocr_cfg.get("keyword", kw_default)
                    all_texts = season_reroll_ocr.scan(frame)  # +????
                    pos = None
                    chars = list(kw)
                    sorted_w = sorted(all_texts, key=lambda t: (t[2], t[1]))
                    # ??7?
                    for t, bx, by, bw, bh in all_texts:
                        if kw in t:
                            pos = (bx + bw // 2, by + bh // 2)
                            break
                    # ?????                    if not pos and len(kw) > 1:
                        for i in range(len(sorted_w) - len(chars) + 1):
                            if all(sorted_w[i+j][0] == ch for j, ch in enumerate(chars)):
                                _, bx, by, bw, bh = sorted_w[i]
                                pos = (bx + bw // 2, by + bh // 2)
                                break
                    # OCR失败+截图
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
                                self.stop()
                                time.sleep(sr_delay)
                                continue
                            else:
                                logging.info(f"OCR原文: {all_text[:120]!r}")
                                import cv2
                                cv2.imwrite("debug/buff_scan_fail.png", frame)
                                logging.info("已保存 debug/buff_scan_fail.png")
                    if pos:
                        logging.info(f"找到目标Buff: {kw}")
                        sim.click_at(pos[0], pos[1], res[0], res[1])
                        self.stop()
                    else:
                        season_reroll_buff_miss += 1
                        if season_reroll_buff_miss >= 2:
                            logging.info(f"{season_reroll_buff_miss}次未找到，退出")
                            season_reroll_exiting = True
                            season_reroll_exit_idx = 0
                            season_reroll_buff_miss = 0
                        else:
                            logging.info(f"未找到目标Buff({season_reroll_buff_miss}次，继续)")
                    time.sleep(sr_delay)
                    continue

                if state == GameState.UNKNOWN:
                    unknown_cnt += 1
                    if unknown_cnt >= 50:
                        logging.warning(f"{unknown_cnt}次未知状态")
                        unknown_cnt = 0
                    time.sleep(sr_delay)
                    continue
                unknown_cnt = 0; t = sc.timing

                settlement_tpls = ["settlement_click", "dismantle_confirm", "settlement_confirm", "node_settlement", "next_step"]

                now = time.time()
                if not hasattr(self, '_state_cd'):
                    self._state_cd = {}
                if not hasattr(self, '_once'): self._once = set()
                if not hasattr(self, '_codex_active'): self._codex_active = False
                if not hasattr(self, '_buff_active'): self._buff_active = False
                if not hasattr(self, '_buff_done'): self._buff_done = False
                if not hasattr(self, '_buff_cooldown'): self._buff_cooldown = 0.0
                if not hasattr(self, '_unex_active'): self._unex_active = False
                if not hasattr(self, '_unex_done'): self._unex_done = False
                if not hasattr(self, '_unex_cooldown'): self._unex_cooldown = 0.0

                # 意外房间 mode
                if self._unex_active:
                    found, conf, pos = detector.matcher.match(frame, "event_option2", 0.9)
                    if found:
                        logging.info(f"意外房间 event_option2 点击2次 中间 ({conf:.2f})")
                        for _ in range(2):
                            sim.click_at(960, pos[1], res[0], res[1])
                            time.sleep(0.2)
                        self._unex_active = False
                        self._unex_done = True
                        self._unex_cooldown = time.time() + 5
                    elif state != GameState.UNEXPECTED_ROOM:
                        self._unex_active = False
                    else:
                        time.sleep(0.5)
                    continue

                # Buff 模式只匹配 event_option2 状态
                if self._buff_active:
                    found, conf, pos = detector.matcher.match(frame, "event_option2", 0.9)
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
                        for tpl in ("codex_btn0", "codex_btn1", "codex_btn2"):
                            found, conf, pos = detector.matcher.match(frame, tpl, 0.9)
                            if found:
                                logging.info(f"合成 {tpl} ({conf:.2f})")
                                sim.click_at(pos[0], pos[1], res[0], res[1])
                                clicked = True; break

                    if not clicked:
                        for tpl in ("settle_done_1", "settle_done_2"):
                            if detector.matcher.match(frame, tpl, 0.98)[0]:
                                logging.info("法典合成完成")
                                self._codex_active = False
                                clicked = True; break
                    if clicked:
                        time.sleep(t.get("post_click_wait", 1.0))
                    else:
                        time.sleep(0.5)
                    continue
                if state == GameState.AUTO_BATTLE_OFF and "auto_battle_off" in self._once:
                    time.sleep(sr_delay); continue
                if state == GameState.MAIN_MENU:
                    self._buff_done = False
                    self._buff_cooldown = 0.0
                    self._unex_done = False
                    self._unex_cooldown = 0.0
                    logging.info("主界面→零式系统")
                    sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                elif state == GameState.ZERO_SYSTEM_ENTRY:
                    logging.info("零式系统→选法典")
                    sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                elif state == GameState.CODEX_SELECT:
                    logging.info("选法典→确认进入")
                    sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                    stats["runs"] += 1; self.root.after(0, self._update_stats, stats.copy())
                elif state == GameState.TEAM_ENTER:
                    logging.info("配队→进入")
                    sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                elif state == GameState.BUFF_SELECT:
                    if self._buff_done:
                        time.sleep(t["screenshot_interval"]); continue
                    if time.time() < self._buff_cooldown:
                        time.sleep(t["screenshot_interval"]); continue
                    self._buff_done = True
                    self._buff_cooldown = time.time() + 300
                    logging.info("Buff模式 首次选择")
                    if "buff_first_region" in cfg.get("click_points", {}):
                        rx, ry, rw, rh = cfg["click_points"]["buff_first_region"]
                        sim.click_at(rx + rw // 2, ry + rh // 2, res[0], res[1])
                    else:
                        sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                    self._buff_active = True
                elif state == GameState.UNEXPECTED_ROOM:
                    if self._unex_done:
                        time.sleep(t["screenshot_interval"]); continue
                    if time.time() < self._unex_cooldown:
                        time.sleep(t["screenshot_interval"]); continue
                    self._unex_done = True
                    self._unex_cooldown = time.time() + 300
                    logging.info("意外房间 首次选择")
                    if "buff_first_region" in cfg.get("click_points", {}):
                        rx, ry, rw, rh = cfg["click_points"]["buff_first_region"]
                        sim.click_at(rx + rw // 2, ry + rh // 2, res[0], res[1])
                    else:
                        sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                    self._unex_active = True
                elif state == GameState.ROOM_SELECT:
                    rooms = [("room_rest", 4), ("room_battle", 1), ("room_event", 2), ("room_elite", 3)]
                    clicked = False
                    for name, _ in rooms:
                        found, conf, pos = detector.matcher.match(frame, name, threshold=0.9)
                        if found:
                            logging.info(f"{name} ({conf:.2f})")
                            sim.click_at(pos[0], pos[1], res[0], res[1])
                            clicked = True; break
                    if not clicked:
                        logging.warning("所有房间没匹配到，点击默认节点")
                        sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                elif state == GameState.MAP_SCREEN:
                    logging.info("地图点击默认节点")
                    sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                elif state == GameState.COMBAT:
                    combat_mod.execute_turn(frame, res, sim, sc)
                elif state == GameState.COMBAT_VICTORY:
                    logging.info("战斗胜利"); stats["battles"] += 1; combat_mod.reset_battle()
                    self.root.after(0, self._update_stats, stats.copy())
                    time.sleep(t["post_click_wait"]); sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                elif state == GameState.CARD_REWARD:
                    logging.info("选卡奖励")
                    _click("card_reward")
                elif state == GameState.NEUTRAL_CARD_SKIP:
                    logging.info("中立卡片跳过")
                    _click("neutral_card_skip")
                elif state == GameState.SKIP_CONFIRM:
                    logging.info("跳过确认")
                    _click("skip_confirm")
                elif state == GameState.RESULT_NEXT:
                    clicked = False
                    for tpl in settlement_tpls:
                        found, conf, pos = detector.matcher.match(frame, tpl, 0.9)
                        if found:
                            logging.info(f"{tpl} ({conf:.2f})")
                            if tpl == "settlement_confirm":
                                sim.click_at(pos[0], pos[1], res[0], res[1])
                                time.sleep(0.2)
                                sim.click_at(pos[0] - 420, pos[1], res[0], res[1])
                            else:
                                sim.click_at(pos[0], pos[1], res[0], res[1])
                            clicked = True; break
                    if not clicked:
                        for tpl in ("settle_done_1", "settle_done_2"):
                            if detector.matcher.exists(tpl) and detector.matcher.match(frame, tpl, 0.9)[0]:
                                logging.info("")
                                clicked = True; break
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
                elif state == GameState.FATE_REWARD:
                    logging.info("获取命运→确定")
                    sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                elif state == GameState.REST_SCREEN:
                    logging.info("休息")
                    sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                elif state == GameState.EVENT_SCREEN:
                    stats["events"] += 1
                    y = detector.last_pos[1]
                    for x in (1350, 990, 600):
                        for _ in range(2):
                            sim.click_at(x, y, res[0], res[1])
                            time.sleep(0.2)
                elif state == GameState.DEATH_SCREEN:
                    logging.info("死亡")
                    combat_mod.reset_battle()
                    sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                elif state == GameState.EXTRACTION:
                    logging.info("提取奖励")
                    sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                elif state == GameState.RETREAT:
                    logging.info("设置→脱离")
                    sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                elif state == GameState.REMOVE_CARD_EVENT:
                    logging.info("移除卡牌")
                    _click("remove_card_event")
                elif state == GameState.CONFIRM_OPTION:
                    logging.info("确认弹窗")
                    _click("confirm_option")
                elif state == GameState.CLOSE_VIEW:
                    logging.info("关闭视图")
                    _click("close_view")
                elif state == GameState.CONTINUE_FORWARD:
                    logging.info("继续前进")
                    _click("continue_forward")
                elif state == GameState.CONFIRM_ACQUIRE:
                    logging.info("确认获得")
                    _click("confirm_acquire")
                elif state == GameState.SKIP_LEFTMOST:
                    matches = detector.matcher.match_all(frame, "skip_leftmost", threshold=0.8)
                    if matches:
                        _, cx, cy = matches[0]
                        detector.last_pos = (cx, cy)
                        logging.info(f"跳过最左 ({cx},{cy})")
                        _click("skip_leftmost")
                elif state == GameState.CARD_REWARD_SKIP:
                    logging.info("卡牌跳过")
                    _click("card_reward_skip")
                elif state == GameState.AUTO_BATTLE_OFF:
                    logging.info("关闭自动战斗")
                    sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                    self._once.add("auto_battle_off")
                elif state == GameState.WRONG_PAGE:
                    logging.info("误入其他页面")
                    _click("wrong_page")
                elif state == GameState.DELETE_SAVE:
                    logging.info("删除存档")
                    sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                elif state == GameState.DREAM_CONFIRM:
                    logging.info("梦境确认")
                    sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                elif state == GameState.INSPIRATION_CARD:
                    logging.info("灵感卡")
                    _click("inspiration_card")
                elif state == GameState.CARD_CONVERT:
                    logging.info("卡牌转换")
                    _click("card_convert")
                elif state == GameState.EVENT_DICE:
                    logging.info("事件骰子")
                    sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                elif state == GameState.DICE_NEXT:
                    logging.info("骰子下一步")
                    sim.click_at(detector.last_pos[0], detector.last_pos[1], res[0], res[1])
                elif state == GameState.SELECT_CHARACTER:
                    logging.info("选择角色")
                    bx, by = detector.last_pos
                    points = [
                        (bx - 500, by - 250),   # 上左 left-500
                        (bx, by - 250),          # 上中 center-250
                        (bx + 500, by - 250),   # 上右 right+500
                        (bx + 750, by),          # 中 match+750
                    ]
                    for px, py in points:
                        sim.click_at(px, py, res[0], res[1])
                        time.sleep(0.2)
                else:
                    time.sleep(t["screenshot_interval"]); continue
                time.sleep(t.get("post_click_wait", 1.0))
            except Exception as e:
                logging.error(f"运行错误: {e}")
                time.sleep(2.0)
        logging.info("=== 运行结束 ===")
        self.root.after(0, lambda: self._set_ui_running(False))
        self._running = False

    def _update_stats(self, s):
        for k, v in self.sv.items():
            v.set(str(s.get(k, 0)))

    def _on_close(self):
        self._stop_evt.set()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = CznZeroFarmGUI(root)
    root.mainloop()

