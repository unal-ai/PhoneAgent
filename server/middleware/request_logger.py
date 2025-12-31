"""
请求日志中间件

功能：
1. 记录所有API请求和响应
2. 记录请求耗时
3. 记录错误和异常
4. 自动记录到日志文件
"""

import logging
import time
import traceback
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("api.request")


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """
    请求日志中间件

    记录每个API请求的详细信息：
    - 请求方法和路径
    - 客户端IP
    - 响应状态码
    - 请求耗时
    - 错误信息（如果有）
    """

    def __init__(self, app, exclude_paths: list = None):
        """
        初始化中间件

        Args:
            app: FastAPI应用实例
            exclude_paths: 不记录日志的路径列表（如健康检查）
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/health", "/api/docs", "/api/redoc"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        # 检查是否需要跳过日志
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # 记录请求开始
        start_time = time.time()
        client_ip = self._get_client_ip(request)

        # 日志上下文信息
        method = request.method
        path = request.url.path
        query = str(request.url.query) if request.url.query else ""

        # 记录请求开始（DEBUG级别）
        logger.debug(f"→ {method} {path}{'?' + query if query else ''} from {client_ip}")

        # 处理请求
        response = None
        error = None

        try:
            response = await call_next(request)
            status_code = response.status_code

        except Exception as e:
            # 捕获异常
            error = str(e)
            status_code = 500

            # 记录异常堆栈
            logger.error(f"{method} {path} - Exception: {error}")
            logger.error(traceback.format_exc())

            # 重新抛出异常让FastAPI处理
            raise

        finally:
            # 计算耗时
            duration = time.time() - start_time
            duration_ms = duration * 1000

            # 根据状态码和耗时选择日志级别
            if error or status_code >= 500:
                log_level = logging.ERROR
                status_mark = "[ERR]"
            elif status_code >= 400:
                log_level = logging.WARNING
                status_mark = "[WARN]"
            elif duration > 5.0:  # 超过5秒的慢请求
                log_level = logging.WARNING
                status_mark = "[SLOW]"
            else:
                log_level = logging.INFO
                status_mark = "[OK]"

            # 格式化日志消息
            log_message = (
                f"{status_mark} {method} {path} - {status_code} - {duration_ms:.0f}ms - {client_ip}"
            )

            if error:
                log_message += f" - ERROR: {error}"
            elif duration > 5.0:
                log_message += " - SLOW"

            # 记录日志
            logger.log(log_level, log_message)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """
        获取客户端真实IP

        优先级：
        1. X-Forwarded-For（代理）
        2. X-Real-IP（Nginx）
        3. request.client.host（直连）
        """
        # 检查代理头
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # X-Forwarded-For 可能包含多个IP，取第一个
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # 直连IP
        if request.client:
            return request.client.host

        return "unknown"


def format_request_log(
    method: str,
    path: str,
    status_code: int,
    duration: float,
    client_ip: str = "unknown",
    error: str = None,
) -> str:
    """
    格式化请求日志

    Args:
        method: HTTP方法
        path: 请求路径
        status_code: 状态码
        duration: 耗时（秒）
        client_ip: 客户端IP
        error: 错误信息

    Returns:
        格式化的日志字符串
    """
    duration_ms = duration * 1000

    # 选择状态标记
    if error or status_code >= 500:
        status_mark = "[ERR]"
    elif status_code >= 400:
        status_mark = "[WARN]"
    elif duration > 5.0:
        status_mark = "[SLOW]"
    else:
        status_mark = "[OK]"

    log_parts = [status_mark, method, path, f"{status_code}", f"{duration_ms:.0f}ms", client_ip]

    if error:
        log_parts.append(f"ERROR: {error}")
    elif duration > 5.0:
        log_parts.append("SLOW")

    return " - ".join(log_parts)


# 慢请求追踪
class SlowRequestTracker:
    """慢请求追踪器"""

    def __init__(self, threshold: float = 3.0):
        """
        初始化追踪器

        Args:
            threshold: 慢请求阈值（秒）
        """
        self.threshold = threshold
        self.slow_requests = []
        self.max_records = 100

    def record(self, method: str, path: str, duration: float, details: dict = None):
        """记录慢请求"""
        if duration >= self.threshold:
            record = {
                "method": method,
                "path": path,
                "duration": duration,
                "timestamp": time.time(),
                "details": details or {},
            }

            self.slow_requests.append(record)

            # 保持最近N条记录
            if len(self.slow_requests) > self.max_records:
                self.slow_requests.pop(0)

            logger.warning(f"[SLOW] Slow request detected: {method} {path} - {duration:.2f}s")

    def get_slow_requests(self, limit: int = 10):
        """获取最近的慢请求"""
        return sorted(self.slow_requests, key=lambda x: x["duration"], reverse=True)[:limit]

    def clear(self):
        """清空记录"""
        self.slow_requests.clear()


# 全局慢请求追踪器实例
_slow_tracker = SlowRequestTracker(threshold=3.0)


def get_slow_tracker() -> SlowRequestTracker:
    """获取慢请求追踪器"""
    return _slow_tracker
