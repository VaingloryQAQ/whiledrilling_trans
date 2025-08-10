"""数据库模型定义（SQLModel）。"""

from typing import Optional
from sqlmodel import SQLModel, Field


class Image(SQLModel, table=True):
    """图片记录。

    字段说明：
    - file_path: 绝对或工程内路径
    - rel_path: 相对 `data/extracted` 的路径
    - thumb_path: 相对 `data/thumbs` 的缩略图路径
    - file_hash: MD5 用于去重
    - well_name: 井名
    - sample_type: 样品类型
    - category: 分类标签
    - start_depth/end_depth: 深度区间（米）
    - ndepth_center: 深度中心（便于分组）
    - anomalies: 异常信息（分号拼接）
    - explain: 分类命中说明（JSON 字符串）
    - raw_name: 原始文件名
    - source_batch: 批次名（来源目录/压缩包名）
    - ingested_at: 导入时间字符串
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    file_path: str
    rel_path: str
    thumb_path: Optional[str] = None
    file_hash: Optional[str] = None
    well_name: Optional[str] = None
    sample_type: Optional[str] = None
    category: Optional[str] = None
    start_depth: Optional[float] = None
    end_depth: Optional[float] = None
    ndepth_center: Optional[float] = None
    anomalies: Optional[str] = None
    explain: Optional[str] = None
    raw_name: Optional[str] = None
    source_batch: Optional[str] = None
    ingested_at: Optional[str] = None


def anomalies_to_str(items):
    """将异常列表以分号拼接为字符串；空列表返回 None。"""
    return ";".join(items) if items else None