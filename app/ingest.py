"""图像数据导入与缩略图生成。

功能概述：
- 遍历解压后的目录，筛选图片文件
- 计算文件 MD5 作为去重标识
- 解析图片路径/名称以提取元数据（井名、深度、样品类型等）
- 依据规则对图片进行分类并记录异常说明
- 生成 JPEG 缩略图至统一目录结构
- 批量写入 SQLite 并产出导入统计报告

命令行：
- `--zip` 解压并导入
- `--dir` 直接导入目录
- 默认遍历解压根目录下的所有子目录
"""

import os, zipfile, hashlib, json, time
from pathlib import Path
from typing import Iterable, Optional, List, Dict, Any
from PIL import Image as PILImage
from sqlmodel import SQLModel, create_engine, Session, select
from .config import DATA_DIR, EXTRACTED_DIR, THUMBS_DIR, REPORTS_DIR, load_app_config, load_rules
from .models import Image, anomalies_to_str
from .parser import parse_metadata
from .classifier import classify

DB_PATH = DATA_DIR / "images.db"
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
def init_db():
    """初始化数据库（如表不存在则创建）。"""
    SQLModel.metadata.create_all(engine)
def compute_md5(path: Path, chunk: int = 1024*1024) -> str:
    """分块计算文件 MD5。

    参数：
    - path: 文件路径
    - chunk: 分块大小（字节），默认 1MB
    """
    m = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""): m.update(b)
    return m.hexdigest()
def unzip(zip_path: Path, target: Path) -> Path:
    """将 zip 解压至 `target/zip文件名` 目录并返回输出目录。"""
    out_dir = target / zip_path.stem; out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf: zf.extractall(out_dir)
    return out_dir
def is_image_file(p: Path) -> bool:
    """判断是否为受支持的图片格式。"""
    return p.suffix.lower() in {".jpg",".jpeg",".png",".bmp",".tif",".tiff",".webp",".gif"}
def make_thumb(src: Path, dst_root: Path, max_side: int) -> Optional[Path]:
    """生成 `src` 的 JPEG 缩略图（最长边不超过 `max_side`）。失败返回 None。"""
    rel = src.relative_to(EXTRACTED_DIR); out = dst_root / rel; out = out.with_suffix(".jpg"); out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with PILImage.open(src) as im:
            im.thumbnail((max_side, max_side)); im.convert("RGB").save(out, quality=85)
        return out
    except Exception: return None
def walk_files(root: Path) -> Iterable[Path]:
    """遍历 `root` 下所有受支持的图片文件并逐个返回路径。"""
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            p = Path(dirpath) / fn
            if is_image_file(p): yield p
def ingest_dir(folder: Path, source_batch: Optional[str] = None) -> Dict[str, Any]:
    """导入目录下图片并写入数据库。

    参数：
    - folder: 待导入目录
    - source_batch: 批次名（默认使用目录名）

    返回：
    - 统计信息字典，包括 total/ok/failed 及异常计数
    """
    
    cfg = load_app_config(); rules = load_rules(); max_side = int(cfg.get("thumb_max_side", 512)); batch_size = int(cfg.get("batch_size", 500))
    stats = {"total": 0, "ok": 0, "failed": 0, "anomalies": {}}
    rows: List[Image] = []; now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    with Session(engine) as sess:
        for fp in walk_files(folder):
            stats["total"] += 1; anomalies = []
            try:
                md5 = compute_md5(fp)
                fp_abs = fp.resolve()
                rel = fp_abs.relative_to(EXTRACTED_DIR.resolve())
                thumb = make_thumb(fp_abs, THUMBS_DIR, max_side)
                thumb_rel = thumb.resolve().relative_to(THUMBS_DIR.resolve()) if thumb else None
                meta = parse_metadata(str(fp))
                well = meta["well_name"]; st, ed = meta["start_depth"], meta["end_depth"]
                ncenter = (st + ed)/2 if (st is not None and ed is not None) else None
                sample_type = meta["sample_type"]; anomalies.extend(meta["anomalies"])
                cat, explain = classify(str(fp), sample_type, rules)
                if not cat: anomalies.append("缺少类别")
                img = Image(file_path=str(fp), rel_path=str(rel), thumb_path = str(thumb.resolve().relative_to(THUMBS_DIR.resolve())) if thumb else None,
                            file_hash=md5, well_name=well, sample_type=sample_type, category=cat, start_depth=st, end_depth=ed,
                            ndepth_center=ncenter, anomalies=anomalies_to_str(anomalies), explain=json.dumps(explain, ensure_ascii=False),
                            raw_name=fp.name, source_batch=source_batch or folder.name, ingested_at=now_str)
                rows.append(img)
                if len(rows) >= batch_size:
                    for r in rows: sess.add(r)
                    sess.commit(); stats["ok"] += len(rows); rows.clear()
            except Exception as e:
                stats["failed"] += 1; key = e.__class__.__name__; stats["anomalies"][key] = stats["anomalies"].get(key, 0) + 1
        if rows:
            for r in rows: sess.add(r)
            sess.commit(); stats["ok"] += len(rows)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_json = REPORTS_DIR / f"ingest_{int(time.time())}.json"
    with open(report_json, "w", encoding="utf-8") as f: json.dump(stats, f, ensure_ascii=False, indent=2)
    return stats
def main():
    """命令行入口：支持 zip 导入、目录导入及默认批量导入。"""
    init_db()
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", type=str); ap.add_argument("--dir", type=str); ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    if args.zip:
        z = Path(args.zip); out = unzip(z, EXTRACTED_DIR); print("解压到:", out); print("结果:", ingest_dir(out, source_batch=z.stem))
    elif args.dir:
        d = Path(args.dir); print("结果:", ingest_dir(d, source_batch=d.name))
    else:
        for child in EXTRACTED_DIR.iterdir():
            if child.is_dir(): print("导入:", child); print("结果:", ingest_dir(child, source_batch=child.name))
if __name__ == "__main__": main()