# app/grouping.py
from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from math import isfinite

from sqlmodel import Session, select

from .models import Image
from .config import load_app_config

CATS_ORDER = ["荧光扫描", "单偏光", "正交光", "三维指纹", "三维立体", "色谱", "轻烃谱图"]


@dataclass
class ImgLite:
    id: int
    rel_path: str
    thumb_path: Optional[str]
    category: Optional[str]
    sample_type: Optional[str]
    start: Optional[float]
    end: Optional[float]
    center: Optional[float]

    @property
    def depth_label(self) -> str:
        if self.start is None or self.end is None:
            return "—"
        if abs(self.start - self.end) < 1e-6:
            return f"{self.start:.2f} m"
        return f"{self.start:.2f}–{self.end:.2f} m"


def _center(img: Image) -> Optional[float]:
    if img.ndepth_center is not None:
        return float(img.ndepth_center)
    if img.start_depth is not None and img.end_depth is not None:
        return float((img.start_depth + img.end_depth) / 2.0)
    return None


def _img_lite(img: Image) -> ImgLite:
    return ImgLite(
        id=int(img.id),
        rel_path=img.rel_path,
        thumb_path=img.thumb_path,
        category=img.category,
        sample_type=img.sample_type,
        start=float(img.start_depth) if img.start_depth is not None else None,
        end=float(img.end_depth) if img.end_depth is not None else None,
        center=_center(img),
    )


def _bucket(x: float, gran: float) -> float:
    # 四舍五入到粒度
    return round(x / gran) * gran


def _valid_depth(img: ImgLite) -> bool:
    return img.start is not None and img.end is not None and img.center is not None and isfinite(img.center)


def _pick_default_well(sess: Session) -> Optional[str]:
    # 选“图片最多”的井名作为默认
    rows = sess.exec(select(Image.well_name)).all()
    counts: Dict[str, int] = {}
    for w in rows:
        if not w:
            continue
        counts[w] = counts.get(w, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]


def build_grouped_data(sess: Session, well: Optional[str]) -> Dict[str, Any]:
    """
    生成“按荧光扫描锚定的深度段 + 各类匹配”的结构（单井）。
    - 若未传 well，自动选“图片最多”的一口井；
    - 匹配容差 = max(全局tol, 段宽/2)；若仍无匹配，回退到“离段中心最近”的一张（阈值 3*gran）。
    """
    cfg = load_app_config()
    gran = float(cfg["depth_group"]["granularity"])
    tol_global = float(cfg["depth_group"]["tolerance"])

    # 1) 锁定井
    if not well:
        well = _pick_default_well(sess)

    q = select(Image).where(Image.well_name == well) if well else select(Image)
    rows: List[Image] = sess.exec(q).all()
    if not rows:
        return {
            "well": well or "",
            "gran": gran,
            "tolerance": tol_global,
            "categories": CATS_ORDER,
            "segments": [],
            "imagesBySegment": {},
        }

    # 2) 轻量化并过滤无深度的
    items: List[ImgLite] = []
    for r in rows:
        il = _img_lite(r)
        if _valid_depth(il):
            items.append(il)

    # 3) 锚：优先荧光；无荧光则全体
    fluo = [x for x in items if x.category == "荧光扫描"]
    anchors_source = fluo if fluo else items

    # 4) 分桶（按粒度）
    buckets: Dict[float, List[ImgLite]] = {}
    for a in anchors_source:
        b = _bucket(a.center, gran)
        buckets.setdefault(b, []).append(a)

    # 5) 构建段 & 匹配
    segments: List[Dict[str, Any]] = []
    imagesBySegment: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    def overlap(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        lo = max(a[0], b[0]); hi = min(a[1], b[1]); return max(0.0, hi - lo)

    def to_dict(img: ImgLite) -> Dict[str, Any]:
        return {
            "id": img.id,
            "thumb_url": f"/thumbs/{img.thumb_path}" if img.thumb_path else None,
            "file_url": f"/files/{img.rel_path}",
            "category": img.category,
            "sample_type": img.sample_type,
            "start_depth": img.start,
            "end_depth": img.end,
            "center": img.center,
            "depth_label": img.depth_label,
        }

    for bucket_center in sorted(buckets.keys()):
        anchor_list = sorted(buckets[bucket_center], key=lambda x: x.center)
        seg_id = f"{(well or '-') }#{bucket_center:.2f}"

        # 段区间：荧光存在 → 用该桶荧光的 [min(start), max(end)]；否则 bucket±gran/2
        if fluo:
            S = min(a.start for a in anchor_list if a.start is not None)
            E = max(a.end for a in anchor_list if a.end is not None)
        else:
            S, E = bucket_center - gran / 2.0, bucket_center + gran / 2.0

        seg_label = f"{S:.2f}–{E:.2f} m"
        # 动态容差：段宽/2 与全局 tol 取大
        tol_dyn = max(tol_global, (E - S) / 2.0)

        # 先按“重叠/中心靠近”匹配；若为空，再做“最近回退”
        cat_map: Dict[str, List[ImgLite]] = {c: [] for c in CATS_ORDER}
        for it in items:
            it_interval = (it.start, it.end)
            seg_interval = (S - tol_dyn, E + tol_dyn)

            ok = False
            if overlap(seg_interval, it_interval) > 0:
                ok = True
            elif abs((it.center or bucket_center) - bucket_center) <= tol_dyn:
                ok = True

            if ok and it.category in cat_map:
                cat_map[it.category].append(it)

        # 回退：为空则取“距离段中心最近”的一张（阈值 3*gran）
        for cat in CATS_ORDER:
            if not cat_map[cat]:
                candidates = [x for x in items if x.category == cat]
                if candidates:
                    best = min(candidates, key=lambda x: abs((x.center or bucket_center) - bucket_center))
                    if abs((best.center or bucket_center) - bucket_center) <= 3 * gran:
                        cat_map[cat] = [best]

        # 序列化：按距段中心从近到远排序
        imagesBySegment[seg_id] = {}
        for cat in CATS_ORDER:
            lst = cat_map.get(cat, [])
            lst_sorted = sorted(lst, key=lambda x: abs((x.center or bucket_center) - bucket_center))
            imagesBySegment[seg_id][cat] = [to_dict(x) for x in lst_sorted]

        anchors_payload = [to_dict(a) for a in anchor_list] if fluo else []

        segments.append({
            "id": seg_id,
            "label": seg_label,
            "center": bucket_center,
            "anchor_options": anchors_payload,
            "counters": {c: len(imagesBySegment[seg_id][c]) for c in CATS_ORDER}
        })

    return {
        "well": well or "",
        "gran": gran,
        "tolerance": tol_global,
        "categories": CATS_ORDER,
        "segments": segments,
        "imagesBySegment": imagesBySegment
    }
