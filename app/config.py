"""路径与配置加载工具。

负责：
- 定义工程路径（根、配置、数据、上传、解压、缩略图、报告）
- 确保上述数据目录存在
- 加载应用与规则配置（YAML）
"""

from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
EXTRACTED_DIR = DATA_DIR / "extracted"
THUMBS_DIR = DATA_DIR / "thumbs"
REPORTS_DIR = DATA_DIR / "reports"

# 确保数据相关目录存在
for p in (DATA_DIR, UPLOADS_DIR, EXTRACTED_DIR, THUMBS_DIR, REPORTS_DIR):
    p.mkdir(parents=True, exist_ok=True)


def load_app_config():
    """加载应用配置 `config/app.yaml`。"""
    with open(CONFIG_DIR / "app.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_rules():
    """加载分类与样品类型匹配规则 `config/rules.yaml`。"""
    with open(CONFIG_DIR / "rules.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)