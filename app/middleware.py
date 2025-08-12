"""中间件模块 - 提供错误处理、日志记录、安全中间件等功能"""

import time
import logging
import traceback
from typing import Callable, Dict, Any
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import json

logger = logging.getLogger(__name__)

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """错误处理中间件"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except HTTPException as e:
            # FastAPI HTTP异常
            logger.warning(f"HTTP异常: {e.status_code} - {e.detail}")
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": e.detail,
                    "type": "http_exception",
                    "status_code": e.status_code
                }
            )
        except Exception as e:
            # 未处理的异常
            logger.error(f"未处理异常: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "内部服务器错误",
                    "type": "internal_error",
                    "message": str(e) if logger.isEnabledFor(logging.DEBUG) else "服务器内部错误"
                }
            )

class LoggingMiddleware(BaseHTTPMiddleware):
    """日志记录中间件"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # 记录请求信息
        logger.info(f"请求开始: {request.method} {request.url.path}")
        
        try:
            response = await call_next(request)
            
            # 记录响应信息
            process_time = time.time() - start_time
            logger.info(
                f"请求完成: {request.method} {request.url.path} - "
                f"状态码: {response.status_code} - 耗时: {process_time:.3f}s"
            )
            
            # 添加处理时间到响应头
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"请求失败: {request.method} {request.url.path} - "
                f"错误: {str(e)} - 耗时: {process_time:.3f}s"
            )
            raise

class SecurityMiddleware(BaseHTTPMiddleware):
    """安全中间件"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 添加安全响应头
        response = await call_next(request)
        
        # 安全响应头
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; script-src 'self' 'unsafe-inline'"
        
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件"""
    
    def __init__(self, app: ASGIApp, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host
        
        # 检查速率限制
        if not self._is_allowed(client_ip):
            logger.warning(f"速率限制触发: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "请求过于频繁，请稍后再试",
                    "type": "rate_limit_exceeded"
                }
            )
        
        response = await call_next(request)
        return response
    
    def _is_allowed(self, client_ip: str) -> bool:
        """检查客户端是否被允许"""
        current_time = time.time()
        
        # 清理过期的请求记录
        if client_ip in self.requests:
            self.requests[client_ip] = [
                ts for ts in self.requests[client_ip]
                if current_time - ts < self.window_seconds
            ]
        
        # 检查请求数量
        if len(self.requests.get(client_ip, [])) >= self.max_requests:
            return False
        
        # 记录新请求
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        self.requests[client_ip].append(current_time)
        
        return True

class RequestValidationMiddleware(BaseHTTPMiddleware):
    """请求验证中间件"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 验证请求大小
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > 10 * 1024 * 1024:  # 10MB限制
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "请求体过大",
                            "type": "payload_too_large"
                        }
                    )
            except ValueError:
                pass
        
        # 验证请求方法
        if request.method not in ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]:
            return JSONResponse(
                status_code=405,
                content={
                    "error": "不支持的请求方法",
                    "type": "method_not_allowed"
                }
            )
        
        response = await call_next(request)
        return response

class CachingMiddleware(BaseHTTPMiddleware):
    """缓存中间件"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.cache: Dict[str, Dict[str, Any]] = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 只缓存GET请求
        if request.method != "GET":
            return await call_next(request)
        
        # 生成缓存键
        cache_key = f"{request.url.path}:{request.url.query}"
        
        # 检查缓存
        if cache_key in self.cache:
            cached_item = self.cache[cache_key]
            if time.time() - cached_item["timestamp"] < 300:  # 5分钟缓存
                logger.info(f"缓存命中: {cache_key}")
                return cached_item["response"]
        
        # 执行请求
        response = await call_next(request)
        
        # 缓存响应（只缓存成功的响应）
        if response.status_code == 200:
            self.cache[cache_key] = {
                "response": response,
                "timestamp": time.time()
            }
        
        return response

def setup_middleware(app):
    """设置中间件"""
    # 注意：中间件的顺序很重要，从外到内执行
    
    # 1. 错误处理中间件（最外层）
    app.add_middleware(ErrorHandlingMiddleware)
    
    # 2. 日志记录中间件
    app.add_middleware(LoggingMiddleware)
    
    # 3. 安全中间件
    app.add_middleware(SecurityMiddleware)
    
    # 4. 速率限制中间件
    app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)
    
    # 5. 请求验证中间件
    app.add_middleware(RequestValidationMiddleware)
    
    # 6. 缓存中间件（最内层）
    app.add_middleware(CachingMiddleware)

class AppException(Exception):
    """应用异常基类"""
    
    def __init__(self, message: str, status_code: int = 500, error_type: str = "app_error"):
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        super().__init__(self.message)

class ValidationException(AppException):
    """验证异常"""
    
    def __init__(self, message: str):
        super().__init__(message, status_code=400, error_type="validation_error")

class SecurityException(AppException):
    """安全异常"""
    
    def __init__(self, message: str):
        super().__init__(message, status_code=403, error_type="security_error")

class NotFoundException(AppException):
    """未找到异常"""
    
    def __init__(self, message: str):
        super().__init__(message, status_code=404, error_type="not_found")

def handle_app_exception(request: Request, exc: AppException):
    """处理应用异常"""
    logger.error(f"应用异常: {exc.error_type} - {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "type": exc.error_type,
            "status_code": exc.status_code
        }
    )