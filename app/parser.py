import os
import re
from functools import lru_cache
from typing import Optional, Tuple, Dict, Any

from .normalizer import Normalizer
from app.normalizer import Normalizer
from .config import load_rules

WELL_RE = re.compile(r"(?P<well>[A-Za-z]{1,4}\d+(?:-\d+){0,3}(?:-[A-Za-z0-9]+)?|.+?(?=井))")

def _units_to_m(val: float, unit: Optional[str]) -> float:
    if not unit: return float(val)
    u = unit.lower()
    if u in ("m", "米"): return float(val)
    if u == "cm": return float(val) / 100.0
    if u == "mm": return float(val)
    return float(val)

def _legacy_well(path: str) -> Optional[str]:
    s = Normalizer.normalize_text(path)
    parts = s.split("/")
    for seg in reversed(parts):
        idx = seg.find("井")
        if idx > 0:
            return seg[:idx].strip()
    m = re.search(r"[A-Za-z]{1,4}\d+(?:-\d+){0,3}(?:-[A-Za-z0-9]+)?", s)
    return m.group(0) if m else None

def _legacy_depth_last_segment(name_only: str) -> Tuple[Optional[float], Optional[float]]:
    s = Normalizer.normalize_for_depth(name_only)
    seg = re.sub(r"\.[^.]+$", "", s)
    if "_" in seg:
        seg = seg.rsplit("_", 1)[-1]
    nums = re.findall(r"\d+(?:\.\d+)?", seg)
    if not nums: return None, None
    if len(nums) == 1:
        d = float(nums[0]); return d, d
    start, end = float(nums[0]), float(nums[1])
    if start > end: start, end = end, start
    return start, end

def _determine_sample_type_by_rules(s: str) -> Optional[str]:
    rules = load_rules(); s_low = s.lower()
    for item in rules.get("sample_types", []):
        label = item.get("label")
        for tok in item.get("tokens", []):
            if tok.lower() in s_low:
                return label
    return None

@lru_cache(maxsize=100_000)
def parse_metadata(path: str) -> Dict[str, Any]:
    anomalies = []
    norm = Normalizer.normalize_text(path)
    well = None; start = end = None

    # 先段内找井名，再全局正则
    well = _legacy_well(norm)
    if not well:
        m_w = WELL_RE.search(norm)
        if m_w:
            well = m_w.group("well").strip()
    if not well:
        anomalies.append("缺少井号")

    # 样品类型
    sample_type = _determine_sample_type_by_rules(norm)

    # 深度：仅在“文件名末段”找，优先区间+单位
    s_depth = Normalizer.normalize_for_depth(norm)
    fname = os.path.basename(s_depth)
    last_seg = fname.rsplit("_", 1)[-1]
    last_seg = re.sub(r"\.[^.]+$", "", last_seg)

    m_d = re.search(
        r"(?P<start>\d+(?:\.\d+)?)\s*(?:-|—|~|to)\s*(?P<end>\d+(?:\.\d+)?)\s*(?P<unit>m|米)\b",
        last_seg, flags=re.IGNORECASE
    )
    if not m_d:
        m_d = re.search(r"(?P<start>\d+(?:\.\d+)?)\s*(?P<unit>m|米)\b", last_seg, flags=re.IGNORECASE)

    if m_d:
        start = _units_to_m(float(m_d.group("start")), m_d.group("unit"))
        gend = m_d.groupdict().get("end")
        end = _units_to_m(float(gend), m_d.group("unit")) if gend else start
        if start > end:
            start, end = end, start; anomalies.append("深度顺序已更正")
    else:
        ls, le = _legacy_depth_last_segment(fname); start, end = ls, le
        if start is None or end is None: anomalies.append("缺少深度")

    return {
        "well_name": well,
        "start_depth": start,
        "end_depth": end,
        "sample_type": sample_type,
        "anomalies": anomalies,
    }
def _determine_sample_type_by_rules(s: str) -> Optional[str]:
    rules = load_rules()
    s_low = s.lower()

    # 展平 (label, token) 列表，并按 token 长度降序，保证更具体的词优先
    pairs = []
    for item in rules.get("sample_types", []):
        label = item.get("label")
        for tok in item.get("tokens", []):
            pairs.append((label, tok))
    pairs.sort(key=lambda x: len(x[1]), reverse=True)

    for label, tok in pairs:
        if tok.lower() in s_low:
            return label
    return None
