"""中间件测试"""

import pytest
from unittest.mock import Mock, AsyncMock
from fastapi import FastAPI, Request, HTTPException
from fastapi.testclient import TestClient
from starlette.responses import Response

from app.middleware import (
    ErrorHandlingMiddleware, 
    LoggingMiddleware, 
    SecurityMiddleware,
    RateLimitMiddleware,
    RequestValidationMiddleware,
    AppException,
    ValidationException,
    SecurityException,
    NotFoundException
)

class TestErrorHandlingMiddleware:
    """错误处理中间件测试"""
    
    @pytest.fixture
    def app(self):
        """创建测试应用"""
        app = FastAPI()
        
        @app.get("/test")
        def test_endpoint():
            return {"message": "success"}
        
        @app.get("/error")
        def error_endpoint():
            raise HTTPException(status_code=400, detail="Test error")
        
        @app.get("/unhandled")
        def unhandled_error():
            raise ValueError("Unhandled error")
        
        return app
    
    @pytest.fixture
    def client(self, app):
        """创建测试客户端"""
        app.add_middleware(ErrorHandlingMiddleware)
        return TestClient(app)
    
    def test_normal_request(self, client):
        """测试正常请求"""
        response = client.get("/test")
        assert response.status_code == 200
        assert response.json() == {"message": "success"}
    
    def test_http_exception(self, client):
        """测试HTTP异常处理"""
        response = client.get("/error")
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "Test error"
        assert data["type"] == "http_exception"
    
    def test_unhandled_exception(self, client):
        """测试未处理异常"""
        response = client.get("/unhandled")
        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "内部服务器错误"
        assert data["type"] == "internal_error"

class TestSecurityMiddleware:
    """安全中间件测试"""
    
    @pytest.fixture
    def app(self):
        """创建测试应用"""
        app = FastAPI()
        
        @app.get("/test")
        def test_endpoint():
            return {"message": "success"}
        
        return app
    
    @pytest.fixture
    def client(self, app):
        """创建测试客户端"""
        app.add_middleware(SecurityMiddleware)
        return TestClient(app)
    
    def test_security_headers(self, client):
        """测试安全响应头"""
        response = client.get("/test")
        assert response.status_code == 200
        
        # 检查安全响应头
        headers = response.headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-XSS-Protection"] == "1; mode=block"
        assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "Content-Security-Policy" in headers

class TestRateLimitMiddleware:
    """速率限制中间件测试"""
    
    @pytest.fixture
    def app(self):
        """创建测试应用"""
        app = FastAPI()
        
        @app.get("/test")
        def test_endpoint():
            return {"message": "success"}
        
        return app
    
    @pytest.fixture
    def client(self, app):
        """创建测试客户端"""
        app.add_middleware(RateLimitMiddleware, max_requests=3, window_seconds=60)
        return TestClient(app)
    
    def test_rate_limiting(self, client):
        """测试速率限制"""
        # 前3个请求应该成功
        for i in range(3):
            response = client.get("/test")
            assert response.status_code == 200
        
        # 第4个请求应该被限制
        response = client.get("/test")
        assert response.status_code == 429
        data = response.json()
        assert data["error"] == "请求过于频繁，请稍后再试"
        assert data["type"] == "rate_limit_exceeded"

class TestRequestValidationMiddleware:
    """请求验证中间件测试"""
    
    @pytest.fixture
    def app(self):
        """创建测试应用"""
        app = FastAPI()
        
        @app.get("/test")
        def test_endpoint():
            return {"message": "success"}
        
        @app.post("/test")
        def test_post():
            return {"message": "success"}
        
        return app
    
    @pytest.fixture
    def client(self, app):
        """创建测试客户端"""
        app.add_middleware(RequestValidationMiddleware)
        return TestClient(app)
    
    def test_valid_request(self, client):
        """测试有效请求"""
        response = client.get("/test")
        assert response.status_code == 200
    
    def test_invalid_method(self, client):
        """测试无效请求方法"""
        # 使用不支持的请求方法
        response = client.request("TRACE", "/test")
        assert response.status_code == 405
        data = response.json()
        assert data["error"] == "不支持的请求方法"
        assert data["type"] == "method_not_allowed"
    
    def test_large_payload(self, client):
        """测试大负载请求"""
        # 创建大负载
        large_data = "x" * (11 * 1024 * 1024)  # 11MB
        
        response = client.post("/test", content=large_data)
        assert response.status_code == 413
        data = response.json()
        assert data["error"] == "请求体过大"
        assert data["type"] == "payload_too_large"

class TestAppExceptions:
    """应用异常测试"""
    
    def test_validation_exception(self):
        """测试验证异常"""
        exc = ValidationException("验证失败")
        assert exc.status_code == 400
        assert exc.error_type == "validation_error"
        assert str(exc) == "验证失败"
    
    def test_security_exception(self):
        """测试安全异常"""
        exc = SecurityException("安全违规")
        assert exc.status_code == 403
        assert exc.error_type == "security_error"
        assert str(exc) == "安全违规"
    
    def test_not_found_exception(self):
        """测试未找到异常"""
        exc = NotFoundException("资源不存在")
        assert exc.status_code == 404
        assert exc.error_type == "not_found"
        assert str(exc) == "资源不存在"
    
    def test_custom_app_exception(self):
        """测试自定义应用异常"""
        exc = AppException("自定义错误", status_code=418, error_type="custom_error")
        assert exc.status_code == 418
        assert exc.error_type == "custom_error"
        assert str(exc) == "自定义错误"