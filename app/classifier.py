from typing import Dict, Any, Tuple, Optional
import os
from .normalize import normalize_text

def _contains_all(hay: str, arr) -> bool:
    arr = arr or []
    return all((a.lower() in hay) for a in arr)

def _contains_any(hay: str, arr) -> bool:
    arr = arr or []
    return any((a.lower() in hay) for a in arr) if arr else True

def classify(path: str, sample_type: Optional[str], rules: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    用“子串包含”做规则判断：
      - mode=dir: 只在目录字符串中查找
      - mode=file: 只在文件名字符串中查找
      - image_tokens_any: 总是在文件名字符串中判断（图像类型补充条件）
    """
    norm = normalize_text(path).lower()
    dir_str = normalize_text(os.path.dirname(norm)).lower()
    file_str = normalize_text(os.path.basename(norm)).lower()

    for cat in rules.get("categories", []):
        name = cat.get("name")
        mode = cat.get("mode", "dir")
        require_all = cat.get("require_all", [])
        require_any = cat.get("require_any", [])
        image_any   = cat.get("image_tokens_any", [])
        prefer_dirs_any = cat.get("prefer_dirs_any", [])
        side_view_tokens = cat.get("side_view_tokens", [])

        hay = dir_str if mode == "dir" else file_str

        ok = True
        if require_all and not _contains_all(hay, require_all): ok = False
        if ok and require_any and not _contains_any(hay, require_any): ok = False
        if ok and image_any and not _contains_any(file_str, image_any): ok = False

        if ok:
            explain = {
                "name": name, "mode": mode,
                "require_all_hit": [x for x in (require_all or []) if x.lower() in hay],
                "require_any_hit": [x for x in (require_any or []) if x.lower() in hay],
                "image_tokens_hit": [x for x in (image_any or []) if x.lower() in file_str],
                "prefer_dirs_hit": [x for x in (prefer_dirs_any or []) if x.lower() in dir_str],
                "side_view_hit": [x for x in (side_view_tokens or []) if x.lower() in hay],
                "sample_type": sample_type
            }
            return name, explain

    return None, {"reason": "no_rule_matched"}
