"""安全模块 - 提供各种安全检查功能"""

import re
import hashlib
import mimetypes
from pathlib import Path
from typing import Set, Optional, Tuple
from fastapi import HTTPException, UploadFile
from PIL import Image as PILImage
import io

class SecurityValidator:
    """安全验证器"""
    
    # 允许的文件扩展名
    ALLOWED_IMAGE_EXTENSIONS: Set[str] = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp'}
    
    # 允许的MIME类型
    ALLOWED_MIME_TYPES: Set[str] = {
        'image/jpeg', 'image/jpg', 'image/png', 'image/bmp', 
        'image/tiff', 'image/gif', 'image/webp'
    }
    
    # 文件大小限制 (10MB)
    MAX_FILE_SIZE: int = 10 * 1024 * 1024
    
    # 图片尺寸限制
    MAX_IMAGE_WIDTH: int = 8000
    MAX_IMAGE_HEIGHT: int = 8000
    
    @staticmethod
    def is_safe_path(base_path: Path, target_path: Path) -> bool:
        """
        检查路径是否安全，防止路径遍历攻击
        
        Args:
            base_path: 基础路径
            target_path: 目标路径
            
        Returns:
            bool: 路径是否安全
        """
        try:
            base_resolved = base_path.resolve()
            target_resolved = target_path.resolve()
            
            # 检查目标路径是否在基础路径下
            return str(target_resolved).startswith(str(base_resolved))
        except (ValueError, RuntimeError):
            return False
    
    @staticmethod
    def validate_file_path(rel_path: str, base_dir: Path) -> Path:
        """
        验证文件路径并返回安全的绝对路径
        
        Args:
            rel_path: 相对路径
            base_dir: 基础目录
            
        Returns:
            Path: 安全的绝对路径
            
        Raises:
            HTTPException: 路径不安全时抛出异常
        """
        # 规范化路径
        rel_path = rel_path.replace('\\', '/').lstrip('/')
        
        # 检查路径遍历攻击
        if '..' in rel_path or rel_path.startswith('/'):
            raise HTTPException(status_code=400, detail="路径包含非法字符")
        
        # 构建目标路径
        target_path = base_dir / rel_path
        
        # 安全检查
        if not SecurityValidator.is_safe_path(base_dir, target_path):
            raise HTTPException(status_code=400, detail="路径超出允许范围")
        
        return target_path
    
    @staticmethod
    def validate_upload_file(file: UploadFile) -> Tuple[bool, str]:
        """
        验证上传文件的安全性
        
        Args:
            file: 上传的文件
            
        Returns:
            Tuple[bool, str]: (是否安全, 错误信息)
        """
        # 检查文件扩展名
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in SecurityValidator.ALLOWED_IMAGE_EXTENSIONS:
            return False, f"不支持的文件类型: {file_ext}"
        
        # 检查MIME类型
        if file.content_type and file.content_type not in SecurityValidator.ALLOWED_MIME_TYPES:
            return False, f"不支持的MIME类型: {file.content_type}"
        
        # 检查文件大小
        if file.size and file.size > SecurityValidator.MAX_FILE_SIZE:
            return False, f"文件大小超过限制: {file.size} bytes"
        
        return True, ""
    
    @staticmethod
    def validate_image_content(file: UploadFile) -> Tuple[bool, str]:
        """
        验证图片内容的有效性
        
        Args:
            file: 上传的文件
            
        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        try:
            # 读取文件内容
            content = file.file.read()
            file.file.seek(0)  # 重置文件指针
            
            # 检查文件大小
            if len(content) > SecurityValidator.MAX_FILE_SIZE:
                return False, "文件内容过大"
            
            # 尝试打开图片
            with PILImage.open(io.BytesIO(content)) as img:
                # 检查图片尺寸
                if img.width > SecurityValidator.MAX_IMAGE_WIDTH or img.height > SecurityValidator.MAX_IMAGE_HEIGHT:
                    return False, f"图片尺寸过大: {img.width}x{img.height}"
                
                # 检查是否为有效图片
                img.verify()
                
        except Exception as e:
            return False, f"图片格式无效: {str(e)}"
        
        return True, ""
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        清理文件名，移除危险字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            str: 清理后的文件名
        """
        # 移除路径分隔符和危险字符
        dangerous_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\0']
        for char in dangerous_chars:
            filename = filename.replace(char, '_')
        
        # 限制长度
        if len(filename) > 255:
            name, ext = Path(filename).stem, Path(filename).suffix
            max_name_length = 255 - len(ext)
            filename = name[:max_name_length] + ext
        
        return filename
    
    @staticmethod
    def validate_well_name(well_name: str) -> bool:
        """
        验证井名格式
        
        Args:
            well_name: 井名
            
        Returns:
            bool: 井名是否有效
        """
        if not well_name:
            return False
        
        # 井名格式：字母数字和连字符
        pattern = r'^[A-Za-z0-9\-]+$'
        return bool(re.match(pattern, well_name))
    
    @staticmethod
    def validate_depth_value(depth: float) -> bool:
        """
        验证深度值
        
        Args:
            depth: 深度值
            
        Returns:
            bool: 深度值是否有效
        """
        return isinstance(depth, (int, float)) and 0 <= depth <= 10000
    
    @staticmethod
    def generate_safe_filename(original_name: str, prefix: str = "") -> str:
        """
        生成安全的文件名
        
        Args:
            original_name: 原始文件名
            prefix: 前缀
            
        Returns:
            str: 安全的文件名
        """
        # 清理原始文件名
        safe_name = SecurityValidator.sanitize_filename(original_name)
        
        # 生成哈希值
        name_hash = hashlib.md5(safe_name.encode()).hexdigest()[:8]
        
        # 构建新文件名
        name_parts = Path(safe_name)
        new_name = f"{prefix}{name_hash}_{name_parts.stem}{name_parts.suffix}"
        
        return SecurityValidator.sanitize_filename(new_name)

class RateLimiter:
    """简单的速率限制器"""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # {ip: [(timestamp, count), ...]}
    
    def is_allowed(self, client_ip: str) -> bool:
        """
        检查请求是否被允许
        
        Args:
            client_ip: 客户端IP
            
        Returns:
            bool: 是否允许请求
        """
        import time
        current_time = time.time()
        
        # 清理过期的请求记录
        if client_ip in self.requests:
            self.requests[client_ip] = [
                (ts, count) for ts, count in self.requests[client_ip]
                if current_time - ts < self.window_seconds
            ]
        
        # 计算当前窗口内的请求数
        current_requests = sum(count for _, count in self.requests.get(client_ip, []))
        
        if current_requests >= self.max_requests:
            return False
        
        # 记录新请求
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        self.requests[client_ip].append((current_time, 1))
        
        return True

# 全局速率限制器实例
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)