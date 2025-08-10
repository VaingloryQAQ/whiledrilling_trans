# app/normalize.py
import re

# 显式的“全角→半角”映射，避免 maketrans 两端长度不等的问题
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
}
# 全角数字 ０-９
FULL_TO_HALF.update({
    ord('０'): '0', ord('１'): '1', ord('２'): '2', ord('３'): '3', ord('４'): '4',
    ord('５'): '5', ord('６'): '6', ord('７'): '7', ord('８'): '8', ord('９'): '9'
})

def normalize_text(s: str) -> str:
    if not s:
        return s
    # 统一全角/半角、大小写与分隔
    s = s.translate(FULL_TO_HALF)
    s = s.replace("\\", "/")  # 统一分隔符
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s

def normalize_for_depth(s: str) -> str:
    s = normalize_text(s)
    # 破折号/波浪/to 统一成 '-'
    s = re.sub(r"(—|~|\\bto\\b)", "-", s, flags=re.IGNORECASE)
    # 小数逗号 -> 点（但 1,000 这种千分位逗号要去掉）
    s = re.sub(r"(?<=\\d),(?=\\d{3}\\b)", "", s)   # 1,000 -> 1000
    s = re.sub(r"(?<=\\d),(?=\\d+\\b)", ".", s)    # 12,34 -> 12.34
    # 去除深度后面常见噪声（m.)] 等）
    s = re.sub(r"m[)\\].,]*\\b", "m", s, flags=re.IGNORECASE)
    return s

def tokenize_path(path: str):
    norm = normalize_text(path)
    parts = norm.split("/")
    tokens = []
    for p in parts:
        toks = re.split(r"[^0-9A-Za-z\\u4e00-\\u9fa5]+", p)
        tokens.extend([t for t in toks if t])
    return tokens
