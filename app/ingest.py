"""图像数据导入（无缩略图版，配合 /preview 动态缩放）

功能概述：
- 遍历解压后的目录，筛选图片文件
- 计算文件 MD5 作为去重标识（可用于后续校验）
- 解析图片路径/名称以提取元数据（井名、深度、样品类型等）
- 依据规则对图片进行分类并记录异常说明
- 不再生成缩略图（thumb_path 恒为 None），前端改用 /preview 动态缩放
- 批量写入 SQLite 并产出导入统计报告（启用 WAL / 批量提交，速度更快）

命令行：
- `--zip` 解压并导入
- `--dir` 直接导入目录
- 默认遍历解压根目录下的所有子目录
"""

"""图像数据导入（无缩略图版，配合 /preview 动态缩放）
……（原文件头注释可保留）……
"""
import os, zipfile, hashlib, json, time
from pathlib import Path
from typing import Iterable, Optional, List, Dict, Any

from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy import and_

from .config import DATA_DIR, EXTRACTED_DIR, REPORTS_DIR, load_app_config, load_rules
from .models import Image, anomalies_to_str
from .parser import parse_metadata
from .classifier import classify
from .normalizer import Normalizer

DB_PATH = DATA_DIR / "images.db"
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)

def _apply_sqlite_pragmas(sess: Session) -> None:
    try:
        sess.exec("PRAGMA journal_mode=WAL;")
        sess.exec("PRAGMA synchronous=NORMAL;")
        sess.exec("PRAGMA temp_store=MEMORY;")
        sess.exec("PRAGMA mmap_size=268435456;")
    except Exception:
        pass

def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    # ★ 建唯一索引：幂等覆盖靠它更稳（首次创建后会被忽略）
    try:
        with Session(engine) as s:
            s.exec("CREATE UNIQUE INDEX IF NOT EXISTS ux_image_well_rel ON image (well_name, rel_path);")
            s.commit()
    except Exception:
        pass

def compute_md5(path: Path, chunk: int = 1024 * 1024) -> str:
    m = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            m.update(b)
    return m.hexdigest()

def unzip(zip_path: Path, target: Path) -> Path:
    out_dir = target / zip_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(out_dir)
    return out_dir

def is_image_file(p: Path) -> bool:
    return p.suffix.lower() in {".jpg",".jpeg",".png",".bmp",".tif",".tiff",".webp",".gif"}

def walk_files(root: Path) -> Iterable[Path]:
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            p = Path(dirpath) / fn
            if is_image_file(p):
                yield p

def _upsert_image(sess: Session, img: Image) -> None:
    """按 (well_name, rel_path) 幂等覆盖更新。"""
    exist = sess.exec(
        select(Image).where(and_(Image.well_name == img.well_name, Image.rel_path == img.rel_path))
    ).first()
    if exist:
        # 覆盖字段（保留老的 id / created_at）
        exist.file_path = img.file_path
        exist.thumb_path = img.thumb_path
        exist.file_hash = img.file_hash
        exist.sample_type = img.sample_type
        exist.category = img.category
        exist.start_depth = img.start_depth
        exist.end_depth = img.end_depth
        exist.ndepth_center = img.ndepth_center
        exist.anomalies = img.anomalies
        exist.explain = img.explain
        exist.raw_name = img.raw_name
        exist.source_batch = img.source_batch
        exist.ingested_at = img.ingested_at
        sess.add(exist)
    else:
        sess.add(img)

def ingest_dir(folder: Path, source_batch: Optional[str] = None) -> Dict[str, Any]:
    cfg = load_app_config()
    rules = load_rules()
    batch_size = int(cfg.get("batch_size", 500))

    stats = {"total": 0, "ok": 0, "failed": 0, "rejected": 0, "anomalies": {}}
    rows: List[Image] = []
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    folder = folder.resolve()
    extracted_root = EXTRACTED_DIR.resolve()

    with Session(engine) as sess:
        _apply_sqlite_pragmas(sess)

        # 本批次内“看过”的 key，避免同批重复写
        seen_keys: set[tuple[str, str]] = set()

        for fp in walk_files(folder):
            stats["total"] += 1
            try:
                fp_abs = fp.resolve()

                # 仅接收 EXTRACTED_DIR 根下的文件
                rel = str(fp_abs.relative_to(extracted_root))  # 供 preview 用
                rel_unix = rel.replace("\\", "/")

                md5 = compute_md5(fp_abs)

                # 元数据解析（井名/深度/样品类型…）
                meta = parse_metadata(str(fp_abs))
                well = meta.get("well_name")
                st, ed = meta.get("start_depth"), meta.get("end_depth")
                ncenter = (st + ed) / 2 if (st is not None and ed is not None) else None
                sample_type_raw = meta.get("sample_type")
                anomalies = list(meta.get("anomalies") or [])

                # 先跑 classifier 得到“原始类别”
                cat_raw, explain = classify(str(fp_abs), sample_type_raw, rules)

                # ★ 规范化&拒收（与 validate 同步规则）
                st_norm, rej_a = Normalizer.canon_sample_type_full(sample_type_raw, rel_unix)
                cat_norm, rej_b = Normalizer.canon_category(cat_raw, rel_unix)
                if rej_a or rej_b or not cat_norm:
                    stats["rejected"] += 1
                    continue

                key = (well or "", rel_unix)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                img = Image(
                    file_path=str(fp_abs),
                    rel_path=rel_unix,
                    thumb_path=None,          # 不生成缩略图
                    file_hash=md5,
                    well_name=well,
                    sample_type=st_norm,      # ★ 用规范化后的
                    category=cat_norm,        # ★ 用规范化后的
                    start_depth=st,
                    end_depth=ed,
                    ndepth_center=ncenter,
                    anomalies=anomalies_to_str(anomalies),
                    explain=json.dumps(explain, ensure_ascii=False),
                    raw_name=fp_abs.name,
                    source_batch=source_batch or folder.name,
                    ingested_at=now_str,
                )
                rows.append(img)

                if len(rows) >= batch_size:
                    for r in rows:
                        _upsert_image(sess, r)     # ★ 幂等覆盖
                    sess.commit()
                    stats["ok"] += len(rows)
                    rows.clear()

            except Exception as e:
                stats["failed"] += 1
                key = e.__class__.__name__
                stats["anomalies"][key] = stats["anomalies"].get(key, 0) + 1

        if rows:
            for r in rows:
                _upsert_image(sess, r)
            sess.commit()
            stats["ok"] += len(rows)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_json = REPORTS_DIR / f"ingest_{int(time.time())}.json"
    with open(report_json, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    return stats

def main() -> None:
    init_db()
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", type=str)
    ap.add_argument("--dir", type=str)
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    if args.zip:
        z = Path(args.zip)
        out = unzip(z, EXTRACTED_DIR)
        print("解压到:", out)
        print("结果:", ingest_dir(out, source_batch=z.stem))
    elif args.dir:
        d = Path(args.dir)
        print("结果:", ingest_dir(d, source_batch=d.name))
    else:
        for child in EXTRACTED_DIR.iterdir():
            if child.is_dir():
                print("导入:", child)
                print("结果:", ingest_dir(child, source_batch=child.name))

if __name__ == "__main__":
    main()

