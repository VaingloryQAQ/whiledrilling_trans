# app/routes_logpdf.py
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from fastapi.responses import FileResponse
from pathlib import Path
import io, hashlib, json, re
from statistics import mean
import pdfplumber

# ========= 你的工程内模块（相对导入为主，兼容绝对导入） =========
try:
    from .config import DATA_DIR
except Exception:
    DATA_DIR = Path("./data").resolve()

try:
    from .enhanced_well_parser import EnhancedWellParser
except Exception:
    from enhanced_well_parser import EnhancedWellParser  # type: ignore

# ========= 目录 =========
PDF_DIR = (DATA_DIR / "pdfs"); PDF_DIR.mkdir(parents=True, exist_ok=True)
MAP_DIR = (DATA_DIR / "pdf_maps"); MAP_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="", tags=["logpdf"])

# ========= 工具 =========
NUM_RE = re.compile(r"^\d{2,4}$")  # 2~4位整数（10/20… 或 500/2920…）
DEPTH_HEADERS = ("深度", "井深", "DEPTH", "Depth", "MD", "MD:")

def _save_pdf(file: UploadFile) -> tuple[str, Path, bytes]:
    buf: bytes = file.file.read()
    if not buf:
        raise HTTPException(400, "empty file")
    sha = hashlib.sha1(buf).hexdigest()[:16]
    p = PDF_DIR / f"{sha}.pdf"
    p.write_bytes(buf)
    return sha, p, buf

def _pdf_y(page_h: float, top: float) -> float:
    """pdfplumber: top=距上；统一转为 PDF 坐标 y(自下而上)。"""
    return float(page_h - top)

def _fit_linear(pairs: list[tuple[float, float]]) -> tuple[float, float]:
    """最小二乘： y = a*depth + b"""
    n = len(pairs)
    sx = sum(d for _, d in pairs)
    sy = sum(y for y, _ in pairs)
    sxx = sum(d * d for _, d in pairs)
    sxy = sum(y * d for y, d in pairs)
    denom = (n * sxx - sx * sx)
    if denom == 0:
        raise ValueError("degenerate fit")
    a = (n * sxy - sx * sy) / denom
    b = (sy - a * sx) / n
    return a, b

def _R2(pairs: list[tuple[float, float]], a: float, b: float) -> float:
    ys = [y for y, _ in pairs]
    if not ys:
        return 0.0
    ybar = sum(ys) / len(ys)
    ss_tot = sum((y - ybar) ** 2 for y in ys) or 1e-9
    ss_res = sum((y - (a * d + b)) ** 2 for y, d in pairs)
    return 1.0 - ss_res / ss_tot

# ---------- 从 chars 重建“数字串/标题串” ----------
def _chars_to_tokens(chars: list[dict], *, expect_digits: bool, page_h: float,
                     line_tol: float = 2.5, gap_tol: float = 10.0):
    """
    把单字符 chars 重组为 token：
      - 若 expect_digits=True：仅拼接 '0-9'，生成数字 token（text 为 '2800' 等）
      - 否则：拼接 A-Za-z0-9:/（）等，生成标题 token（'MD:'、'DEPTH'、'井深'、'深度'）
    返回 list[dict]: {text, x0, x1, top, bottom, y_pdf}
    """
    def ok_char(ch: str):
        if expect_digits:
            return ch.isdigit()
        # 标题：中英混排，常见符号一起接受
        return bool(re.match(r"[A-Za-z0-9:/：()\u4e00-\u9fa5]", ch))

    # 按 top 分行，再按 x 连续拼接
    items = []
    # 先按 top 归并到“行”
    lines = []
    for c in chars:
        t = c.get("text") or ""
        if not t or (expect_digits and not t.isdigit()) or (not expect_digits and not ok_char(t)):
            continue
        top = float(c["top"]); x0 = float(c["x0"]); x1 = float(c["x1"])
        # 插入到相近的行
        placed = False
        for line in lines:
            if abs(line["top"] - top) <= line_tol:
                line["chars"].append((x0, x1, top, t))
                placed = True
                break
        if not placed:
            lines.append({"top": top, "chars": [(x0, x1, top, t)]})

    # 每行内按 x0 排序并拼接
    for line in lines:
        line["chars"].sort(key=lambda z: z[0])
        buf = []
        for (x0, x1, top, t) in line["chars"]:
            if not buf:
                buf = [(x0, x1, top, t)]
                continue
            px0, px1, ptop, pt = buf[-1]
            # 与上一个字符是否“相连”
            if x0 - px1 <= gap_tol:
                buf[-1] = (px0, x1, top, pt + t)
            else:
                # 先推送上一个
                text = buf[-1][3]
                items.append({
                    "text": text, "x0": buf[-1][0], "x1": buf[-1][1],
                    "top": buf[-1][2], "bottom": buf[-1][2], "y_pdf": _pdf_y(page_h, buf[-1][2])
                })
                buf = [(x0, x1, top, t)]
        if buf:
            text = buf[-1][3]
            items.append({
                "text": text, "x0": buf[-1][0], "x1": buf[-1][1],
                "top": buf[-1][2], "bottom": buf[-1][2], "y_pdf": _pdf_y(page_h, buf[-1][2])
            })

    # 只保留合规 token
    out = []
    for it in items:
        txt = it["text"].strip()
        if expect_digits:
            if NUM_RE.match(txt):
                out.append(it)
        else:
            # 标题匹配更宽松一些，统一大写后比对关键字
            tU = txt.upper().replace("：",":")
            if any(h in tU for h in ("DEPTH","井深","深度","MD")):
                out.append(it)
    return out

