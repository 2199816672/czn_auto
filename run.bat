@echo off
chcp 65001 >nul
title CZN Zero Farm - 零式系统自动刷取
cd /d "%~dp0"
echo 安装依赖中（首次运行需要）...
python -m pip install -r requirements.txt >nul 2>&1
python -m core.gui
