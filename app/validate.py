# app/validate.py
"""
对一批压缩包做“无解压验证”（修复中文名乱码）：
- 遍历 ZIP 条目（不解压）
- 纠正 Windows ZIP 的中文名（CP437 -> GB18030/GBK 兜底）
- 仅挑选图片后缀
- 基于“合成路径”跑 parse_metadata / classify（保证 dir/file 规则都能起效）
- 输出每个压缩包的分类统计、未知/缺深度计数
用法：
  python -m app.validate --root data/new_archives
  python -m app.validate --root data/new_archives --out data/reports/validate_xxx.json
"""
# ……文件头注释保留……
from __future__ import annotations
import argparse, json, time, zipfile, struct
from collections import Counter
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from .config import REPORTS_DIR, load_rules
from .parser import parse_metadata
from .classifier import classify
from .normalizer import Normalizer

IMG_EXTS = (".jpg",".jpeg",".png",".bmp",".tif",".tiff",".webp",".gif")

# …… decode_zip_name 等辅助函数保持不变 ……

def validate_one_zip(zp: Path, rules: Dict[str, Any]) -> Dict[str, Any]:
    imgs_count = 0
    cat_counter: Counter[str] = Counter()
    unknown = 0
    st_missing = 0
    anomalies_total = 0
    rejected = 0  # ★ 统计被规范化拒收的数量

    with zipfile.ZipFile(zp, "r") as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            name = decode_zip_name(info)
            if not name.lower().endswith(IMG_EXTS):
                continue

            imgs_count += 1
            fake_path = synth_path(zp.stem, name)

            meta = parse_metadata(fake_path)
            if meta.get("start_depth") is None or meta.get("end_depth") is None:
                st_missing += 1
            anomalies_total += len(meta.get("anomalies") or [])

            # 先跑旧的分类器
            cat_raw, _exp = classify(fake_path, meta.get("sample_type"), rules)
            # 再按导入的最终规则做规范化/拒收
            st_norm, rej_a = Normalizer.canon_sample_type_full(meta.get("sample_type"), fake_path)
            cat_norm, rej_b = Normalizer.canon_category(cat_raw, fake_path)
            if rej_a or rej_b or not cat_norm:
                rejected += 1
                continue

            cat_counter[cat_norm] += 1

    return {
        "imgs": imgs_count,
        "cat": dict(cat_counter),
        "unknown": unknown,
        "st_missing": st_missing,
        "anomalies": anomalies_total,
        "rejected": rejected,  # ★ 新增
    }
