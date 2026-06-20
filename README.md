# CZN Zero Farm — 卡厄思梦境零式系统自动刷取脚本

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20Only-orange)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> 基于模板匹配 + 状态机的 PC 端自动化脚本，支持 **国际服** 与 **国服**。  
> 无需 AI 模型、无需 GPU，纯 OpenCV 模板匹配驱动。

---

## 目录

- [功能概述](#功能概述)
- [系统要求](#系统要求)
- [快速开始](#快速开始)
- [使用指南](#使用指南)
- [两种刷取模式](#两种刷取模式)
- [模板采集教程](#模板采集教程)
- [常见问题](#常见问题)
- [项目结构](#项目结构)

---

## 功能概述

**CZN Zero Farm** 是一套专为《卡厄思梦境》（Chaos Zero Nightmare）设计的 PC 端自动化脚本，能够：

- ✅ 自动刷取进入零式系统 → 选法典→ 法典合成 → 配队 → 选 Buff→ 选房间 → 战斗 → 结算循环
- ✅ **赛季图初始刷取** — 纯 OCR 驱动循环刷指定 Buff，刷到即停
- ✅ **自动开启战斗**（检测自动战斗开关，一键开启）
- ✅ **60+ 种模板/状态**全程模板匹配，无启发式误判
- ✅ **多结算/法典合成兼容**（手动扫描按钮模式 + 退出标志）
- ✅ **国际服 / 国服** 双版本模板（GUI 一键切换）
- ✅ **三种输入模式**：前台点击（推荐）/ 后台消息 / 不碰鼠标
- ✅ **全局热键**：F6 开始 / F8 停止 / F9 暂停
- ✅ **暗色主题 MAA 风格 GUI**，高 DPI 适配
- ✅ **实时统计**：运行次数、战斗数、层数、运行时间

---

## 系统要求

| 项目 | 要求 |
|---|----|
| 操作系统 | Windows 10 / 11（仅限 Windows） |
| Python | 3.11 或更高 |
| 游戏 | 卡厄思梦境（Chaos Zero Nightmare）— Steam / 国际服 / 国服 |
| 分辨率 | 1920×1080（推荐，其他分辨率按比例缩放） |
| 权限 | **管理员权限**（全局热键需要） |

---

## 快速开始

### 1. 安装 Python

下载安装 [Python 3.11+](https://www.python.org/downloads/)，安装时勾选 **"Add Python to PATH"**。

### 2. 下载项目

```bash
git clone https://github.com/你的用户名/czn_zero_farm.git
cd czn_zero_farm
```

或者直接下载 ZIP 解压。

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 启动

**方式一：双击运行**

双击 `run.bat`（推荐）。

**方式二：命令行**

```bash
python gui.py
```

> ⚠️ **以管理员身份运行**（否则全局热键 F6/F8/F9 可能无效，但仍可使用界面按钮）。

---

## 使用指南

### 配置说明

打开 GUI → **"配置"** → 各标签页按需调整：

**运行参数**
- `截图间隔`：0.2~1.0 秒，越小检测越快
- `点击后等待`：0.3~1.0 秒，网络延迟高可调大
- `刷取模式`：零式系统 / 赛季图初始刷取

**输入模式**
- `SendInput（前台点击，推荐）`：光标跳转点击后归位
- `SendMessage（后台点击）`：窗口消息，光标不动
- `PostMessage（不碰鼠标）`：完全不碰鼠标

### 运行流程

1. 打开游戏，进入主菜单
2. 启动脚本（F6 或点击"开始"）
3. 脚本自动完成：**主菜单 → 零式系统入口 → 选法典→ 法典合成 → 配队 → 选 Buff→ 选房间 → 战斗 → 结算 → 继续**
4. 随时按 **F8 停止** / **F9 暂停**

### 热键控制

| 热键 | 功能 | 备注 |
|---|----|----|
| **F6** | 开始运行 | 全局热键（需管理员） |
| **F8** | 停止 | 全局热键 |
| **F9** | 暂停 / 继续 | 全局热键 |

---

## 两种刷取模式

### 零式系统（自动刷层）

完整的零式系统自动循环：

```
MAIN_MENU → ZERO_SYSTEM_ENTRY → CODEX_SELECT → CODEX_SYNTH
    → TEAM_ENTER → BUFF_SELECT → event_option2 → ROOM_SELECT → MAP_SCREEN
    → COMBAT → COMBAT_VICTORY → CARD_REWARD → SKIP
    → RESULT_NEXT → MAP_SCREEN → ...（循环刷层）
```

- 房间优先级 GUI 可自定义（默认節火 > 战斗 > 事件 > 精英），Boss 节点/节点保底固定兜底
- 自动开启自动战斗（检测到关闭状态则开启）
- 自动处理各种结算弹窗、奖励弹窗、确认框
- 法典合成：手动扫描按钮模式，直到合成完成
- 事件处理：点最左边位置 2 次
- 结算：手动扫描结算按钮 + 完成标志退出
- Buff 选择：点击区域框 → 手动模式等 event_option2 → 左键 2 次完成
- 死亡后自动提取奖励 → 重新开始

### 赛季图初始刷取（OCR 刷 Buff）

纯 OCR 驱动，三阶段循环：

**Phase 1：入口**
- 全屏 OCR 扫描入口关键词（如 `進入`）
- 支持连续字匹配（解决中文单字拆分）

**Phase 2：Buff 扫描**
- 全屏 OCR 扫描目标 Buff关键词
- 三路兗底匹配：精确词 → 连续字 → 全文子串
- 连续 2 次未匹配 → 退出重进

**Phase 3：退出**
- 按模板匹配退出按钮（脱逃 → 确认）
- 全部退出 → 重置 → 重新 Phase 1

> 刷到目标 Buff后自动停止。
