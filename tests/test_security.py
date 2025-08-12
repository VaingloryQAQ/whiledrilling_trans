"""安全模块测试"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi import HTTPException

from app.security import SecurityValidator, RateLimiter

class TestSecurityValidator:
    """安全验证器测试"""
    
    def test_is_safe_path(self):
        """测试路径安全检查"""
        base_path = Path("/safe/base")
        
        # 安全路径
        assert SecurityValidator.is_safe_path(base_path, base_path / "file.txt")
        assert SecurityValidator.is_safe_path(base_path, base_path / "subdir" / "file.txt")
        
        # 不安全路径
        assert not SecurityValidator.is_safe_path(base_path, Path("/etc/passwd"))
        assert not SecurityValidator.is_safe_path(base_path, base_path / ".." / "file.txt")
    
    def test_validate_file_path(self):
        """测试文件路径验证"""
        base_dir = Path("/test/base")
        
        # 正常路径
        result = SecurityValidator.validate_file_path("file.txt", base_dir)
        assert result == base_dir / "file.txt"
        
        # 路径遍历攻击
        with pytest.raises(HTTPException) as exc_info:
            SecurityValidator.validate_file_path("../../../etc/passwd", base_dir)
        assert exc_info.value.status_code == 400
        
        # 绝对路径攻击
        with pytest.raises(HTTPException) as exc_info:
            SecurityValidator.validate_file_path("/etc/passwd", base_dir)
        assert exc_info.value.status_code == 400
    
    def test_validate_upload_file(self):
        """测试文件上传验证"""
        # 创建模拟文件
        mock_file = Mock()
        mock_file.filename = "test.jpg"
        mock_file.content_type = "image/jpeg"
        mock_file.size = 1024
        
        # 正常文件
        is_safe, error_msg = SecurityValidator.validate_upload_file(mock_file)
        assert is_safe
        assert error_msg == ""
        
        # 不支持的文件类型
        mock_file.filename = "test.exe"
        is_safe, error_msg = SecurityValidator.validate_upload_file(mock_file)
        assert not is_safe
        assert "不支持的文件类型" in error_msg
        
        # 文件过大
        mock_file.filename = "test.jpg"
        mock_file.size = 20 * 1024 * 1024  # 20MB
        is_safe, error_msg = SecurityValidator.validate_upload_file(mock_file)
        assert not is_safe
        assert "文件大小超过限制" in error_msg
    
    def test_sanitize_filename(self):
        """测试文件名清理"""
        # 正常文件名
        assert SecurityValidator.sanitize_filename("test.jpg") == "test.jpg"
        
        # 包含危险字符
        assert SecurityValidator.sanitize_filename("test/../file.jpg") == "test___file.jpg"
        assert SecurityValidator.sanitize_filename("test<>.jpg") == "test__.jpg"
        
        # 过长文件名
        long_name = "a" * 300 + ".jpg"
        sanitized = SecurityValidator.sanitize_filename(long_name)
        assert len(sanitized) <= 255
        assert sanitized.endswith(".jpg")
    
    def test_validate_well_name(self):
        """测试井名验证"""
        # 有效井名
        assert SecurityValidator.validate_well_name("BZ8-3S-3")
        assert SecurityValidator.validate_well_name("LK25-4-2d")
        
        # 无效井名
        assert not SecurityValidator.validate_well_name("")
        assert not SecurityValidator.validate_well_name("test<script>")
        assert not SecurityValidator.validate_well_name("test' OR 1=1--")
    
    def test_validate_depth_value(self):
        """测试深度值验证"""
        # 有效深度
        assert SecurityValidator.validate_depth_value(1000.5)
        assert SecurityValidator.validate_depth_value(0)
        assert SecurityValidator.validate_depth_value(5000)
        
        # 无效深度
        assert not SecurityValidator.validate_depth_value(-1)
        assert not SecurityValidator.validate_depth_value(15000)
        assert not SecurityValidator.validate_depth_value("invalid")

class TestRateLimiter:
    """速率限制器测试"""
    
    def test_rate_limiter(self):
        """测试速率限制"""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        client_ip = "127.0.0.1"
        
        # 前3个请求应该被允许
        assert limiter.is_allowed(client_ip)
        assert limiter.is_allowed(client_ip)
        assert limiter.is_allowed(client_ip)
        
        # 第4个请求应该被拒绝
        assert not limiter.is_allowed(client_ip)
    
    def test_rate_limiter_window(self):
        """测试速率限制时间窗口"""
        limiter = RateLimiter(max_requests=1, window_seconds=1)
        client_ip = "127.0.0.1"
        
        # 第一个请求被允许
        assert limiter.is_allowed(client_ip)
        
        # 第二个请求被拒绝
        assert not limiter.is_allowed(client_ip)
        
        # 等待时间窗口过去后应该被允许
        import time
        time.sleep(1.1)
        assert limiter.is_allowed(client_ip)