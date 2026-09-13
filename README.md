# 话轮 TurnScribe

> 把视频转成「谁在说」的文稿。

把视频（或音频、或视频链接）转成**带说话人区分的 Markdown 转写稿**。

上传一个 3 分钟的抖音短片，或一条 3 小时的 B站讲座，输出这样一份文档：

```markdown
**角色A** `00:00:01`：hello，大家好，我是小陈。

**角色B** `00:01:36`：这个观点我不太认同，能展开说说吗？
```

全程本地运行，**数据不出本机**，不依赖任何云服务。

## 由来

我想要一个能把 B站链接、抖音链接和本地视频转成文稿的工具。此前我只知道百度网盘有这个能力，但先把视频传上去、再从里面提取文字，这个流程实在有点绕。

于是想到了通义千问团队的 SenseVoiceSmall——它本身就是为语音理解设计的，中文识别够准、模型也小。把它和 VAD 断句、CAM++ 声纹聚类拼起来，正好能做成我想要的东西。

这个项目全程由 WorkBuddy 跑出来，代码能跑通，但各种边界情况我并没有充分把握。遇到问题欢迎提 Issue，我尽量修。

### 关于名字

「**话轮**」是会话分析（Conversation Analysis）里 *turn* 的标准译名，指对话中的一次发言轮次。输出里的每一行 `角色A：…` 就是一个话轮，按时间顺序排下来，就是这份转写稿。

英文名 **TurnScribe** = turn + scribe（记录），和中文名说的是同一件事。取名时刻意避开了 `whosaid`、`diarize`、`voxscribe` 这类已被大量同类项目占用的词，`turnscribe` 目前在 GitHub 上是零撞名。

## 特性

| 能力 | 说明 |
|---|---|
| 多语言识别 | 中文（普通话 / 粤语）、英语、日语、韩语，可自动判语种 |
| 说话人区分 | 自动分出不同说话人，编号为「角色A / 角色B」 |
| 多种输入 | 本地视频、本地音频、视频链接；可批量混合处理 |
| Markdown 输出 | 带时间戳，便于对照原视频回查；可选各角色发言时长统计 |
| 断点续传 | 分段结果增量落盘，长视频中断后不从头重跑 |
| 本地 GUI | Gradio 网页界面，支持拖拽上传、实时进度、结果预览 |
| 命令行入口 | 适合批量脚本化处理，输出目录可自定义 |

## 技术链路

```
输入：本地文件 / 视频链接
  │
  ├─ 链接：yt-dlp 解析并只下载音轨
  ├─ ffmpeg 抽取音轨 → 16kHz 单声道 wav
  ├─ FSMN-VAD 语音端点检测，切出语音段
  ├─ SenseVoiceSmall 逐段识别（+ ct-punc 补标点）
  ├─ CAM++ 提取声纹 → 全局层次聚类 → 说话人编号
  ├─ 按时间轴排序，合并成发言轮次
  └─ 渲染 Markdown
```

模型全部来自 ModelScope 上的 FunASR 生态：`SenseVoiceSmall`（识别）、`fsmn-vad`（断句）、`ct-punc`（标点）、`cam++`（声纹）。

> **为什么不用 funasr 内置的说话人分离组合？** 官方文档标注该组合「未验证分离准确率」，且其滑窗聚类在长音频上簇编号会漂移——3 小时素材容易把一个人拆成好几个角色。本项目改为每段单独提声纹 + 一次性全局聚类，从根上避免漂移。

## 环境要求

| 项目 | 要求 |
|---|---|
| 操作系统 | Windows（`install.bat` / `run.bat` 为 Windows 批处理；其他平台可直接用 Python 命令，见下） |
| Python | **3.10 – 3.13**（本项目在 3.13 上开发验证；3.9 装不上 torch 2.8） |
| ffmpeg | **必须**。需可被找到：加入 PATH，或设环境变量 `FFMPEG_BIN`，或写进 `local_config.py` |
| NVIDIA GPU | 可选，但**强烈建议**（见下表） |
| 磁盘空间 | 约 10 GB（虚拟环境 7 GB + 模型权重 2 GB + 中间产物） |

**有 / 无 GPU 的耗时对比**（实测参考）：

| 素材时长 | GPU（RTX 3050 4GB） | 纯 CPU |
|---|---|---|
| 3 分钟 | 约 1.5 分钟 | 约 3 – 5 分钟 |
| 13 分钟 | 约 3 分钟 | 约 10 – 20 分钟 |
| 3 小时 | 约 5 – 10 分钟 | **约 40 – 90 分钟** |

首次运行需额外 1 – 2 分钟加载模型。

## 使用前请注意

