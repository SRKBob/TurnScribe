"""话轮 TurnScribe · Gradio 本地界面。

启动：
    run.bat                  （推荐，双击即可）
    .venv\\Scripts\\python.exe app.py

服务只监听 127.0.0.1，数据不出本机。切勿开启 share=True。
"""

from __future__ import annotations

import os
import subprocess
import sys
import traceback
from dataclasses import replace
from pathlib import Path

import gradio as gr

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import CONFIG, OUTPUT_DIR, ASRConfig, DiarizeConfig, RenderConfig, ensure_dirs  # noqa: E402
from core.downloader import detect_platform, is_url  # noqa: E402
from core.media import ffmpeg_available  # noqa: E402
from core.pipeline import Pipeline  # noqa: E402
from core.render import fmt_ts  # noqa: E402
from ui_theme import (
    FONTS_DIR,
    base_css,
    gradio_theme,
    load_theme,
    save_theme,
    theme_choices,
    theme_css,
)  # noqa: E402

VIDEO_TYPES = [".mp4", ".mkv", ".mov", ".avi", ".flv", ".webm", ".ts", ".m4v", ".wmv"]
AUDIO_TYPES = [".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"]

if FONTS_DIR.is_dir():
    gr.set_static_paths([FONTS_DIR])  # 内置字体按 /file= 直读磁盘，不进缓存

PLATFORM_NOTE = {
    "bilibili": "B站链接通常可直接解析",
    "douyin": "抖音可能需要浏览器登录态，失败时请改用本地文件",
    "kuaishou": "快手可能需要浏览器登录态",
    "xiaohongshu": "小红书可能需要浏览器登录态",
    "wechat_channels": "视频号可能需要浏览器登录态",
    "youtube": "YouTube 通常可直接解析",
}

_PIPELINE: Pipeline | None = None


def get_pipeline() -> Pipeline:
    """复用同一个 Pipeline 实例，模型只在首次调用时加载。"""
    global _PIPELINE
    if _PIPELINE is None:
        _PIPELINE = Pipeline(CONFIG)
    return _PIPELINE


def env_report() -> str:
    ok_ffmpeg, detail = ffmpeg_available()
    lines = [f"- ffmpeg：{'正常' if ok_ffmpeg else '异常'} — {detail}"]
    try:
        import torch

        if torch.cuda.is_available():
            lines.append(f"- 推理设备：{torch.cuda.get_device_name(0)}")
        else:
            lines.append("- 推理设备：CPU（3 小时素材约需 40-90 分钟，建议使用 GPU）")
    except ImportError:
        lines.append("- 推理设备：未安装 torch")
    return "\n".join(lines)


def open_folder(raw_path: str) -> str:
    """在系统文件管理器里打开输出目录（Windows 用 explorer，其他平台用各自命令）。"""
    target = Path(raw_path).expanduser() if (raw_path or "").strip() else OUTPUT_DIR
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return f"### 无法创建目录\n{target}\n\n{exc}\n"

    try:
        if sys.platform == "win32":
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
    except Exception as exc:  # noqa: BLE001 - 打不开目录不该中断界面
        return f"### 无法打开目录\n{target}\n\n{exc}\n\n请手动复制上面的路径。\n"
    return f"### 已打开目录\n`{target}`\n"


def build_inputs(files: list[str] | None, links: str) -> tuple[list[str], list[str]]:
    sources: list[str] = []
    notes: list[str] = []

    for path in files or []:
        sources.append(path)
        notes.append(f"本地文件：{Path(path).name}")

    for line in (links or "").splitlines():
        url = line.strip()
        if not url:
            continue
        sources.append(url)
        if is_url(url):
            platform = detect_platform(url)
            suffix = PLATFORM_NOTE.get(platform, "未知平台，将尝试用 yt-dlp 解析")
            notes.append(f"链接（{platform}）：{url[:60]}… — {suffix}")
        else:
            notes.append(f"忽略无法识别的一行：{url[:60]}")
    return sources, notes


