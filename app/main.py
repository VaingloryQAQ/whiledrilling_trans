from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import Request, UploadFile, File, Query, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse

import unicodedata
from typing import Tuple

from sqlmodel import Session, select, create_engine
from sqlalchemy import or_, and_, not_

from .config import BASE_DIR, DATA_DIR, UPLOADS_DIR, EXTRACTED_DIR, THUMBS_DIR, load_app_config, load_rules
from .models import Image
from .ingest import init_db, unzip, ingest_dir, DB_PATH
from .grouping import build_grouped_data

import io
import os
import uuid
import shutil
import subprocess
from PIL import Image as PILImage, ImageOps
from starlette.responses import Response
import hashlib, time

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from .extract import extract_archive

app = FastAPI(title="Drill Image Web")
# 简单内存 LRU（按需可换 disk cache）
_PREVIEW_CACHE = {}  # key -> bytes
_PREVIEW_CACHE_MAX = 128


# 静态目录挂载（保留一次即可）
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/files", StaticFiles(directory=EXTRACTED_DIR), name="files")
app.mount("/thumbs", StaticFiles(directory=THUMBS_DIR), name="thumbs")


templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# 数据库初始化
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
init_db()


def get_sess():
    with Session(engine) as sess:
        yield sess


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(BASE_DIR / "static" / "favicon.ico")

@app.get("/", include_in_schema=False)
async def root():
    # 307 保留 POST 方法；这里我们只是 GET 浏览器访问
    return RedirectResponse(url="/upload", status_code=307)




# ================= 内存中的上传任务进度 =================
# 结构：{ job_id: {"status": "pending|extracting|ingesting|recalculating|done|error",
#                 "done": int, "total": int, "current": str, "file": str, "message": str}}
# ========= 进度存储 =========
JOBS: Dict[str, Dict[str, Any]] = {}

def _safe_filename(name: str) -> str:
    name = name.replace("\\", "/").split("/")[-1]
    return "".join(ch for ch in name if ch not in {'\r','\n','\t'})

def _run_cli(module: str, args: List[str]) -> None:
    import os, subprocess
    cmd = [os.sys.executable, "-m", module] + args
    subprocess.run(cmd, check=True)

def _process_upload_job(job_id: str, saved_path: Path) -> None:
    job = JOBS[job_id]
    job.update({"status": "extracting", "done": 0, "total": 0, "current": ""})

    base = saved_path.stem
    out_dir = EXTRACTED_DIR / base
    out_dir.mkdir(parents=True, exist_ok=True)

    def on_progress(done: int, total: int, current_rel: str):
        job.update({"status": "extracting", "done": done, "total": total, "current": current_rel})

    try:
        summary = extract_archive(saved_path, out_dir, on_progress=on_progress)
        job.update({"status": "ingesting", "current": str(out_dir)})
        _run_cli("app.ingest", ["--dir", str(out_dir)])
        job.update({"status": "recalculating"})
        _run_cli("app.recalc", [])
        job.update({
            "status": "done",
            "message": f"OK: {summary.extracted}/{summary.total}, nested={len(summary.nested_archives)}",
            "current": "",
        })
    except subprocess.CalledProcessError as e:
        job.update({"status": "error", "message": f"CLI failed: {e}", "current": ""})
    except Exception as e:
        job.update({"status": "error", "message": f"{type(e).__name__}: {e}", "current": ""})