def _find_depth_bands_by_chars(chars: list[dict], page_w: float, page_h: float):
    """
    仅用 chars 寻找“深度/井深/DEPTH/MD(:)” 标题，返回若干 band: {x0,x1,y,score}
    """
    title_tokens = _chars_to_tokens(chars, expect_digits=False, page_h=page_h, line_tol=3.0, gap_tol=6.0)
    bands = []
    for t in title_tokens:
        textU = t["text"].upper().replace("：",":")
        if any(k in textU for k in ("DEPTH","井深","深度","MD")):
            x0, x1 = float(t["x0"]), float(t["x1"])
            bands.append({
                "x0": x0 - 12.0,
                "x1": x1 + 80.0,  # 给足右侧余量
                "y": t["y_pdf"],
                "score": 1.0 if any(k in textU for k in ("井深","深度","DEPTH")) else 0.9
            })
    return bands

def _unfold_pairs_from_tokens(tokens: list[dict], page_h: float):
    """
    输入数字 token：[{text:'2800', x0, x1, top, y_pdf}...]（已是 2~4 位纯数字）
    规则：>=3位数字作为锚点；2位(10/20/…) 用当前百位展开，遇回跳则进位。
    输出：[(y_pdf, depth)]
    """
    items = sorted(tokens, key=lambda t: -t["y_pdf"])  # 从上到下
    pairs = []
    cur_base = None
    last_depth = None
    for it in items:
        t = it["text"]; y = it["y_pdf"]
        v = int(t)
        if len(t) >= 3:
            d = float(v)
            cur_base = (v // 100) * 100
            last_depth = d
            pairs.append((y, d))
        else:
            if cur_base is None:  # 没有锚点就跳过
                continue
            d = float(cur_base + v)
            if last_depth is not None and d < last_depth - 30:
                cur_base += 100
                d = float(cur_base + v)
            last_depth = d
            pairs.append((y, d))
    # y 去重
    out = []
    last_y = None
    for y, d in pairs:
        if last_y is None or abs(y - last_y) > 2.0:
            out.append((y, d)); last_y = y
    return out

def _depth_map_by_text(pdf_bytes: bytes):
    """
    新策略（仅文本法、不用 OCR）：
      A) 先用 chars 重建“标题串”和“数字串”，以“DEPTH/MD/深度/井深”为锚定；
      B) 只在锚定 band 内做候选；若无标题则退回“全页 x 聚类”；
      C) 用 >=3位数字为锚 + 2位展开，拟合 y=a*d+b；
      D) 过滤：a<0、跨度>=60、R²>=0.97；评分：R² + 跨度 + anchored 加分 + 距 band 中心近加分；
    返回：depth_map, pages_meta, strategy_info
    """
    depth_map: list[dict] = []
    pages_meta: list[dict] = []
    strategy_pages: list[dict] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            page_h, page_w = float(page.height), float(page.width)
            pages_meta.append({"index": i, "width_pt": page_w, "height_pt": page_h})

            chars = page.chars or []
            if not chars:
                strategy_pages.append({"page": i, "method":"none", "note":"no_chars"}); continue

            # A) 标题锚定
            bands = _find_depth_bands_by_chars(chars, page_w, page_h)  # 可能为空
            # B) 全量数字 token（2~4位）
            digit_tokens = _chars_to_tokens(chars, expect_digits=True, page_h=page_h, line_tol=2.5, gap_tol=8.0)

            # 预先按 x 聚类（所有数字 token）
            buckets: dict[int, list[dict]] = {}
            for t in digit_tokens:
                k = int(round(float(t["x0"]) / 8.0))
                buckets.setdefault(k, []).append(t)
            # 候选列：优先 band 内的桶，否则全桶
            candidates: list[tuple[str, dict|None, int, list[dict]]] = []
            if bands:
                for band in bands:
                    x0, x1 = band["x0"], band["x1"]
                    for k, items in buckets.items():
                        xs = [float(it["x0"]) for it in items]
                        if not xs: continue
                        x_mean = sum(xs) / len(xs)
                        if x0 <= x_mean <= x1:
                            candidates.append(("anchored", band, k, items))
            if not candidates:
                for k, items in buckets.items():
                    if items: candidates.append(("cluster", None, k, items))

            # C) 拟合并打分
            best = None
            for how, band, k, items in candidates:
                pairs = _unfold_pairs_from_tokens(items, page_h)
                if len(pairs) < 4:  # 点太少
                    continue
                try:
                    a, b = _fit_linear(pairs)
                except Exception:
                    continue
                dmin = min(d for _, d in pairs); dmax = max(d for _, d in pairs)
                span = dmax - dmin
                r2 = _R2(pairs, a, b)
                xs = [float(it["x0"]) for it in items]; x_mean = sum(xs)/len(xs)

                # 质量门限（稍放宽跨度与R²，兼顾 8pt 数字噪声）
                if not (a < 0 and span >= 60 and r2 >= 0.97):
                    continue

                score = r2 + min(span/1000.0, 0.35) + (0.2 if how=="anchored" else 0.0)
                if band:
                    cx = (band["x0"] + band["x1"]) / 2.0
                    score += max(0.0, 0.12 - abs(x_mean - cx)/page_w)   # 距 band 中心越近越好

                if not best or score > best["score"]:
                    best = {
                        "score": score, "a": a, "b": b,
                        "dmin": dmin, "dmax": dmax,
                        "how": how, "band": band, "x_mean": x_mean, "r2": r2, "span": span
                    }

            if best:
                depth_map.append({
                    "page": i, "a": best["a"], "b": best["b"], "unit":"pt",
                    "depth_min": float(best["dmin"]), "depth_max": float(best["dmax"])
                })
                strategy_pages.append({
                    "page": i, "method": best["how"],
                    "r2": round(best["r2"], 6), "span": round(best["span"], 2),
                    "x_mean": round(best["x_mean"], 2),
                    "band": best["band"], "a": best["a"], "b": best["b"]
                })
            else:
                strategy_pages.append({"page": i, "method":"none", "r2": None, "span": None, "x_mean": None, "band": bands[:1] if bands else None})

    strategy_info = {
        "message": f"文本法完成：{len(depth_map)}/{len(pages_meta)} 页建立映射",
        "coverage": len(depth_map),
        "pages": strategy_pages
    }
    return depth_map, pages_meta, strategy_info

# ========= 路由：上传并解析 =========
@router.post("/api/logpdf/ingest")
async def ingest_log_pdf(file: UploadFile = File(...)):
    """
    1) 保存 PDF
    2) 文件名解析井号
    3) 文本法建立各页 y=a*d+b 映射（chars→数字串；DEPTH/MD/深度/井深 锚定；无锚定回退聚类）
    """
    sha, pdf_path, buf = _save_pdf(file)

    parser = EnhancedWellParser()
    well, conf, _ = parser.parse_well_name(file.filename or pdf_path.name)
    well = (well or "").strip()
    if well.endswith("井"):
        well = well[:-1]

    depth_map, pages_meta, strategy_info = _depth_map_by_text(buf)
    pages_total = len(pages_meta)
    covered = {d["page"] for d in depth_map}
    missing_pages = [p for p in range(pages_total) if p not in covered]

    (MAP_DIR / f"{sha}.json").write_text(json.dumps(depth_map, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "pdf_id": sha,
        "well": well,
        "confidence": conf,
        "file_url": f"/api/logpdf/{sha}.pdf",
        "pages_meta": pages_meta,
        "depth_map": depth_map,
        "missing_pages": missing_pages,
        "strategy_info": strategy_info
    }

# ========= 路由：PDF 获取 =========
@router.get("/api/logpdf/{pdf_id}.pdf")
def get_pdf(pdf_id: str):
    p = PDF_DIR / f"{pdf_id}.pdf"
    if not p.exists():
        raise HTTPException(404, "not found")
    return FileResponse(p, media_type="application/pdf")

# ========= 路由：两点标定 =========
@router.post("/api/logpdf/calibrate")
def calibrate_log_pdf(payload: dict = Body(...)):
    """
    payload = {
      "pdf_id": "xxxx",
      "page": 3,
      "pairs": [
        {"y_pdf": 123.4, "depth": 550.0},
        {"y_pdf": 20.1,  "depth": 650.0}
      ]
    }
    """
    pdf_id = payload.get("pdf_id")
    page = payload.get("page")
    pairs = payload.get("pairs") or []
    if not pdf_id or page is None or len(pairs) < 2:
        raise HTTPException(400, "invalid payload")

    pts = [(float(p["y_pdf"]), float(p["depth"])) for p in pairs]
    a, b = _fit_linear(pts)
    dmin = min(d for _, d in pts); dmax = max(d for _, d in pts)

    mp = MAP_DIR / f"{pdf_id}.json"
    existing: list[dict] = []
    if mp.exists():
        try: existing = json.loads(mp.read_text(encoding="utf-8"))
        except Exception: existing = []

    updated = False
    for d in existing:
        if int(d.get("page")) == int(page):
            d.update({"a": a, "b": b, "unit": "pt", "depth_min": float(dmin), "depth_max": float(dmax)})
            updated = True
            break
    if not updated:
        existing.append({"page": int(page), "a": a, "b": b, "unit": "pt",
                         "depth_min": float(dmin), "depth_max": float(dmax)})

    existing.sort(key=lambda x: x["page"])
    mp.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "pdf_id": pdf_id, "page": int(page),
        "a": a, "b": b, "unit": "pt",
        "depth_min": float(dmin), "depth_max": float(dmax),
        "depth_map": existing
    }
