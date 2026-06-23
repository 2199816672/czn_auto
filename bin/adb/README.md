# 内置 ADB

本目录随仓库内置了 Android Platform Tools 的 adb，供 ADB 设备模式使用：

- `adb.exe`
- `AdbWinApi.dll`
- `AdbWinUsbApi.dll`

说明：

- `core/adb/client.py` 的 `adb_path()` 开发态指向项目根的 `bin/adb/adb.exe`，打包态优先用 exe 同目录 `bin/adb/adb.exe`（由 `build.bat` 复制），缺失时兜底使用系统 PATH 上的 `adb`。
- 升级 adb：从 https://developer.android.com/tools/releases/platform-tools 下载后替换本目录这三个文件即可。