@app.post("/api/upload")
async def api_upload(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files")
    results = []
    for uf in files:
        job_id = uuid.uuid4().hex
        fname = _safe_filename(uf.filename or f"upload-{job_id}.zip")
        dst = UPLOADS_DIR / fname    # ★ 用配置里的 UPLOADS_DIR
        content = await uf.read()
        dst.write_bytes(content)
        JOBS[job_id] = {"status":"pending","done":0,"total":0,"current":"","file":fname,"message":""}
        background_tasks.add_task(_process_upload_job, job_id, dst)
        results.append({"job_id": job_id, "filename": fname})
    return {"jobs": results}

@app.get("/api/upload/status/{job_id}")
def api_upload_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    total = job.get("total") or 0
    done = job.get("done") or 0
    pct = int(done * 100 / total) if total else (100 if job["status"] in {"done","error"} else 0)
    return {"job_id": job_id, "status": job["status"], "done": done, "total": total,
            "percent": pct, "current": job.get("current",""), "file": job.get("file",""),
            "message": job.get("message","")}

# 预览缓存目录
PREVIEW_CACHE_DIR = BASE_DIR / "data" / "cache" / "previews"
PREVIEW_CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _safe_join_under(root: Path, rel: str) -> Path:
    p = (root / rel).resolve()
    root = root.resolve()
    if not str(p).startswith(str(root)):
        raise HTTPException(status_code=400, detail="invalid path")
    return p

def _preview_cache_path(rel: str, max_side: int) -> Path:
    # 缓存也保留目录结构，最后统一存 jpg
    return (PREVIEW_CACHE_DIR / str(max_side) / rel).with_suffix(".jpg")

@app.get("/preview/{max_side}/{rel_path:path}")
def preview_image(max_side: int, rel_path: str):
    """
    动态缩放原图（最长边=max_side），磁盘缓存。
    使用方式：<img src="/preview/256/{{ item.rel_path }}">
    """
    if max_side <= 0 or max_side > 4000:
        raise HTTPException(400, "invalid max_side")

    src = _safe_join_under(EXTRACTED_DIR, rel_path)
    if not src.exists() or not src.is_file():
        raise HTTPException(404, "file not found")

    cache = _preview_cache_path(rel_path, max_side)
    cache.parent.mkdir(parents=True, exist_ok=True)

    # 缓存是否过期：源图更新则重建
    try:
        src_mtime = src.stat().st_mtime_ns
        if cache.exists():
            if cache.stat().st_mtime_ns >= src_mtime:
                # 直接返回缓存
                etag = hashlib.md5(f"{cache.stat().st_mtime_ns}-{cache.stat().st_size}".encode()).hexdigest()
                headers = {
                    "Cache-Control": "public, max-age=2592000",
                    "ETag": etag
                }
                return FileResponse(cache, media_type="image/jpeg", headers=headers)
    except Exception:
        pass

    # 生成并写缓存
    try:
        with PILImage.open(src) as im:
            im = im.convert("RGB")
            w, h = im.size
            if max(w, h) > max_side:
                if w >= h:
                    nh = int(h * max_side / w)
                    nw = max_side
                else:
                    nw = int(w * max_side / h)
                    nh = max_side
                im = im.resize((nw, nh), PILImage.LANCZOS)
            # 保存到缓存（先临时文件后原子替换，避免并发读到半文件）
            tmp = cache.with_suffix(".tmp")
            tmp.parent.mkdir(parents=True, exist_ok=True)
            im.save(tmp, format="JPEG", quality=82, optimize=True)
            tmp.replace(cache)
    except Exception as e:
        raise HTTPException(500, f"preview failed: {e}")

    etag = hashlib.md5(f"{cache.stat().st_mtime_ns}-{cache.stat().st_size}".encode()).hexdigest()
    headers = {
        "Cache-Control": "public, max-age=2592000",
        "ETag": etag
    }
    return FileResponse(cache, media_type="image/jpeg", headers=headers)

@app.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

def _best_preview_format(accept_header: str) -> str:
    a = accept_header or ""
    if "image/avif" in a:
        return "AVIF"
    if "image/webp" in a:
        return "WEBP"
    return "JPEG"

@app.get("/preview/{size}/{path:path}")
def preview_image(size: int, path: str, request: Request):
    """按需生成缩略图，并做强缓存/协商（ETag/Last-Modified/Vary: Accept）"""
    try:
        size = int(size)
    except Exception:
        size = 256
    size = max(64, min(1600, size))

    src = (EXTRACTED_DIR / path).resolve()
    if not src.exists() or EXTRACTED_DIR not in src.parents:
        raise HTTPException(status_code=404, detail="file not found")

    st = src.stat()
    etag = f'W/"{st.st_mtime_ns}-{st.st_size}-{size}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    fmt = _best_preview_format(request.headers.get("accept", ""))
    key = (str(src), st.st_mtime_ns, size, fmt)
    buf = _PREVIEW_CACHE.get(key)

    media_type = "image/jpeg"
    if buf is None:
        with PILImage.open(src) as im:
            im = ImageOps.exif_transpose(im)
            im.thumbnail((size, size), PILImage.LANCZOS)

            out = io.BytesIO()
            if fmt == "AVIF":
                try:
                    im.save(out, "AVIF", quality=50, speed=6)
                    media_type = "image/avif"
                except Exception:
                    # 平台无 AVIF 编码器时降级
                    im.save(out, "WEBP", quality=82, method=6)
                    media_type = "image/webp"
            elif fmt == "WEBP":
                im.save(out, "WEBP", quality=82, method=6)
                media_type = "image/webp"
            else:
                if im.mode in ("RGBA", "LA"):
                    bg = PILImage.new("RGB", im.size, (0, 0, 0))
                    bg.paste(im, mask=im.split()[-1])
                    im = bg
                im.save(out, "JPEG", quality=85, optimize=True, progressive=True)
                media_type = "image/jpeg"
            buf = out.getvalue()

        # very small LRU
        if len(_PREVIEW_CACHE) > _PREVIEW_CACHE_MAX:
            _PREVIEW_CACHE.clear()
        _PREVIEW_CACHE[key] = buf

    headers = {
        "Cache-Control": "public, max-age=31536000, immutable",
        "ETag": etag,
        "Last-Modified": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(st.st_mtime)),
        "Vary": "Accept",
    }
    return Response(content=buf, media_type=media_type, headers=headers)