**仓库很小，跑起来不小。**

| 阶段 | 磁盘占用 | 说明 |
|---|---|---|
| 从 GitHub clone | **约 0.1 MB** | 只有源码（25 个文件 / 约 100 KB），下载几乎不占空间 |
| 跑完 `install.bat` | 约 7 GB | 虚拟环境 `.venv`，其中 torch 的 CUDA 库独占约 6.3 GB |
| 首次运行后 | 约 9 GB | 多出约 2 GB 模型权重 |
| 日常使用 | 10 GB 左右 | `temp/` 随处理量增长，可随时清理 |

- **首次运行需联网**：要下载约 2 GB 模型权重，之后可完全离线。
- **处理链接需联网**：本地文件不受影响。
- **缓存与中间文件较多**：全部收在 `temp/` 下，可用 `clean.bat` 分级清理，也可整体删除；单个 3 小时视频的中间产物约几十到几百 MB。
- **模型权重不在项目目录内**：默认下到 `~/.cache/modelscope`（Windows 为 `C:\Users\<用户名>\.cache\modelscope`），删掉本项目不会连带删除它。
- **没有 NVIDIA GPU 能省一大半**：换 CPU 版 torch 可省约 5.5 GB（占用降到约 3.5 GB），代价是长视频慢 8 – 10 倍。替换命令见上文「快速开始」。

请酌情下载。

## 快速开始

### 1. 安装

双击 **`install.bat`**。它会依次完成：

1. 创建虚拟环境 `.venv`
2. 升级 pip
3. 安装 CUDA 12.6 版 torch + torchaudio（约 2.5 GB，走阿里云镜像）
4. 安装其余依赖（funasr / modelscope / gradio / yt-dlp / scipy / soundfile）
5. 运行环境自检

耗时约 10 分钟，主要花在下 torch。

> **没有 NVIDIA GPU？** 把 `install.bat` 第 3 步换成 CPU 版（Windows 上 PyPI 的 torch 本身就是 CPU-only 版本）：
>
> ```bat
> ".venv\Scripts\python.exe" -m pip install torch torchaudio -i https://pypi.tuna.tsinghua.edu.cn/simple
> ```
>
> 能省约 5.5 GB 空间，代价是长视频会慢 8 – 10 倍。

> **Python 不在 PATH？** 设置环境变量 `PYTHON_BIN` 指向 `python.exe` 再运行。

### 2. 启动

双击 **`run.bat`**，浏览器会自动打开 `http://127.0.0.1:7860`。

服务只监听本机回环地址。**不要改成 `0.0.0.0` 或开启 Gradio 的 `share=True`** —— 那会把界面暴露到局域网或公网。

关闭方式：关掉那个黑色命令行窗口（不是关浏览器标签页）。

### 3. 首次运行会自动下载模型

约 2 GB，共 4 个模型，默认下载到：

```
Windows：C:\Users\<用户名>\.cache\modelscope
Linux/macOS：~/.cache/modelscope
```

**第一次必须联网**，之后断网也能跑。

> 想跳过下载：把这台机器上已下载的 `modelscope` 目录整个拷贝到目标机的同名位置即可。

## 使用方式

### GUI

`run.bat` 启动后，界面上可以：

| 控件 | 说明 |
|---|---|
| 上传视频 / 音频 | 支持多选，含 `.mp4 .mkv .mov .avi .flv .webm .ts .m4v .wmv` 与 `.wav .mp3 .m4a .aac .flac .ogg` |
| 视频链接 | 每行一个，可与上传文件混用 |
| 输出目录 | 默认 `output/`，可改成任意本地路径；旁边有「打开输出目录」按钮 |
| 推理设备 | `auto` / `cuda:0` / `cpu` |
| 语言 | `auto` 或指定 `zh / yue / en / ja / ko`，指定后更准 |
| Markdown 样式 | `角色A：内容`（紧凑）或 角色名独立成行（长发言更清晰） |
| 高级参数 | 聚类阈值、时间戳开关、发言时长统计、断点续传、保留音轨 |
| 界面主题 | 右上角调色盘图标，点开下拉选择：秋波蓝 / 竹月青 / 桂黄暖 / WorkBuddy 亮 / WorkBuddy 暗；**选择会被记住，重启后仍生效** |

处理过程中日志实时刷新，右侧同步预览结果，结束后可一键下载。

前三套配色取自中国传统色卡素材，后两套对齐 WorkBuddy 客户端的明暗设计语言。五套全部通过 CSS 变量实现，点调色盘图标即在下拉中切换，不重载页面，也不依赖任何网络字体或外部资源。选择保存在项目根目录的 `.ui_theme.json`（已 gitignore），删除它则恢复默认主题。每套的完整色值、组件样式与派生规则见 [`docs/THEMES.md`](docs/THEMES.md)。

