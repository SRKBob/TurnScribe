"""全局配置。所有可调参数集中在此，GUI 与 CLI 共用同一套默认值。"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# 交付物目录：只放最终 Markdown，用户的输出目标默认指向这里
OUTPUT_DIR = ROOT / "output"

# 临时目录：一切中间产物、日志、调试脚本都收在 temp/ 下，可随时整体删除，不影响流程重跑
TEMP_DIR = ROOT / "temp"
CACHE_DIR = TEMP_DIR / "cache"    # 中间产物：抽出的音频、分段 JSON、下载缓存（断点续传靠它）
LOG_DIR = TEMP_DIR / "logs"       # 自检 / 测试 / 调试日志与样例输出
SCRATCH_DIR = TEMP_DIR / "scratch"  # 一次性调试脚本与临时素材

# 模型缓存单独留在根目录：体积大且重新下载昂贵，不应随 temp 清理一起丢掉
MODEL_DIR = ROOT / "models"

def _load_local_ffmpeg_candidates() -> tuple[str, ...]:
    """读取本机私有配置 local_config.py 里的 FFMPEG_CANDIDATES（不进版本库）。

    按文件路径直接加载，不依赖 sys.path，避免从别处导入 config 时静默失效。
    """
    module = _load_local_module()
    if module is None:
        return ()
    return tuple(str(p) for p in getattr(module, "FFMPEG_CANDIDATES", ()))


def _load_local_module() -> object | None:
    path = ROOT / "local_config.py"
    if not path.is_file():
        return None
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("_local_config", path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:  # 本机配置写错不应该阻断主流程
        return None


def _local_attr(name: str, default: str = "") -> str:
    """从 local_config.py 读单个字符串配置，缺省返回 default。"""
    module = _load_local_module()
    if module is None:
        return default
    return str(getattr(module, name, default) or default)


# ffmpeg 搜索顺序：环境变量 FFMPEG_BIN > PATH > 项目 bin/ > 常见安装位置 > 本机私有配置。
# 含用户名的个人目录路径不写在这里（会随仓库公开），一律放 local_config.py。
FFMPEG_CANDIDATES = (
    str(ROOT / "bin" / "ffmpeg.exe"),
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
) + _load_local_ffmpeg_candidates()


def find_ffmpeg() -> str:
    """定位 ffmpeg：环境变量 FFMPEG_BIN > PATH > 本机已知副本。"""
    env = os.environ.get("FFMPEG_BIN")
    if env and Path(env).is_file():
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    for candidate in FFMPEG_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    raise FileNotFoundError(
        "未找到 ffmpeg。请安装后加入 PATH，或设置环境变量 FFMPEG_BIN 指向 ffmpeg.exe"
    )


def ensure_dirs() -> None:
    for d in (OUTPUT_DIR, TEMP_DIR, CACHE_DIR, LOG_DIR, SCRATCH_DIR, MODEL_DIR):
        d.mkdir(parents=True, exist_ok=True)


@dataclass
class ASRConfig:
    """SenseVoiceSmall + VAD + 标点 的识别参数。"""

    device: str = "auto"                 # auto | cuda:0 | cpu
    language: str = "auto"               # auto | zh | yue | en | ja | ko
    use_itn: bool = True                 # 数字/日期归一化："2026年" 而非 "二零二六年"
    batch_size_s: int = 60               # 批处理窗口，显存不足时调小
    max_single_segment_ms: int = 30000   # VAD 单段上限，超过强制切分
    request_punc: bool = True            # 补标点模型 ct-punc
    # VAD 合并：小段拼成最长 merge_length_s 的块，ASR 上下文更好，但可能把两个人拼进同一段，
    # 导致声纹变成"混音"而被聚错。说话人分离优先，故默认关闭。
    merge_vad: bool = False
    merge_length_s: int = 15
    # 官方权重标识（ModelScope）
    asr_model: str = "iic/SenseVoiceSmall"
    vad_model: str = "fsmn-vad"
    punc_model: str = "ct-punc"
    spk_model: str = "cam++"


@dataclass
class DiarizeConfig:
    """说话人分离参数。3 小时长音频必须分窗口提声纹，再做全局重聚类。"""

    window_s: int = 600                  # 声纹提取窗口（秒），过长会漂移
    cluster_threshold: float = 0.55      # 余弦距离阈值，越小越倾向合并同一人
    # 短于此时长的片段不参与聚类：几百毫秒的「对不对？」「嗯」声纹极不可靠，
    # 让它们单独成簇会把一个说话人拆成一堆角色。改为事后归给时间最近的说话人。
    min_segment_ms: int = 1000
    max_speakers: int = 10               # 上限，防止噪声把簇撑爆
    # 小簇吸收：簇内总发言时长低于 min_cluster_ms，或低于最大簇的 min_cluster_ratio，
    # 视为噪声簇，按声纹相似度并入最近的大簇。
    # 判据用「相对比例」为主，这样 13 秒的短片和 3 小时的长片用同一套阈值都成立。
    min_cluster_ms: int = 1500
    min_cluster_ratio: float = 0.08
    merge_gap_ms: int = 1200             # 同一人相邻段落间隔小于此值则合并
    min_turn_ms: int = 800               # 合并后短于此的插话并入上一段


@dataclass
class RenderConfig:
    """Markdown 输出样式。"""

    style: str = "inline"                # inline -> "**角色A**：内容"；block -> 角色名独立成行
    with_timestamp: bool = True          # 每段前缀时间戳，便于回查视频
    paragraph_chars: int = 500           # inline 模式下超长发言按此长度切段，避免大段文字墙
    include_meta: bool = True            # 输出文件头的来源/时长等元信息
    include_speaker_stats: bool = False  # 附各角色发言时长统计


@dataclass
class AppConfig:
    asr: ASRConfig = field(default_factory=ASRConfig)
    diarize: DiarizeConfig = field(default_factory=DiarizeConfig)
    render: RenderConfig = field(default_factory=RenderConfig)
    keep_audio: bool = False             # 处理完是否保留抽取的音频
    resume: bool = True                  # 断点续传：已完成的片段不重跑
    export_md: bool = True               # 导出 Markdown 文稿
    export_srt: bool = True              # 导出 SRT 字幕（与文稿同名）；二者至少选一
    srt_prefix: str = "auto"             # 字幕角色前缀：auto=多人时加 | always | never
    prefer_cc: bool = True               # B站链接优先直读自带 CC 字幕（命中则跳过下载与识别）


CONFIG = AppConfig()

# B站登录态：AI 字幕（ai-zh）必须登录才能拉到，UP 主手传 CC 匿名可见。
# 从环境变量或 local_config.py 的 BILIBILI_SESSDATA 读取（后者已 gitignore）。
BILIBILI_SESSDATA = os.environ.get("BILIBILI_SESSDATA", "").strip() or _local_attr("BILIBILI_SESSDATA")
