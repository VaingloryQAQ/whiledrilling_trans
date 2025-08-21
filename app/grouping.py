# app/grouping.py
from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from math import isfinite

from sqlmodel import Session, select

from .models import Image
from .config import load_app_config

CATS_ORDER = ["荧光扫描", "单偏光", "正交光", "三维指纹", "三维立体", "色谱谱图", "轻烃谱图", "热解谱图"]


# ---------- 轻量对象 ----------
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


# ---------- 小工具 ----------
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

def _valid_depth(img: ImgLite) -> bool:
    return img.start is not None and img.end is not None and img.center is not None and isfinite(img.center)

def _overlap(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lo = max(a[0], b[0]); hi = min(a[1], b[1]); return max(0.0, hi - lo)

from .normalizer import Normalizer

def canon_sample_type(s: Optional[str]) -> str:
    return Normalizer.canon_sample_type_simple(s)

def path_has_any(s: str, words: List[str]) -> bool:
    if not s: return False
    return any(w in s for w in words)


# ---------- 主函数 ----------
def build_grouped_data(
    sess: Session,
    well: Optional[str],
    sample_type: Optional[str] = None,
    from_depth: Optional[float] = None
) -> Dict[str, Any]:
    """
    生成“按荧光扫描锚定的分段 + 各类匹配”的结构。
    - 锚：优先用荧光扫描，每张荧光图一个分段，直接取其 [start,end]（不规则锚也支持）；
      若无荧光，则退回“粒度分桶”。
    - 匹配池：只使用“看起来就是目标样品类型”的图片（正向匹配 + 黑词排除）；
    - 匹配规则：段扩容 tol = max(全局 tol, 段宽/2)；重叠或中心接近即收；为空则取离段中心最近的一张（阈值 3*gran）。
    """
    cfg = load_app_config()
    gran = float(cfg["depth_group"]["granularity"])
    tol_global = float(cfg["depth_group"]["tolerance"])

    # 1) 选井
    if not well:
        # 选图片最多的井（兜底）
        rows = sess.exec(select(Image.well_name)).all()
        counts: Dict[str, int] = {}
        for w in rows:
            if w: counts[w] = counts.get(w, 0) + 1
        well = max(counts.items(), key=lambda kv: kv[1])[0] if counts else None

    q_base = select(Image).where(Image.well_name == well) if well else select(Image)
    rows_all: List[Image] = sess.exec(q_base).all()
    if not rows_all:
        return {"well": well or "", "gran": gran, "tolerance": tol_global,
                "categories": CATS_ORDER, "segments": [], "imagesBySegment": {}}

    # 2) 轻量化
    all_items: List[ImgLite] = []
    for r in rows_all:
        il = _img_lite(r)
        if _valid_depth(il):
            all_items.append(il)

    # 3) 锚：先取荧光
    fluo = [x for x in all_items if x.category == "荧光扫描"]
    anchors: List[ImgLite] = sorted(fluo, key=lambda x: x.center) if fluo else []

    # 4) 匹配池：正向样品类型判定 + 类别保护
    st = canon_sample_type(sample_type)
    demo_words = ["样例","示例","模板","标准图","谱库","效验","校验","标样","空白"]

    def looks_like_sample(img: ImgLite) -> bool:
        if not st:
            return True
        p = img.rel_path
        val = canon_sample_type(img.sample_type)
        if st == "岩屑":
            if (val == "岩屑") or path_has_any(p, ["岩屑","岩心","岩芯"]):
                if not path_has_any(p, ["泥浆","钻井液"] + demo_words):
                    return True
            return False
        if st == "泥浆":
            return (val == "泥浆") or path_has_any(p, ["泥浆","钻井液"])
        if st == "岩心":
            if (val == "岩心") or path_has_any(p, ["岩心","岩芯"]):
                return not path_has_any(p, ["泥浆","钻井液"])
            return False
        # 其它：简单包含，且排除演示词
        return (val == st) or (st in (p or ""))

    def category_guard(img: ImgLite) -> bool:
        if img.category == "轻烃谱图":
            # 屏蔽热解混入
            if path_has_any(img.rel_path, ["热解","热解分析","热解谱图"]):
                return False
        return True

    items_pool: List[ImgLite] = [x for x in all_items if looks_like_sample(x) and category_guard(x)]

    # 5) 若无荧光，退回粒度分桶做锚
    segments: List[Dict[str, Any]] = []
    imagesBySegment: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

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

    # A) 不规则锚：每张荧光即一个分段
    if anchors:
        # from_depth 过滤（按段中心）
        if from_depth is not None:
            anchors = [a for a in anchors if (a.center is not None and a.center >= from_depth)]

        for a in anchors:
            seg_id = f"{(well or '-') }#{a.center:.2f}"
            S, E = a.start or a.center, a.end or a.center
            if S is None or E is None:  # 理论上不会发生（valid_depth）
                continue
            if S > E: S, E = E, S
            tol = max(tol_global, (E - S) / 2.0)
            seg_interval = (S - tol, E + tol)
            bucket_center = a.center

            # 匹配
            cat_map: Dict[str, List[ImgLite]] = {c: [] for c in CATS_ORDER}
            for it in items_pool:
                if _overlap(seg_interval, (it.start, it.end)) > 0:
                    cat_map[it.category].append(it)
                elif it.center is not None and bucket_center is not None and abs(it.center - bucket_center) <= tol:
                    cat_map[it.category].append(it)

            # 回退：距离段中心最近（阈值 3*gran）
            for cat in CATS_ORDER:
                if not cat_map[cat]:
                    cands = [x for x in items_pool if x.category == cat]
                    if cands:
                        best = min(cands, key=lambda x: abs((x.center or bucket_center) - bucket_center))
                        if abs((best.center or bucket_center) - bucket_center) <= 3 * gran:
                            cat_map[cat] = [best]

            imagesBySegment[seg_id] = {}
            for cat in CATS_ORDER:
                lst = cat_map.get(cat, [])
                lst_sorted = sorted(lst, key=lambda x: abs((x.center or bucket_center) - bucket_center))
                imagesBySegment[seg_id][cat] = [to_dict(x) for x in lst_sorted]

            segments.append({
                "id": seg_id,
                "label": f"{S:.2f}–{E:.2f} m",
                "center": bucket_center,
                "anchor_options": [to_dict(a)],  # 当前锚自身
                "counters": {c: len(imagesBySegment[seg_id][c]) for c in CATS_ORDER}
            })

    # B) 无荧光：退回粒度分桶
    else:
        # 以全集为锚来源
        buckets: Dict[float, List[ImgLite]] = {}
        for it in all_items:
            b = round((it.center or 0.0) / gran) * gran
            buckets.setdefault(b, []).append(it)

        if from_depth is not None:
            buckets = {c: lst for c, lst in buckets.items() if c >= from_depth}

        for c in sorted(buckets.keys()):
            lst = sorted(buckets[c], key=lambda x: x.center or c)
            S = min(a.start for a in lst if a.start is not None)
            E = max(a.end for a in lst if a.end is not None)
            seg_id = f"{(well or '-') }#{c:.2f}"
            tol = max(tol_global, (E - S) / 2.0)
            seg_interval = (S - tol, E + tol)

            cat_map: Dict[str, List[ImgLite]] = {ct: [] for ct in CATS_ORDER}
            for it in items_pool:
                if _overlap(seg_interval, (it.start, it.end)) > 0:
                    cat_map[it.category].append(it)
                elif it.center is not None and abs(it.center - c) <= tol:
                    cat_map[it.category].append(it)

            for cat in CATS_ORDER:
                if not cat_map[cat]:
                    cands = [x for x in items_pool if x.category == cat]
                    if cands:
                        best = min(cands, key=lambda x: abs((x.center or c) - c))
                        if abs((best.center or c) - c) <= 3 * gran:
                            cat_map[cat] = [best]

            imagesBySegment[seg_id] = {}
            for cat in CATS_ORDER:
                lst2 = sorted(cat_map.get(cat, []), key=lambda x: abs((x.center or c) - c))
                imagesBySegment[seg_id][cat] = [to_dict(x) for x in lst2]

            segments.append({
                "id": seg_id,
                "label": f"{S:.2f}–{E:.2f} m",
                "center": c,
                "anchor_options": [],  # 没有荧光时不提供锚选项
                "counters": {ct: len(imagesBySegment[seg_id][ct]) for ct in CATS_ORDER}
            })

    return {
        "well": well or "",
        "gran": gran,
        "tolerance": tol_global,
        "categories": CATS_ORDER,
        "segments": segments,
        "imagesBySegment": imagesBySegment
    }
