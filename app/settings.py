"""配置管理模块 - 使用Pydantic进行配置验证和管理"""

from pathlib import Path
from typing import Set, Optional, Dict, Any
from pydantic import BaseSettings, validator, Field
import os

class AppSettings(BaseSettings):
    """应用配置类"""
    
    # 数据库配置
    database_url: str = "sqlite:///./data/images.db"
    
    # 文件上传配置
    upload_max_size: int = Field(default=10 * 1024 * 1024, description="最大上传文件大小(字节)")
    allowed_extensions: Set[str] = Field(
        default={'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp'},
        description="允许的文件扩展名"
    )
    allowed_mime_types: Set[str] = Field(
        default={'image/jpeg', 'image/jpg', 'image/png', 'image/bmp', 'image/tiff', 'image/gif', 'image/webp'},
        description="允许的MIME类型"
    )
    
    # 图片处理配置
    max_image_width: int = Field(default=8000, description="最大图片宽度")
    max_image_height: int = Field(default=8000, description="最大图片高度")
    preview_max_side: int = Field(default=4000, description="预览图片最大边长")
    
    # 安全配置
    rate_limit_requests: int = Field(default=100, description="速率限制请求数")
    rate_limit_window: int = Field(default=60, description="速率限制时间窗口(秒)")
    
    # 缓存配置
    cache_max_size: int = Field(default=128, description="缓存最大条目数")
    cache_ttl: int = Field(default=300, description="缓存生存时间(秒)")
    
    # 数据库连接池配置
    db_pool_size: int = Field(default=10, description="数据库连接池大小")
    db_max_overflow: int = Field(default=20, description="数据库最大溢出连接数")
    db_pool_recycle: int = Field(default=3600, description="数据库连接回收时间(秒)")
    
    # 路径配置
    base_dir: Path = Field(default=Path(__file__).parent.parent, description="基础目录")
    data_dir: Path = Field(default=Path("./data"), description="数据目录")
    uploads_dir: Path = Field(default=Path("./data/uploads"), description="上传目录")
    extracted_dir: Path = Field(default=Path("./data/extracted"), description="解压目录")
    thumbs_dir: Path = Field(default=Path("./data/thumbs"), description="缩略图目录")
    cache_dir: Path = Field(default=Path("./data/cache"), description="缓存目录")
    
    # 深度分组配置
    depth_granularity: float = Field(default=1.0, description="深度分组粒度")
    depth_tolerance: float = Field(default=1.5, description="深度分组容差")
    
    # 样品类型敏感配置
    sample_sensitive_types: Set[str] = Field(
        default={'岩屑', '壁心'},
        description="样品类型敏感度配置"
    )
    
    @validator('base_dir', 'data_dir', 'uploads_dir', 'extracted_dir', 'thumbs_dir', 'cache_dir')
    def validate_paths(cls, v):
        """验证路径配置"""
        if isinstance(v, str):
            v = Path(v)
        return v
    
    @validator('upload_max_size')
    def validate_upload_size(cls, v):
        """验证上传大小限制"""
        if v <= 0 or v > 100 * 1024 * 1024:  # 最大100MB
            raise ValueError("上传大小限制必须在1字节到100MB之间")
        return v
    
    @validator('preview_max_side')
    def validate_preview_size(cls, v):
        """验证预览尺寸限制"""
        if v <= 0 or v > 8000:
            raise ValueError("预览尺寸限制必须在1到8000之间")
        return v
    
    @validator('rate_limit_requests')
    def validate_rate_limit(cls, v):
        """验证速率限制配置"""
        if v <= 0 or v > 1000:
            raise ValueError("速率限制请求数必须在1到1000之间")
        return v
    
    def ensure_directories(self):
        """确保必要的目录存在"""
        directories = [
            self.data_dir,
            self.uploads_dir,
            self.extracted_dir,
            self.thumbs_dir,
            self.cache_dir,
            self.cache_dir / "previews"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_database_url(self) -> str:
        """获取数据库URL"""
        if self.database_url.startswith('sqlite:///'):
            # 确保SQLite数据库目录存在
            db_path = Path(self.database_url.replace('sqlite:///', ''))
            db_path.parent.mkdir(parents=True, exist_ok=True)
        return self.database_url
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

class SecuritySettings(BaseSettings):
    """安全配置类"""
    
    # 路径安全检查
    enable_path_validation: bool = Field(default=True, description="启用路径验证")
    enable_file_validation: bool = Field(default=True, description="启用文件验证")
    enable_rate_limiting: bool = Field(default=True, description="启用速率限制")
    
    # 文件上传安全
    enable_content_validation: bool = Field(default=True, description="启用内容验证")
    enable_filename_sanitization: bool = Field(default=True, description="启用文件名清理")
    
    # 输入验证
    enable_input_validation: bool = Field(default=True, description="启用输入验证")
    max_input_length: int = Field(default=1000, description="最大输入长度")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

class PerformanceSettings(BaseSettings):
    """性能配置类"""
    
    # 数据库优化
    enable_query_cache: bool = Field(default=True, description="启用查询缓存")
    enable_connection_pool: bool = Field(default=True, description="启用连接池")
    enable_indexes: bool = Field(default=True, description="启用数据库索引")
    
    # 前端优化
    enable_lazy_loading: bool = Field(default=True, description="启用懒加载")
    enable_virtual_scroll: bool = Field(default=True, description="启用虚拟滚动")
    enable_debouncing: bool = Field(default=True, description="启用防抖")
    
    # 缓存策略
    enable_browser_cache: bool = Field(default=True, description="启用浏览器缓存")
    cache_control_max_age: int = Field(default=2592000, description="缓存控制最大年龄(秒)")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

# 全局配置实例
settings = AppSettings()
security_settings = SecuritySettings()
performance_settings = PerformanceSettings()

# 确保目录存在
settings.ensure_directories()

def get_settings() -> AppSettings:
    """获取应用配置"""
    return settings

def get_security_settings() -> SecuritySettings:
    """获取安全配置"""
    return security_settings

def get_performance_settings() -> PerformanceSettings:
    """获取性能配置"""
    return performance_settings

def reload_settings():
    """重新加载配置"""
    global settings, security_settings, performance_settings
    settings = AppSettings()
    security_settings = SecuritySettings()
    performance_settings = PerformanceSettings()
    settings.ensure_directories()