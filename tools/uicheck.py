"""GUI 冒烟测试：构建界面并打印环境报告，结果写入 temp/logs/_ui.log。

用法：.venv\\Scripts\\python.exe tools\\uicheck.py
不加载模型，秒级完成，用于改完 app.py 后确认界面仍能正常构建。
"""

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import LOG_DIR  # noqa: E402

report = []
try:
    import app

    demo = app.build_ui()
    report.append(f"UI_OK blocks={len(demo.blocks)}")
    report.append(f"env_report={app.env_report()!r}")
except Exception as exc:
    report.append(f"UI_FAIL: {type(exc).__name__}: {exc}")
    report.append(traceback.format_exc())

LOG_DIR.mkdir(parents=True, exist_ok=True)
(LOG_DIR / "_ui.log").write_text("\n".join(report), encoding="utf-8")
print("\n".join(report))
sys.exit(0 if report[0].startswith("UI_OK") else 1)
