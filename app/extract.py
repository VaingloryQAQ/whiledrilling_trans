# app/extract.py
from __future__ import annotations
import io
import os
import sys
import shutil
import bz2
import lzma
import gzip
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional, Dict, List, Tuple

from .encoding_utils import normalize_zip_name, try_decode, looks_mojibake

# 可选依赖
try:
    import py7zr  # type: ignore
except Exception:
    py7zr = None

try:
    import rarfile  # type: ignore
except Exception:
    rarfile = None

def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)

SUPPORTED_EXTS = {
    ".zip", ".7z", ".rar",
    ".tar", ".tgz", ".tar.gz",
    ".tbz2", ".tar.bz2",
    ".txz", ".tar.xz",
    ".gz", ".bz2", ".xz",
}

NESTED_EXTS = {
    ".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz",
    ".tgz", ".tbz2", ".txz", ".tar.gz", ".tar.bz2", ".tar.xz"
}

@dataclass
class ExtractSummary:
    src: Path
    out_dir: Path
    total: int = 0
    extracted: int = 0
    skipped_dirs: int = 0
    nested_archives: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

ProgressCb = Callable[[int, int, str], None]  # (done, total, current_relpath)

def _safe_join(root: Path, rel: str) -> Path:
    # 防 ZipSlip：禁止 .. 穿越
    rel = rel.strip().lstrip("/").replace("\\", "/")
    p = (root / rel).resolve()
    root_res = root.resolve()
    if not str(p).startswith(str(root_res)):
        raise ValueError(f"Invalid path outside target: {rel}")
    return p