def run_task(
    files: list[str] | None,
    links: str,
    out_dir: str,
    device: str,
    language: str,
    style: str,
    with_timestamp: bool,
    speaker_stats: bool,
    resume: bool,
    keep_audio: bool,
    threshold: float,
):
    """生成器：边处理边把进度推给界面。"""
    sources, notes = build_inputs(files, links)
    if not sources:
        yield "### 请先上传视频文件或填入视频链接\n", "", [], ""
        return

    cfg = replace(
        CONFIG,
        asr=replace(CONFIG.asr, device=device, language=language),
        diarize=replace(CONFIG.diarize, cluster_threshold=threshold),
        render=replace(
            CONFIG.render,
            style=style,
            with_timestamp=with_timestamp,
            include_speaker_stats=speaker_stats,
        ),
        resume=resume,
        keep_audio=keep_audio,
    )
    global _PIPELINE
    if _PIPELINE is None or _PIPELINE.cfg != cfg:
        _PIPELINE = Pipeline(cfg)
    pipeline = _PIPELINE

    target_dir = Path(out_dir).expanduser() if out_dir.strip() else OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    log = [f"待处理 {len(sources)} 个任务：", *[f"  · {n}" for n in notes], ""]
    outputs: list[str] = []
    preview = ""

    for index, source in enumerate(sources, start=1):
        header = f"[{index}/{len(sources)}] {Path(source).name if not is_url(source) else source}"
        log.append(f"{header} 开始处理")
        yield f"### ⏳ 处理中 {index}/{len(sources)}\n", "\n".join(log), outputs, preview

        def progress(ratio: float, message: str) -> None:
            log.append(f"  {ratio * 100:5.1f}%  {message}")

        try:
            result = pipeline.process(source, out_dir=target_dir, progress=progress)
            outputs.append(str(result.md_path))
            preview = result.md_path.read_text(encoding="utf-8")
            log.append(f"  完成 → {result.md_path.name}（{result.summary}）")
            for warning in result.warnings:
                log.append(f"  注意：{warning}")
        except Exception as exc:  # 单个任务失败不应中断整批
            log.append(f"  失败：{exc}")
            log.append("  " + traceback.format_exc(limit=3).replace("\n", "\n  "))
        log.append("")
        yield f"### ⏳ 已处理 {index}/{len(sources)}\n", "\n".join(log), outputs, preview

    done = len(outputs)
    failed = len(sources) - done
    status = f"### ✅ 完成 {done} 个" + (f"，失败 {failed} 个" if failed else "")
    log.append(status)
    log.append(f"输出目录：{target_dir}")
    yield status + "\n", "\n".join(log), outputs, preview


