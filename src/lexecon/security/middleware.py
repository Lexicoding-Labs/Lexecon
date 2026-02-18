"""FastAPI middleware for authentication and authorization."""

from functools import wraps
from typing import Callable, Optional

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from lexecon.security.auth_service import AuthService, Permission, Session
from lexecon.security.rate_limiter import RateLimiter
from lexecon.security.security_headers import SecurityHeadersMiddleware


class AuthMiddleware:
    """Authentication middleware for FastAPI."""

    def __init__(self, auth_service: AuthService):
        self.auth_service = auth_service

    async def __call__(self, request: Request, call_next):
        """Middleware to validate session on protected endpoints."""
        # Skip authentication for public endpoints
        public_endpoints = [
            "/health",
            "/login",
            "/docs",
            "/openapi.json",
            "/redoc",
        ]

        if any(request.url.path.startswith(endpoint) for endpoint in public_endpoints):
            return await call_next(request)

        # Get session token from cookie or header
        session_id = request.cookies.get("session_id")
        if not session_id:
            session_id = request.headers.get("Authorization", "").replace("Bearer ", "")

        if not session_id:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Not authenticated", "message": "No session token provided"},
            )

        # Validate session
        session, error = self.auth_service.validate_session(session_id)
        if not session:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Invalid session", "message": error},
            )

        # Attach session to request state
        request.state.session = session
        request.state.user_id = session.user_id
        request.state.username = session.username
        request.state.role = session.role

        return await call_next(request)


def require_permission(permission: Permission):
    """Decorator to require a specific permission for an endpoint.

    Usage:
        @require_permission(Permission.EXPORT_DATA)
        async def some_endpoint(request: Request):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            if not hasattr(request.state, "session"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                )

            session: Session = request.state.session
            auth_service = request.app.state.auth_service

            if not auth_service.has_permission(session.role, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {permission.value}",
                )

            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


class RateLimitMiddleware:
    """Rate limiting middleware for FastAPI."""

    BYPASS_PATHS = ("/health",)

    def __init__(self, rate_limiter: RateLimiter):
        self.rate_limiter = rate_limiter

    async def __call__(self, request: Request, call_next):
        if any(request.url.path.startswith(p) for p in self.BYPASS_PATHS):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        allowed, info = self.rate_limiter.check_rate_limit(client_ip)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"retry_after_seconds": info.get("retry_after_seconds", 60)},
                headers={"Retry-After": str(info.get("retry_after_seconds", 60))},
            )

        response = await call_next(request)

        cfg = self.rate_limiter.config
        response.headers["X-RateLimit-Limit-Minute"] = str(cfg.requests_per_minute)
        response.headers["X-RateLimit-Limit-Hour"] = str(cfg.requests_per_hour)
        response.headers["X-RateLimit-Remaining-Minute"] = str(info.get("remaining_minute", 0))
        response.headers["X-RateLimit-Remaining-Hour"] = str(info.get("remaining_hour", 0))
        return response


def get_current_user(request: Request) -> Optional[dict]:
    """Helper to get current user from request."""
    if not hasattr(request.state, "session"):
        return None

    return {
        "user_id": request.state.user_id,
        "username": request.state.username,
        "role": request.state.role.value if hasattr(request.state.role, "value") else str(request.state.role),
    }