def _ensure_unique(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    i = 1
    while True:
        cand = parent / f"{stem}({i}){suffix}"
        if not cand.exists():
            return cand
        i += 1

def _percent(done: int, total: int) -> float:
    return (done / total * 100.0) if total else 100.0

def _is_nested_archive(name: str) -> bool:
    low = name.lower()
    return any(low.endswith(ext) for ext in NESTED_EXTS)

def _iter_zip_entries(z: zipfile.ZipFile) -> List[zipfile.ZipInfo]:
    return [zi for zi in z.infolist() if not zi.is_dir()]

def _extract_zip(src: Path, out_dir: Path, cb: Optional[ProgressCb], summary: ExtractSummary):
    with zipfile.ZipFile(src, "r") as z:
        entries = _iter_zip_entries(z)
        summary.total += len(entries)
        done = summary.extracted

        for zi in entries:
            name = zi.filename
            # UTF-8 标志判断
            is_utf8 = bool(zi.flag_bits & 0x800)
            rel = name.replace("\\", "/")
            if not is_utf8:
                rel = normalize_zip_name(rel)

            if _is_nested_archive(rel):
                summary.nested_archives.append(rel)
                # 仍然把文件本体解出来，但不递归处理
            target = _safe_join(out_dir, rel)
            target.parent.mkdir(parents=True, exist_ok=True)

            # 处理同名覆盖
            target = _ensure_unique(target)

            with z.open(zi, "r") as fsrc, open(target, "wb") as fdst:
                shutil.copyfileobj(fsrc, fdst)

            summary.extracted += 1
            done = summary.extracted
            if cb:
                cb(done, summary.total, rel)

def _iter_tar_members(tf: tarfile.TarFile) -> Iterable[tarfile.TarInfo]:
    for m in tf.getmembers():
        if m.isfile():
            yield m

def _tar_open_with_enc(src: Path) -> tarfile.TarFile:
    # 优先 utf-8，其次 gb18030
    try:
        return tarfile.open(src, "r:*", encoding="utf-8", errors="surrogateescape")
    except Exception:
        return tarfile.open(src, "r:*", encoding="gb18030", errors="surrogateescape")

def _extract_tar(src: Path, out_dir: Path, cb: Optional[ProgressCb], summary: ExtractSummary):
    with _tar_open_with_enc(src) as tf:
        members = list(_iter_tar_members(tf))
        summary.total += len(members)
        for m in members:
            rel = m.name.replace("\\", "/")
            # 某些古早 tar，名字可能是 bytes -> 再尝试修复
            if looks_mojibake(rel):
                try:
                    rel = try_decode(rel.encode("latin1"), encs=("utf-8", "gb18030", "gbk"))
                except Exception:
                    pass

            if _is_nested_archive(rel):
                summary.nested_archives.append(rel)

            target = _safe_join(out_dir, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target = _ensure_unique(target)

            fsrc = tf.extractfile(m)
            if fsrc is None:
                continue
            with fsrc, open(target, "wb") as fdst:
                shutil.copyfileobj(fsrc, fdst)

            summary.extracted += 1
            if cb:
                cb(summary.extracted, summary.total, rel)

def _extract_7z(src: Path, out_dir: Path, cb: Optional[ProgressCb], summary: ExtractSummary):
    if py7zr is None:
        raise RuntimeError("py7zr not installed; please `pip install py7zr`")
    with py7zr.SevenZipFile(src, mode="r") as z:
        # 列表
        allinfos = z.list()  # type: ignore
        # 只算文件
        files = [i for i in allinfos if getattr(i, "is_directory", False) is False]
        summary.total += len(files)
        # py7zr 没有逐条回调，拆成单文件提取
        for info in files:
            rel = info.filename.replace("\\", "/")
            if _is_nested_archive(rel):
                summary.nested_archives.append(rel)
            target = _safe_join(out_dir, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target = _ensure_unique(target)
            # 单个提取到内存再写出
            buf = io.BytesIO()
            z.extract(targets=[rel], path=out_dir)  # 会写到 out_dir/rel
            # 上面已经落地了，为了统一唯一名处理，我们如果变名了，需要移动
            real = out_dir / rel
            if real != target and real.exists():
                shutil.move(str(real), str(target))
            summary.extracted += 1
            if cb:
                cb(summary.extracted, summary.total, rel)

def _extract_rar(src: Path, out_dir: Path, cb: Optional[ProgressCb], summary: ExtractSummary):
    if rarfile is None:
        # 尝试 unar 兜底
        unar = _which("unar")
        if not unar:
            raise RuntimeError("rarfile not installed and `unar` not found; install one of them to support RAR.")
        # 使用 unar：不递归，输出到 out_dir/档名
        base = src.stem
        tmp_out = out_dir
        # -force-overwrite=false，避免覆盖；编码让 unar 自解
        import subprocess
        cmd = [unar, "-o", str(tmp_out), "-q", str(src)]
        subprocess.check_call(cmd)
        # 无法逐条回调，只能在完成后扫描计数
        return

    with rarfile.RarFile(src) as rf:
        infos = [i for i in rf.infolist() if not i.isdir()]
        summary.total += len(infos)
        for info in infos:
            rel = info.filename.replace("\\", "/")
            if looks_mojibake(rel):
                try:
                    rel = try_decode(rel.encode("cp437"), encs=("gb18030","gbk","utf-8"))
                except Exception:
                    pass
            if _is_nested_archive(rel):
                summary.nested_archives.append(rel)

            target = _safe_join(out_dir, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target = _ensure_unique(target)

            with rf.open(info) as fsrc, open(target, "wb") as fdst:
                shutil.copyfileobj(fsrc, fdst)

            summary.extracted += 1
            if cb:
                cb(summary.extracted, summary.total, rel)

def _extract_single_stream(src: Path, out_dir: Path, cb: Optional[ProgressCb], summary: ExtractSummary):
    """
    处理 .gz/.bz2/.xz 这类单文件流：输出为去掉扩展名的同名文件。
    """
    opener = None
    if src.suffix.lower() == ".gz":
        opener = gzip.open
    elif src.suffix.lower() == ".bz2":
        opener = bz2.open
    elif src.suffix.lower() == ".xz":
        opener = lzma.open
    else:
        raise RuntimeError(f"Unsupported single-stream type: {src}")
    # 目标名
    out_name = src.name[: -len(src.suffix)]
    target = _safe_join(out_dir, out_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target = _ensure_unique(target)

    summary.total += 1
    with opener(src, "rb") as fsrc, open(target, "wb") as fdst:
        shutil.copyfileobj(fsrc, fdst)
    summary.extracted += 1
    if cb:
        cb(summary.extracted, summary.total, out_name)

def extract_archive(
    src: Path | str,
    out_dir: Path | str,
    on_progress: Optional[ProgressCb] = None,
) -> ExtractSummary:
    """
    解压一个压缩包到 out_dir/（不会创建额外的顶层目录）
    - 自动修复常见中文乱码（尤其 ZIP 的 GBK/GB18030）
    - 支持进度回调：on_progress(done, total, current_relpath)
    - 检测内嵌压缩包并汇报（不递归解）
    """
    src = Path(src)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    low = src.name.lower()

    summary = ExtractSummary(src=src, out_dir=out_dir, total=0, extracted=0)

    if low.endswith(".zip"):
        _extract_zip(src, out_dir, on_progress, summary)
    elif low.endswith((".7z",)):
        _extract_7z(src, out_dir, on_progress, summary)
    elif low.endswith((".rar",)):
        _extract_rar(src, out_dir, on_progress, summary)
    elif low.endswith((".tar", ".tgz", ".tar.gz", ".tbz2", ".tar.bz2", ".txz", ".tar.xz")):
        _extract_tar(src, out_dir, on_progress, summary)
    elif low.endswith((".gz", ".bz2", ".xz")):
        _extract_single_stream(src, out_dir, on_progress, summary)
    else:
        raise RuntimeError(f"Unsupported archive type: {src.suffix}")

    return summary

# ------------------------- CLI -------------------------

def _print_progress(done: int, total: int, name: str):
    width = shutil.get_terminal_size((80, 20)).columns
    bar_w = max(10, min(40, width - 40))
    pct = int((done / total * 100) if total else 100)
    filled = int(bar_w * pct / 100)
    bar = "█" * filled + "·" * (bar_w - filled)
    end = "\r" if done < total else "\n"
    sys.stdout.write(f"[{bar}] {pct:3d}%  {done}/{total}  {name[:max(10, width-30)]}{end}")
    sys.stdout.flush()

def _iter_archives_under(path: Path) -> List[Path]:
    res: List[Path] = []
    for p in path.iterdir():
        if not p.is_file():
            continue
        if any(p.name.lower().endswith(ext) for ext in SUPPORTED_EXTS):
            res.append(p)
    return sorted(res)

def main():
    import argparse, json
    ap = argparse.ArgumentParser(description="Smart extractor with encoding fix & progress")
    ap.add_argument("--src", required=True, help="file or directory (contains archives)")
    ap.add_argument("--out", required=True, help="output dir (extracted here)")
    ap.add_argument("--json", action="store_true", help="print JSON summary")
    args = ap.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    summaries: List[ExtractSummary] = []
    archives: List[Path] = []
    if src.is_file():
        archives = [src]
    else:
        archives = _iter_archives_under(src)

    for i, arc in enumerate(archives, 1):
        print(f"\n==> [{i}/{len(archives)}] {arc.name}")
        try:
            summary = extract_archive(arc, out, on_progress=_print_progress)
            summaries.append(summary)
            if summary.nested_archives:
                print(f"  ⚠️  nested archives found ({len(summary.nested_archives)}):")
                for na in summary.nested_archives[:5]:
                    print(f"     - {na}")
                if len(summary.nested_archives) > 5:
                    print("     ...")
        except Exception as e:
            print(f"  ❌ failed: {e}")
            continue

    if args.json:
        obj = [s.__dict__ for s in summaries]
        print(json.dumps(obj, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