### 命令行

```bat
run_cli.bat "D:\videos\a.mp4" https://www.bilibili.com/video/BVxxxxxxxxxx/ -o "D:\我的文稿"
```

直接调 Python：

```bat
.venv\Scripts\python.exe tools\run.py <本地文件或链接> [更多来源...] [-o 输出目录]
```

常用参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| `-o, --out` | `output/` | 输出目录 |
| `--device` | `auto` | `auto` / `cuda:0` / `cpu` |
| `--language` | `auto` | `auto` / `zh` / `yue` / `en` / `ja` / `ko` |
| `--style` | `inline` | `inline`（角色A：内容）/ `block`（角色名独立成行） |
| `--no-timestamp` | 关闭 | 不输出每段时间戳 |
| `--speaker-stats` | 关闭 | 附加各角色发言时长统计 |
| `--threshold` | `0.55` | 说话人聚类阈值，越小越倾向合并为同一人 |
| `--no-resume` | 关闭 | 忽略缓存，强制重新识别 |
| `--keep-audio` | 关闭 | 保留抽取的音轨 |

## 支持的视频链接

链接下载走一层可插拔的解析层，默认引擎为 [yt-dlp](https://github.com/yt-dlp/yt-dlp)。

| 平台 | 情况 |
|---|---|
| BiliBili | ✅ 稳定，免登录（1080P 以上或付费内容需 Cookie） |
| 抖音 | ⚠️ 通常可用，反爬变动频繁；失败时程序会自动尝试读取本机浏览器的登录态 |
| 快手 / 小红书 / 视频号 | ⚠️ 视平台而定，可能需要登录态 |
| YouTube 等 | ✅ 通常可直接解析 |

链接失效或平台改版时，直接改用本地文件即可，不影响主流程。

下载时**只取音轨**，3 小时视频从几百 MB 降到几十 MB。

> 下载公开视频请遵守对应平台的服务条款与著作权规定。

## 配置

绝大多数参数集中在 `config.py`，GUI 与 CLI 共用同一套默认值。

**本机私有路径**（含用户名的目录）不进版本库，放在 `local_config.py`：

```bat
copy local_config.example.py local_config.py
```

然后编辑 `local_config.py` 填入本机的 ffmpeg 路径。`config.py` 会自动加载它；文件不存在时使用项目内通用默认值。

ffmpeg 的查找顺序：环境变量 `FFMPEG_BIN` → `PATH` → 项目 `bin/` → 常见安装位置 → `local_config.py`。

## 目录结构

```
├── app.py                    Gradio 界面入口
├── ui_theme.py               界面主题与样式（五套配色，含明暗）
├── config.py                 配置中心（所有可调参数）
├── local_config.example.py   本机私有路径模板（复制为 local_config.py 使用）
├── requirements.txt          Python 依赖清单
├── install.bat               一键安装
├── run.bat                   一键启动 GUI
├── run_cli.bat               命令行批量入口
├── clean.bat                 交互式磁盘清理
├── core/                     核心逻辑
│   ├── types.py              数据结构（Segment / Word / Turn）
│   ├── media.py              ffmpeg 抽音轨、时长探测
│   ├── downloader.py         链接解析（可插拔，默认 yt-dlp）
│   ├── asr.py                SenseVoice 封装，标签剥离 + 分段
│   ├── diarize.py            CAM++ 声纹 + 全局层次聚类
│   ├── textutil.py           文本清洗（去标签、压重复标点）
│   ├── render.py             段落合并 + Markdown 渲染
│   └── pipeline.py           流程编排 + 断点续传
├── tools/                    命令行工具
│   ├── run.py                CLI 批量转写
│   ├── check_env.py          环境自检（ffmpeg / torch / GPU / 模型）
│   ├── selftest.py           离线自检（文本清洗、时间戳、聚类、渲染）
│   ├── e2e_test.py           端到端测试（自造两人对话音频跑全链路）
│   ├── uicheck.py            GUI 构建冒烟测试
│   ├── themecheck.py         主题对比度校验（WCAG，离线秒级）
│   └── gen_theme_doc.py      从代码导出 docs/THEMES.md
├── docs/                     文档（THEMES.md 界面设计规范）
├── output/                   转写稿（可从界面改为任意路径）
├── temp/                     临时产物：cache / logs / scratch，可整体删除
└── models/                   预留的模型目录（模型实际缓存在用户目录，见上文）
```

`temp/` 下的一切都是可重建的中间产物，删掉只会导致下次重新计算，不影响正确性。`clean.bat` 提供了分级清理菜单。

## 开发与测试

```bat
rem 语法检查 + 离线自检（秒级，不需要模型和 GPU）
.venv\Scripts\python.exe tools\selftest.py

rem GUI 能否正常构建（列出组件数量）
.venv\Scripts\python.exe tools\uicheck.py

rem 五套主题的对比度校验（WCAG，改配色后必跑）
.venv\Scripts\python.exe tools\themecheck.py

rem 改动配色后刷新设计规范文档
.venv\Scripts\python.exe tools\gen_theme_doc.py

rem 端到端：自动合成一段两人对话音频，跑完整链路
.venv\Scripts\python.exe tools\e2e_test.py

rem 环境自检
.venv\Scripts\python.exe tools\check_env.py
```

## 参数调优

**说话人分得太碎**（一个人被拆成多个角色）：调大 `--threshold`（例如 `0.65`）。

**不同的人被合并成一个角色**：调小 `--threshold`（例如 `0.45`）。

**发现说话人分离的效果不理想**：先确认素材本身是否适合——多人**重叠说话**、远场录音、强背景音乐都会显著降低准确率。单人独白场景下，结果通常最干净。

**长视频（1 小时以上）建议**：保留默认的全局重聚类，不要为了提速关掉，否则容易出现角色编号漂移。

## 常见问题

**提示找不到 ffmpeg**
装一个并加入 PATH，或设环境变量 `FFMPEG_BIN` 指向 `ffmpeg.exe`，或写进 `local_config.py`。

**模型下载卡住**
网络问题。可手动从 ModelScope 下载 `iic/SenseVoiceSmall`、`fsmn-vad`、`ct-punc`、`cam++` 后放到 `~/.cache/modelscope`，或直接拷贝其他机器上已下好的目录。

**首次运行报显存不足**
把 `config.py` 里 `ASRConfig.batch_size_s` 从 `60` 调小（如 `20`），或改用 `--device cpu`。

**识别结果有错别字**
SenseVoice 的同音字误差是固有现象（如「健身房」→「健心房」），无法完全消除。正式用途建议保留时间戳并人工校对。中文素材下，清晰近场录音的准确率明显更高。

**文稿里角色编号是「角色A/B」，想知道具体是谁**
说话人分离输出的是**匿名簇**，只能告诉你「这是不同的人」，不包含身份信息。要对应到真实姓名，需要额外建声纹库比对，或转完后人工标注映射表。

**输出目录可以自定义吗**
可以。GUI 顶部有输出目录输入框，CLI 用 `-o` 参数。默认写到 `output/`。

**支持哪些输入格式**
视频：`mp4 mkv mov avi flv webm ts m4v wmv`；音频：`wav mp3 m4a aac flac ogg`。

## 已知限制

- **说话人分离是估计值**，不是身份识别。重叠说话、口音、远场拾音会掉点。
- **不能做到 100% 准确**，工程上必须保留人工校对环节——所以每段都带时间戳，方便对照原视频。
- **链接下载依赖 yt-dlp**，平台反爬变动会导致偶发失败。
- **本项目为 Windows 优先**。Linux/macOS 下可直接用 Python 命令运行，但 `.bat` 脚本不可用。

## 许可

代码部分采用 **MIT 许可**，完整条款见 [LICENSE](LICENSE)。

模型权重（SenseVoiceSmall / fsmn-vad / ct-punc / cam++）由 ModelScope 分发，各自遵循其模型页面上的开源协议；商用前请查阅对应条款。链接下载功能依赖 yt-dlp，请遵守目标平台的服务条款与著作权规定。

## 致谢

**开源社区。** 本项目站在 FunASR、SenseVoice、CAM++、Gradio、yt-dlp、FFmpeg 的肩膀上。每一个库都让「做产品」这件事变得前所未有地简单；没有这些持续维护的开源项目，这个工具根本不会存在。

**DeepSeek 团队。** 从第一行代码到跑通第一段真实视频，背后是 DeepSeek 模型（V4.1-Flash）在持续推理、写码、查错。感谢他们把高质量的中文模型能力做到便宜、稳、可用，让个人开发者也能把一个念头真正落地成能跑的东西。

**GLM 团队。** 感谢智谱 GLM（GLM-5.3-Flash）承担了本项目日常开发中的大量推理与代码生成工作——响应快、性价比高，让高频迭代的每一步都轻盈。

**WorkBuddy 团队。** 感谢 WorkBuddy 提供了一套真正顺手的编程 Agent 环境——文件读写、命令执行、后台任务、界面预览，整条开发链路都被打磨得足够顺滑。它把「和 AI 一起写代码」从演示变成了日常。
