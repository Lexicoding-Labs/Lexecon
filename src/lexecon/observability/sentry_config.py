"""Sentry integration for error tracking and performance monitoring.

Provides centralized Sentry configuration for the Lexecon governance system,
including FastAPI integration, error tracking, and performance monitoring.
"""

import os
from typing import Optional

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration


def init_sentry(
    dsn: Optional[str] = None,
    environment: Optional[str] = None,
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1,
    enable_tracing: bool = True,
) -> None:
    """Initialize Sentry SDK with FastAPI integration.

    Args:
        dsn: Sentry DSN. If not provided, reads from SENTRY_DSN env var
        environment: Deployment environment (production, staging, development)
        traces_sample_rate: Percentage of transactions to trace (0.0 to 1.0)
        profiles_sample_rate: Percentage of transactions to profile (0.0 to 1.0)
        enable_tracing: Whether to enable performance tracing
    """
    # Get DSN from parameter or environment
    sentry_dsn = dsn or os.getenv("SENTRY_DSN")

    if not sentry_dsn:
        # Sentry is optional - if no DSN provided, skip initialization
        return

    # Determine environment
    env = environment or os.getenv("LEXECON_ENV", "development")

    # Configure Sentry
    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=env,
        # Enable FastAPI and Starlette integrations
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            StarletteIntegration(transaction_style="endpoint"),
        ],
        # Performance monitoring
        traces_sample_rate=traces_sample_rate if enable_tracing else 0.0,
        profiles_sample_rate=profiles_sample_rate if enable_tracing else 0.0,
        # Send PII data for better debugging (disable in production if needed)
        send_default_pii=env != "production",
        # Release tracking (can be set via SENTRY_RELEASE env var)
        release=os.getenv("SENTRY_RELEASE"),
        # Additional options
        attach_stacktrace=True,
        max_breadcrumbs=50,
    )


def capture_exception(
    error: Exception,
    context: Optional[dict] = None,
    level: str = "error",
) -> str:
    """Capture an exception and send to Sentry.

    Args:
        error: The exception to capture
        context: Additional context to attach
        level: Severity level (fatal, error, warning, info, debug)

    Returns:
        Event ID from Sentry
    """
    with sentry_sdk.push_scope() as scope:
        if context:
            for key, value in context.items():
                scope.set_context(key, value)

        scope.level = level
        return sentry_sdk.capture_exception(error)


def capture_message(
    message: str,
    level: str = "info",
    context: Optional[dict] = None,
) -> str:
    """Capture a message and send to Sentry.

    Args:
        message: The message to capture
        level: Severity level (fatal, error, warning, info, debug)
        context: Additional context to attach

    Returns:
        Event ID from Sentry
    """
    with sentry_sdk.push_scope() as scope:
        if context:
            for key, value in context.items():
                scope.set_context(key, value)

        scope.level = level
        return sentry_sdk.capture_message(message)


def set_user(user_id: str, email: Optional[str] = None, username: Optional[str] = None) -> None:
    """Set user context for error tracking.

    Args:
        user_id: Unique user identifier
        email: User email address
        username: Username
    """
    sentry_sdk.set_user({
        "id": user_id,
        "email": email,
        "username": username,
    })


def set_context(name: str, data: dict) -> None:
    """Add custom context to Sentry events.

    Args:
        name: Context category name
        data: Context data dictionary
    """
    sentry_sdk.set_context(name, data)


def add_breadcrumb(
    message: str,
    category: str = "default",
    level: str = "info",
    data: Optional[dict] = None,
) -> None:
    """Add a breadcrumb for debugging.

    Args:
        message: Breadcrumb message
        category: Category (e.g., "auth", "database", "http")
        level: Severity level
        data: Additional data
    """
    sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        level=level,
        data=data or {},
    )
