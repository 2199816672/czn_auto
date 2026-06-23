# 内置 ADB

把 Android Platform Tools 里的以下文件放到本目录（`bin/adb/`），程序会优先调用此处的 adb：

- `adb.exe`
- `AdbWinApi.dll`
- `AdbWinUsbApi.dll`

下载地址：https://developer.android.com/tools/releases/platform-tools

说明：

- `core/adb/client.py` 的 `adb_path()` 开发态指向项目根的 `bin/adb/adb.exe`，打包态优先用 `sys._MEIPASS`。
- 若本目录缺少 `adb.exe`，会兜底使用系统 PATH 上的 `adb`。
- 这些二进制文件不纳入 git，请自行下载放入。