@app.get("/sw.js", include_in_schema=False)
def sw_file():
    return FileResponse(BASE_DIR / "static" / "sw.js", media_type="application/javascript")

def normalize_well(s: str) -> str:
    """
    统一全/半角，去掉末尾“井”，去空白，再转大写，用于比对。
    例：'BZ8-3S-11井' -> 'BZ8-3S-11'
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s).strip()
    if s.endswith("井"):
        s = s[:-1]
    return s.upper()

def resolve_wells(sess: Session, q: str) -> Tuple[str, list]:
    wells = [w for w in sess.exec(select(Image.well_name).distinct()).all() if w]
    if not q:
        # 没输入就返回全部候选（不设置 resolved）
        return None, sorted(wells)

    qn = normalize_well(q)
    pairs = [(w, normalize_well(w)) for w in wells]

    exact = [w for (w, n) in pairs if n == qn]
    if exact:
        return exact[0], exact  # 唯一/首个精确命中

    prefix = [w for (w, n) in pairs if n.startswith(qn)]
    if prefix:
        # 有多个前缀命中：返回候选，前端让用户选
        return None, sorted(set(prefix))

    contains = [w for (w, n) in pairs if qn in n]
    if contains:
        return None, sorted(set(contains))

    return None, []  # 没匹配

@app.get("/api/wells")
def api_wells(q: str = "", sess: Session = Depends(get_sess)):
    resolved, candidates = resolve_wells(sess, q)
    return {"resolved": resolved, "candidates": candidates}

# 样品类型列表（可按井名过滤）
@app.get("/api/sample-types")
def api_sample_types(
    well: Optional[str] = None,
    sess: Session = Depends(get_sess),
):
    q = select(Image.sample_type).distinct()
    if well:
        q = q.where(Image.well_name == well)
    stypes = [s for s in sess.exec(q).all() if s]
    return {"sample_types": stypes}


@app.get("/gallery", response_class=HTMLResponse)
async def gallery(
    request: Request,
    well: Optional[str] = None,
    category: Optional[str] = None,
    sample_type: Optional[str] = None,
    # 用 str 接收，允许空串
    depth_min: Optional[str] = Query(None),
    depth_max: Optional[str] = Query(None),
    page: int = 1,
    per_page: int = 40,
    sess: Session = Depends(get_sess),
):
    def to_float(x):
        try:
            return float(x) if x not in (None, "", "null", "None") else None
        except Exception:
            return None

    dm = to_float(depth_min)
    dx = to_float(depth_max)

    # —— 构造查询 —— #
    q = select(Image)
    if well:
        q = q.where(Image.well_name.contains(well))
    if category:
        q = q.where(Image.category == category)

    # 首屏也干净：全局黑词排除
    demo_words = ["样例", "示例", "模板", "标准图", "谱库", "效验", "校验", "标样", "参比"]
    q = q.where(not_(or_(*[Image.rel_path.contains(w) for w in demo_words])))

    # 规范化样品类型（错别字/同义词）
    def canon_st(s: Optional[str]) -> Optional[str]:
        mapping = {"岩屽": "岩屑", "岩芯": "岩心", "钻井液": "泥浆", "岩屑岩心": "岩屑"}
        s = (s or "").strip()
        return mapping.get(s, s) or None

    st = canon_st(sample_type)
    if st:
        if st == "岩屑":
            pos = or_(
                Image.sample_type == "岩屑",
                Image.rel_path.contains("岩屑"),
                Image.rel_path.contains("岩心"),
                Image.rel_path.contains("岩芯"),
            )
            neg = or_(Image.rel_path.contains("泥浆"), Image.rel_path.contains("钻井液"))
            q = q.where(and_(pos, not_(neg)))
        elif st == "泥浆":
            pos = or_(
                Image.sample_type == "泥浆",
                Image.rel_path.contains("泥浆"),
                Image.rel_path.contains("钻井液"),
            )
            neg = or_(
                Image.rel_path.contains("岩屑"),
                Image.rel_path.contains("岩心"),
                Image.rel_path.contains("岩芯"),
            )
            q = q.where(and_(pos, not_(neg)))
        elif st == "岩心":
            pos = or_(
                Image.sample_type == "岩心",
                Image.rel_path.contains("岩心"),
                Image.rel_path.contains("岩芯"),
            )
            neg = or_(Image.rel_path.contains("泥浆"), Image.rel_path.contains("钻井液"))
            q = q.where(and_(pos, not_(neg)))
        else:
            q = q.where(or_(Image.sample_type == st, Image.rel_path.contains(st)))

    # 轻烃 → 排除 “热解*”
    if category == "轻烃谱图":
        q = q.where(
            not_(
                or_(
                    Image.rel_path.contains("热解"),
                    Image.rel_path.contains("热解分析"),
                    Image.rel_path.contains("热解谱图"),
                )
            )
        )

    # 深度：允许区间重叠
    if dm is not None:
        q = q.where(Image.end_depth >= dm)
    if dx is not None:
        q = q.where(Image.start_depth <= dx)

    # 稳定排序
    q = q.order_by(Image.well_name, Image.category, Image.start_depth, Image.end_depth, Image.id)

    items_all = sess.exec(q).all()
    total = len(items_all)
    start = max(0, (page - 1) * per_page)
    end = start + per_page
    items = items_all[start:end]

    wells  = [w for w in sess.exec(select(Image.well_name).distinct()).all() if w]
    cats   = [c for c in sess.exec(select(Image.category).distinct()).all() if c]
    stypes = [s for s in sess.exec(select(Image.sample_type).distinct()).all() if s]

    cfg = load_app_config()

    return templates.TemplateResponse(
        "gallery.html",
        {
            "request": request,
            "items": items,
            "wells": wells,
            "cats": cats,
            "stypes": stypes,
            "filters": {
                "well": well or "",
                "category": category or "",
                "sample_type": sample_type or "",
                "depth_min": depth_min or "",
                "depth_max": depth_max or "",
                "page": page,
                "per_page": per_page,
                "total_count": total,
            },
            "cfg": cfg,
        },
    )

# ---------- 新的分组接口 & 页面 ----------

@app.get("/grouped", response_class=HTMLResponse)
async def grouped(request: Request, well: Optional[str] = None):
    """
    页面本身只渲染外框和输入，数据由 /api/grouped-data 提供，并在前端完成交互渲染。
    """
    stypes = [x.get("label") for x in load_rules().get("sample_types", [])]
    return templates.TemplateResponse(
        "grouped.html",
        {"request": request, "well": well or "", "stypes": stypes}
    )

# ==== 分组数据 API（带样品类型 & 起始深度）====
@app.get("/api/grouped-data")
async def api_grouped_data(
    well: Optional[str] = None,
    sample_type: Optional[str] = None,
    from_depth: Optional[float] = Query(None),
    sess: Session = Depends(get_sess),
):
    data = build_grouped_data(sess, well, sample_type, from_depth)
    return JSONResponse(data)