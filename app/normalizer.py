# app/normalizer.py
"""
统一的规范化服务类
整合 normalize.py 和 normalization.py 的功能
"""

from __future__ import annotations
import re
from typing import Optional, Tuple

# 从 normalize.py 移植的映射
FULL_TO_HALF = {
    ord('，'): ',',
    ord('。'): '.',
    ord('：'): ':',
    ord('【'): '[',
    ord('】'): ']',
    ord('（'): '(',
    ord('）'): ')',
    ord('％'): '%',
    ord('＋'): '+',
    ord('－'): '-',
    ord('；'): ';',
    ord('、'): ',',
    ord('　'): ' ',   # 全角空格
    ord('Ｍ'): 'M',
    ord('ｍ'): 'm',
    # 添加更多全角字母映射
    ord('Ａ'): 'A', ord('Ｂ'): 'B', ord('Ｃ'): 'C', ord('Ｄ'): 'D', ord('Ｅ'): 'E',
    ord('Ｆ'): 'F', ord('Ｇ'): 'G', ord('Ｈ'): 'H', ord('Ｉ'): 'I', ord('Ｊ'): 'J',
    ord('Ｋ'): 'K', ord('Ｌ'): 'L', ord('Ｍ'): 'M', ord('Ｎ'): 'N', ord('Ｏ'): 'O',
    ord('Ｐ'): 'P', ord('Ｑ'): 'Q', ord('Ｒ'): 'R', ord('Ｓ'): 'S', ord('Ｔ'): 'T',
    ord('Ｕ'): 'U', ord('Ｖ'): 'V', ord('Ｗ'): 'W', ord('Ｘ'): 'X', ord('Ｙ'): 'Y',
    ord('Ｚ'): 'Z',
    ord('ａ'): 'a', ord('ｂ'): 'b', ord('ｃ'): 'c', ord('ｄ'): 'd', ord('ｅ'): 'e',
    ord('ｆ'): 'f', ord('ｇ'): 'g', ord('ｈ'): 'h', ord('ｉ'): 'i', ord('ｊ'): 'j',
    ord('ｋ'): 'k', ord('ｌ'): 'l', ord('ｍ'): 'm', ord('ｎ'): 'n', ord('ｏ'): 'o',
    ord('ｐ'): 'p', ord('ｑ'): 'q', ord('ｒ'): 'r', ord('ｓ'): 's', ord('ｔ'): 't',
    ord('ｕ'): 'u', ord('ｖ'): 'v', ord('ｗ'): 'w', ord('ｘ'): 'x', ord('ｙ'): 'y',
    ord('ｚ'): 'z',
}
# 全角数字 ０-９
FULL_TO_HALF.update({
    ord('０'): '0', ord('１'): '1', ord('２'): '2', ord('３'): '3', ord('４'): '4',
    ord('５'): '5', ord('６'): '6', ord('７'): '7', ord('８'): '8', ord('９'): '9'
})

# 从 normalization.py 移植的词汇
QC_WORDS = ["效验","校验","标样","样例","示例","模板","谱库","标准图","参比"]
MUD_WORDS = ["泥浆","钻井液"]
CORE_WORDS = ["岩心","岩芯"]
CUTTINGS_WORDS = ["岩屑"]
HOTWORDS = ["热解","热解分析","热解谱图"]

class Normalizer:
    """统一的规范化服务类"""
    
    @staticmethod
    def normalize_text(s: str) -> str:
        """文本规范化（从 normalize.py 移植）"""
        if not s:
            return s
        s = s.translate(FULL_TO_HALF)
        s = s.replace("\\", "/")
        s = re.sub(r"[ \t]+", " ", s).strip()
        return s
    
    @staticmethod
    def normalize_for_depth(s: str) -> str:
        """深度专用规范化（从 normalize.py 移植）"""
        s = Normalizer.normalize_text(s)
        s = re.sub(r"(—|~|\\bto\\b)", "-", s, flags=re.IGNORECASE)
        s = re.sub(r"(?<=\\d),(?=\\d{3}\\b)", "", s)
        s = re.sub(r"(?<=\\d),(?=\\d+\\b)", ".", s)

        s = re.sub(r"m[)\\].,]*\\b", "m", s, flags=re.IGNORECASE)
        return s
    
    @staticmethod
    def tokenize_path(path: str):
        """路径分词（从 normalize.py 移植）"""
        norm = Normalizer.normalize_text(path)
        parts = norm.split("/")
        tokens = []
        for p in parts:
            toks = re.split(r"[^0-9A-Za-z\\u4e00-\\u9fa5]+", p)
            tokens.extend([t for t in toks if t])
        return tokens
    
    @staticmethod
    def _contains_any(s: str, words: list[str]) -> bool:
        """检查是否包含任意词汇"""
        return any(w in s for w in words)
    
    @staticmethod
    def canon_sample_type_full(raw: Optional[str], rel_path: str) -> Tuple[Optional[str], bool]:
        """
        完整的样品类型规范化（从 normalization.py 移植）
        返回：(规范化结果, 是否拒收)
        """
        p = f"{rel_path} {raw or ''}"
        if Normalizer._contains_any(p, QC_WORDS):
            return (None, True)
        if Normalizer._contains_any(p, MUD_WORDS):
            return ("泥浆", False)
        if Normalizer._contains_any(p, CORE_WORDS):
            return ("岩心", False)
        if Normalizer._contains_any(p, CUTTINGS_WORDS):
            return ("岩屑", False)
        return ((raw or None), False)
    
    @staticmethod
    def canon_sample_type_simple(s: Optional[str]) -> str:
        """
        简单样品类型规范化（从 grouping.py 移植）
        返回：规范化结果字符串
        """
        t = (s or "").strip()
        mapping = {"岩屽":"岩屑","岩芯":"岩心","钻井液":"泥浆","岩屑岩心":"岩屑"}
        return mapping.get(t, t)
    
    @staticmethod
    def canon_category(raw: Optional[str], rel_path: str) -> Tuple[Optional[str], bool]:
        """
        类别规范化（从 normalization.py 移植）
        返回：(规范化结果, 是否拒收)
        """
        cat = (raw or "").strip()
        if cat == "轻烃谱图" and Normalizer._contains_any(rel_path, HOTWORDS):
            return (None, True)
        return (cat or None, False)

# 为了向后兼容，提供模块级函数
def normalize_text(s: str) -> str:
    """向后兼容：文本规范化"""
    return Normalizer.normalize_text(s)

def normalize_for_depth(s: str) -> str:
    """向后兼容：深度规范化"""
    return Normalizer.normalize_for_depth(s)

def tokenize_path(path: str):
    """向后兼容：路径分词"""
    return Normalizer.tokenize_path(path)

def canon_sample_type_simple(s: Optional[str]) -> str:
    """向后兼容：简单样品类型规范化"""
    return Normalizer.canon_sample_type_simple(s)
