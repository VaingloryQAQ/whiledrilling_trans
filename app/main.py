from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, Request, UploadFile, File, Query, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse

from sqlmodel import Session, select, create_engine

from .config import BASE_DIR, DATA_DIR, UPLOADS_DIR, EXTRACTED_DIR, THUMBS_DIR, load_app_config
from .models import Image
from .ingest import init_db, unzip, ingest_dir, DB_PATH
from .grouping import build_grouped_data


app = FastAPI(title="Drill Image Web")

# 静态目录挂载
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/files", StaticFiles(directory=BASE_DIR / "data" / "extracted"), name="files")
app.mount("/thumbs", StaticFiles(directory=BASE_DIR / "data" / "thumbs"), name="thumbs")

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

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/upload")
async def upload(files: List[UploadFile] = File(...)):
    # Web 上传 ZIP：保存 -> 解压 -> 导入
    for uf in files:
        dest = UPLOADS_DIR / uf.filename
        with dest.open("wb") as f:
            f.write(await uf.read())
        out = unzip(dest, EXTRACTED_DIR)
        ingest_dir(out, source_batch=dest.stem)
    return RedirectResponse(url="/gallery", status_code=303)


@app.get("/gallery", response_class=HTMLResponse)
async def gallery(
    request: Request,
    well: Optional[str] = None,
    category: Optional[str] = None,
    sample_type: Optional[str] = None,
    # 关键：先用 str 接收以允许 ""，再手动转 float
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

    q = select(Image)
    if well:
        q = q.where(Image.well_name.contains(well))
    if category:
        q = q.where(Image.category == category)
    if sample_type:
        q = q.where(Image.sample_type == sample_type)
    if dm is not None:
        q = q.where(Image.start_depth >= dm)
    if dx is not None:
        q = q.where(Image.end_depth <= dx)

    items = sess.exec(q).all()
    total = len(items)
    items = items[(page - 1) * per_page : page * per_page]

    # 你的 SQLModel 版本这里直接返回标量列表，用 .all() 即可
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

@app.get("/api/grouped-data")
async def api_grouped_data(well: Optional[str] = None, sess: Session = Depends(get_sess)):
    data = build_grouped_data(sess, well)
    return JSONResponse(data)

@app.get("/grouped", response_class=HTMLResponse)
async def grouped(request: Request, well: Optional[str] = None):
    """
    页面本身只渲染外框和输入，数据由 /api/grouped-data 提供，并在前端完成交互渲染。
    """
    return templates.TemplateResponse(
        "grouped.html",
        {"request": request, "well": well or ""}
    )


# @app.get("/grouped", response_class=HTMLResponse)
# async def grouped(
#     request: Request,
#     well: Optional[str] = None,
#     sess: Session = Depends(get_sess),
# ):
#     # 列序与前端模板一致
#     cats = ["荧光扫描", "单偏光", "正交光", "三维指纹", "三维立体", "色谱", "轻烃谱图"]

#     q = select(Image)
#     if well:
#         q = q.where(Image.well_name.contains(well))
#     rows = sess.exec(q).all()

#     cfg = load_app_config()
#     gran = float(cfg["depth_group"]["granularity"])
#     # tol = float(cfg["depth_group"]["tolerance"])  # 当前按粒度取整即可

#     grouped_map = {}
#     for img in rows:
#         if img.ndepth_center is None or img.category is None:
#             continue
#         key_depth = round(img.ndepth_center / gran) * gran
#         key = (img.well_name or "-", key_depth)
#         if key not in grouped_map:
#             grouped_map[key] = {c: [] for c in cats}
#         if img.category in grouped_map[key]:
#             grouped_map[key][img.category].append(img)

#     table = []
#     for (w, d), mp in sorted(grouped_map.items(), key=lambda x: ((x[0][0] or ""), x[0][1])):
#         row = {
#             "well": w,
#             "depth": d,
#             "cells": [mp[c][0] if mp[c] else None for c in cats],
#         }
#         table.append(row)

#     return templates.TemplateResponse(
#         "grouped.html",
#         {"request": request, "cats": cats, "table": table, "well": well or ""},
#     )
