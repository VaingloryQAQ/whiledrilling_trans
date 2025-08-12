# app/classifier.py
from __future__ import annotations
import os
from typing import Dict, Any, List, Optional, Tuple

from .normalizer import Normalizer
from .config import load_rules

def _contains_any(hay: str, needles: List[str]) -> List[str]:
    hit = []
    for t in needles or []:
        if t and t.lower() in hay:
            hit.append(t)
    return hit

def _split_dir_file(path_norm: str) -> Tuple[str, str]:
    # 统一分隔符后拆分
    s = path_norm.replace("\\", "/")
    base = os.path.basename(s)
    dirs = s[: max(0, len(s) - len(base))]
    return dirs, base

def classify(path: str, sample_type: Optional[str], rules: Optional[Dict[str, Any]] = None):
    """
    返回: (category_name or None, explain_dict)
    explain_dict: {
      name, mode, priority, score, require_all_hit, require_any_hit, image_tokens_hit, prefer_dirs_hit,
      side_view_hit, sample_type, excluded_by
    }
    """
    if rules is None:
        rules = load_rules()

    norm = Normalizer.normalize_text(path)  # 全路径（含我们在 validate/ingest 里构造的 zip.stem 前缀）
    dirs_norm, file_norm = _split_dir_file(norm)
    dirs_only = dirs_norm.lower()
    file_only = file_norm.lower()
    full = norm.lower()

    best = None  # (score, priority, idx, rule, detail)

    for idx, rule in enumerate(rules.get("categories", [])):
        name = rule.get("name")
        mode = (rule.get("mode") or "dir").lower()
        priority = int(rule.get("priority") or 0)

        require_all = [t.lower() for t in (rule.get("require_all") or [])]
        require_any = [t.lower() for t in (rule.get("require_any") or [])]
        image_any   = [t.lower() for t in (rule.get("image_tokens_any") or [])]
        prefer_dirs = [t.lower() for t in (rule.get("prefer_dirs_any") or [])]
        side_view   = [t.lower() for t in (rule.get("side_view_tokens") or [])]
        exclude_any = [t.lower() for t in (rule.get("exclude_any") or rule.get("reject_any") or [])]
        sample_sens = [t.lower() for t in (rule.get("sample_sensitive") or [])]

        # 选择作用域
        scope = file_only if mode == "file" else full
        scope_file = file_only
        scope_dirs = dirs_only

        # 排除词：任一命中即排除
        if exclude_any and any(x in scope for x in exclude_any):
            detail = {
                "name": name, "mode": mode, "priority": priority, "score": -1e9,
                "require_all_hit": [], "require_any_hit": [], "image_tokens_hit": [],
                "prefer_dirs_hit": [], "side_view_hit": [], "sample_type": sample_type,
                "excluded_by": [t for t in exclude_any if t in scope],
            }
            continue  # 直接跳过

        # 必要条件：require_all / require_any
        req_all_hit = [t for t in require_all if t in scope]
        if require_all and len(req_all_hit) < len(require_all):
            continue

        req_any_hit = [t for t in require_any if t in scope] if require_any else []
        if require_any and not req_any_hit:
            continue

        # 其他加分项
        img_hit = [t for t in image_any if (t in scope_file or t in scope_dirs)]
        dir_hit = [t for t in prefer_dirs if t in scope_dirs]
        side_hit = [t for t in side_view if t in scope]

        score = 0.0
        score += 2.0 * len(req_all_hit)
        score += 1.0 * len(req_any_hit)
        score += 1.0 * len(img_hit)
        score += 0.5 * len(dir_hit)
        score += 0.2 * len(side_hit)

        # 样品类型偏好（非硬条件）：若声明了 sample_sensitive 且传入 sample_type，
        # 命中则+0.5，否则-0.2（轻微影响，避免误分）
        st = (sample_type or "").lower()
        if sample_sens:
            if st and st in [x.lower() for x in sample_sens]:
                score += 0.5
            elif st:
                score -= 0.2

        detail = {
            "name": name, "mode": mode, "priority": priority, "score": score,
            "require_all_hit": req_all_hit, "require_any_hit": req_any_hit,
            "image_tokens_hit": img_hit, "prefer_dirs_hit": dir_hit,
            "side_view_hit": side_hit, "sample_type": sample_type, "excluded_by": [],
        }

        if best is None or (score, priority, -idx) > (best[0], best[1], best[2]):
            best = (score, priority, -idx, rule, detail)

    if not best or best[0] <= 0:
        return None, {"reason": "no_rule_matched"}

    return best[3]["name"], best[4]
