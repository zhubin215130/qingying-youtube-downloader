# 清影 Qingying

简洁的 Windows 桌面 YouTube 视频下载器。粘贴单个视频或 Shorts 链接后，清影会列出视频实际提供的分辨率；如果提供 1440p，会默认选中。下载时可选择保存位置、查看进度并取消任务，程序会自动合并视频与音频。

## 功能

- 支持普通视频和 Shorts 链接
- 选择视频提供的原生分辨率，不对低分辨率视频进行放大
- 下载进度、取消与断点续传
- 简体中文界面，Windows 10/11（64 位）

## 从源代码运行

使用 Python 3.12 创建虚拟环境并安装依赖：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\main.py
```

读取 YouTube 视频信息需要 Node.js，下载与合并需要 FFmpeg。请从各自的官方渠道取得，并将 `node.exe` 和 `ffmpeg.exe` 放到项目的 `bin` 文件夹。项目未包含这些可执行文件。

## 构建安装程序

1. 完成上述 Python 环境准备。
2. 将 Node.js 22+ 的 `node.exe` 和 FFmpeg 的 `ffmpeg.exe` 放到 `bin` 文件夹。
3. 安装 NSIS 3.13，将 `makensis.exe` 放到 `nsis` 文件夹。
4. 运行 `.\.venv\Scripts\python.exe make_icon.py`，然后运行 `.\build.ps1`。

构建结果位于 `dist\Qingying-Setup-1.0.0.exe`。若需要源代码压缩包，运行 `.\.venv\Scripts\python.exe package_source.py`，结果位于 `dist` 文件夹。

## 项目结构

- `src/core.py`：视频信息、画质选择和下载逻辑
- `src/main.py`：桌面界面
- `assets/`：图标与字体
- `build.ps1`、`installer.nsi`：Windows 打包与安装程序
- `THIRD_PARTY.txt`、`licenses/`：第三方组件信息与许可文本

清影使用 PySide6、yt-dlp、yt-dlp-ejs、Node.js 和 FFmpeg。随源代码提供的 Noto Sans SC 字体遵循 SIL Open Font License 1.1。第三方许可详见 `THIRD_PARTY.txt` 和 `licenses/`。

`--self-test <output.json> <YouTube URL>` 用于验证打包后的程序能否读取视频信息。

