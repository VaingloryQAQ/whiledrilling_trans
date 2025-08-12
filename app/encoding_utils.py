# app/encoding_utils.py
from __future__ import annotations
import re

_CJK_RANGES = [
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
    (0x3400, 0x4DBF),  # CJK Extension A
    (0xF900, 0xFAFF),  # CJK Compatibility Ideographs
    (0x3000, 0x303F),  # CJK Symbols and Punctuation
    (0xFF00, 0xFFEF),  # Halfwidth and Fullwidth Forms
]

def _has_cjk(s: str) -> bool:
    for ch in s:
        cp = ord(ch)
        for a, b in _CJK_RANGES:
            if a <= cp <= b:
                return True
    return False

def _cjk_ratio(s: str) -> float:
    if not s:
        return 0.0
    n = 0
    for ch in s:
        cp = ord(ch)
        for a, b in _CJK_RANGES:
            if a <= cp <= b:
                n += 1
                break
    return n / max(1, len(s))

def fix_zip_name_cp437_to_gb18030(s: str) -> str:
    """
    zipfile 在未设置 UTF-8 标志时会按 CP437 解码为 str。
    这里把它重新编码回 CP437 的 bytes，再用 GB18030 解码，还原中文。
    无法还原则原样返回。
    """
    try:
        raw = s.encode("cp437", errors="strict")
        alt = raw.decode("gb18030", errors="strict")
        # 经验：若候选包含更多中文，且不出现大量控制/绘图符号，则采用
        bad_chars = len(re.findall(r"[\u2500-\u259F\u2260\u2190-\u21FF]", s))
        if _cjk_ratio(alt) >= _cjk_ratio(s) and bad_chars > 0:
            return alt
        # 即使 bad_chars == 0，只要 alt 明显更“中文”，也采用
        if _cjk_ratio(alt) > _cjk_ratio(s):
            return alt
    except Exception:
        pass
    return s

def normalize_zip_name(name: str) -> str:
    # 分段处理（路径中的每个目录名分别修复，避免一次性失败）
    parts = name.replace("\\", "/").split("/")
    fixed = [fix_zip_name_cp437_to_gb18030(p) for p in parts]
    return "/".join(fixed)

def try_decode(b: bytes, encs=("utf-8", "gb18030", "gbk")) -> str:
    for e in encs:
        try:
            return b.decode(e)
        except Exception:
            continue
    return b.decode("latin1", errors="replace")

def looks_mojibake(s: str) -> bool:
    # 很粗的启发式：包含大量 box-drawing/扩展字符，且基本没中文
    return _cjk_ratio(s) < 0.05 and bool(re.search(r"[\u2500-\u259F\u00C0-\u00FF]", s))
