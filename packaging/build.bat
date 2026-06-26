@echo off
chcp 65001 >nul
title CZN Zero Farm - 打包 EXE
rem 本脚本位于 packaging/，切换到项目根目录执行，产物输出到根目录 dist\
cd /d "%~dp0.."

echo [1/4] 检查并安装 PyInstaller...
python -m PyInstaller --version >nul 2>&1 || python -m pip install pyinstaller

echo [2/4] 清理旧的构建产物...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/4] 开始打包（首次较慢，请耐心等待）...
python -m PyInstaller packaging\czn_auto.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo [错误] 打包失败，请查看上方日志。
    pause
    exit /b 1
)

echo [4/4] 复制配置、模板与内置 adb 到 exe 同目录...
copy /y config.json dist\config.json >nul
xcopy /e /i /y templates dist\templates >nul
if exist bin xcopy /e /i /y bin dist\bin >nul
if not exist dist\logs mkdir dist\logs

echo.
echo ================================================
echo  打包完成！产物位于 dist\ 目录：
echo    dist\CZN_Zero_Farm_v2.3.exe   (主程序)
echo    dist\config.json         (配置，可编辑)
echo    dist\templates\          (模板：国服/国际服/像素规则)
echo    dist\bin\adb\            (内置 adb，ADB 设备模式需要)
echo  分发时请将整个 dist 目录一起拷贝。
echo  注意：脚本依赖管理员权限热键，请右键以管理员身份运行 exe。
echo ================================================
pause