def build_ui() -> gr.Blocks:
    ensure_dirs()
    initial_theme = load_theme()   # 恢复上次选择的主题（重启 / 刷新不丢）
    # 注意：Gradio 6 起 theme / css 不再由 Blocks() 生效，必须在 launch() 里传。
    with gr.Blocks(title="话轮 TurnScribe") as demo:
        # 换肤变量槽：内容是 <style>，主题变化时由 Python 回调整体替换（无需前端 JS）
        theme_vars = gr.HTML(value=theme_css(initial_theme), elem_classes=["ts-theme-vars"])

        with gr.Row(elem_classes=["ts-head"]):
            gr.HTML(
                '<div class="ts-hero">'
                '<h1>话轮<span class="ts-en">TurnScribe</span></h1>'
                "<p>把视频转成「谁在说」的文稿"
                '<span class="ts-dot">·</span>上传视频或粘贴链接，自动转写为带说话人区分的 Markdown'
                '<span class="ts-dot">·</span>全程本地运行，数据不出本机</p>'
                "</div>"
            )
            # 主题选择器：调色盘图标按钮，点击弹出下拉选项
            theme_picker = gr.Dropdown(
                choices=theme_choices(),
                value=initial_theme,
                show_label=False,
                filterable=False,
                elem_classes=["ts-theme-dd"],
            )

        with gr.Column(elem_classes=["ts-card"]):
            with gr.Row():
                with gr.Column(scale=3):
                    files = gr.File(
                        label="上传视频 / 音频（可多选）",
                        file_count="multiple",
                        file_types=VIDEO_TYPES + AUDIO_TYPES,
                        type="filepath",
                    )
                    links = gr.Textbox(
                        label="视频链接（每行一个）",
                        placeholder="https://www.bilibili.com/video/BV...\nhttps://v.douyin.com/xxxxx/",
                        lines=3,
                    )
                with gr.Column(scale=2):
                    out_dir = gr.Textbox(
                        label="输出目录（可改为任意本地路径，如 D:\\我的文稿）",
                        value=str(OUTPUT_DIR),
                    )
                    open_btn = gr.Button("打开输出目录", size="sm")
                    device = gr.Dropdown(
                        label="推理设备",
                        choices=["auto", "cuda:0", "cpu"],
                        value="auto",
                    )
                    language = gr.Dropdown(
                        label="语言",
                        choices=["auto", "zh", "yue", "en", "ja", "ko"],
                        value="auto",
                    )
                    style = gr.Radio(
                        label="Markdown 样式",
                        choices=[("角色A：内容", "inline"), ("角色名独立成行", "block")],
                        value="inline",
                    )

        with gr.Accordion("高级参数", open=False):
            with gr.Row():
                threshold = gr.Slider(
                    label="说话人聚类阈值（越小越倾向合并为同一人）",
                    minimum=0.30, maximum=0.90, step=0.01, value=0.55,
                )
                with gr.Column():
                    with_timestamp = gr.Checkbox(label="每段标注时间戳", value=True)
                    speaker_stats = gr.Checkbox(label="附各角色发言时长统计", value=False)
                    resume = gr.Checkbox(label="断点续传（复用已有识别结果）", value=True)
                    keep_audio = gr.Checkbox(label="保留抽取的音频文件", value=False)

        run_btn = gr.Button("开始转写", variant="primary", size="lg", elem_classes=["ts-run"])

        status = gr.Markdown("### 就绪\n", elem_classes=["ts-status"])
        with gr.Row():
            with gr.Column(scale=1):
                log_box = gr.Textbox(
                    label="处理日志",
                    lines=16,
                    max_lines=24,
                    autoscroll=True,
                    buttons=["copy"],  # Gradio 6 已移除 show_copy_button
                    elem_classes=["ts-log"],
                )
            with gr.Column(scale=2):
                preview = gr.Markdown(
                    label="转写结果预览",
                    value="_转写完成后，文稿会显示在这里。_",
                    elem_classes=["ts-preview"],
                )
        download = gr.Files(label="下载 Markdown", height=88, elem_classes=["ts-download"])

        with gr.Accordion("环境状态", open=False):
            gr.Markdown(env_report())

        gr.HTML(
            '<div class="ts-foot">'
            "转写由 SenseVoice 自动完成，可能存在识别误差；"
            "角色编号（角色A / 角色B）只表示「不同的人」，不含身份信息。"
            "<br>全部处理在本机完成 · <code>127.0.0.1:7860</code>"
            "</div>"
        )

        run_btn.click(
            fn=run_task,
            inputs=[
                files, links, out_dir, device, language, style,
                with_timestamp, speaker_stats, resume, keep_audio, threshold,
            ],
            outputs=[status, log_box, download, preview],
        )
        open_btn.click(fn=open_folder, inputs=[out_dir], outputs=[status])

        def apply_theme(name: str) -> str:
            """换肤 + 记住选择：重启 / 刷新后由 load_theme() 恢复。"""
            save_theme(name or "")
            return theme_css(name)

        theme_picker.change(
            fn=apply_theme, inputs=[theme_picker], outputs=[theme_vars]
        )

        def sync_theme_on_load():
            """每次页面加载都以后端偏好文件为准。

            picker 初值与 launch(head=) 都是服务器启动时算好的静态值——刷新只是
            重连同一进程，若不在这里重读文件，刷新会回退到「启动那一刻」的主题。
            """
            t = load_theme()
            return t, theme_css(t)

        demo.load(fn=sync_theme_on_load, inputs=None, outputs=[theme_picker, theme_vars])

    return demo


def main() -> None:
    ok, detail = ffmpeg_available()
    if not ok:
        print(f"[警告] {detail}")

    demo = build_ui()
    demo.launch(
        server_name="127.0.0.1",   # 仅本机可访问；改 0.0.0.0 会暴露到局域网
        server_port=7860,
        inbrowser=True,
        show_error=True,
        quiet=False,
        theme=gradio_theme(),
        css=base_css(),
        head=theme_css(load_theme()),   # 首屏即用上次选择的主题，避免闪一下无色
    )


if __name__ == "__main__":
    main()
