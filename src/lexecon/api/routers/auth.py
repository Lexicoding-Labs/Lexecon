"""Authentication and OIDC endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from lexecon.api.dependencies import ServiceRegistry, get_services, get_session_id
from lexecon.api.models import (
    ChangePasswordRequest,
    CreateUserRequest,
    LoginRequest,
    LoginResponse,
    OIDCLinkedProvider,
    OIDCProviderInfo,
    OIDCUnlinkRequest,
    PasswordPolicyResponse,
    PasswordStatusResponse,
)
from lexecon.security.auth_service import Permission, Role, StaleCredentialsError

router = APIRouter()


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    request: Request,
    login_req: LoginRequest,
    services: ServiceRegistry = Depends(get_services),
):
    ip_address = request.client.host if request.client else None

    user, error = await services.async_auth_service.authenticate(
        login_req.username, login_req.password, ip_address,
    )

    if not user:
        return LoginResponse(success=False, error=error)

    # The supported local API cannot complete an MFA challenge. Fail closed and
    # give an explicit recovery message rather than implying a challenge exists.
    if error == "mfa_required":
        return LoginResponse(
            success=False,
            error="MFA-enabled accounts are unsupported by this local API; contact the local administrator for offline recovery",
        )

    try:
        session = await services.async_auth_service.create_session(user, ip_address)
    except StaleCredentialsError as exc:
        return LoginResponse(success=False, error=str(exc))

    if error == "password_change_required":
        return LoginResponse(
            success=False, session_id=session.session_id,
            error="Password change required; this session can only change the password",
        )

    services.audit_service.log_access(
        endpoint="/auth/login", method="POST", status_code=200,
        user_id=user.user_id, username=user.username, ip_address=ip_address,
    )

    return LoginResponse(
        success=True,
        session_id=session.session_id,
        user={
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "full_name": user.full_name,
        },
    )


@router.post("/auth/logout")
async def logout(
    request: Request,
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
):
    if session_id:
        await services.async_auth_service.revoke_session(session_id)
    return {"success": True, "message": "Logged out successfully"}


@router.get("/auth/me")
async def get_current_user_info(
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
):
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session, error = await services.async_auth_service.validate_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail=error)

    user = await services.async_auth_service.get_user_by_id(session.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user": {
            "id": user.user_id,
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "full_name": user.full_name,
            "last_login": user.last_login,
        }
    }


@router.post("/auth/users")
async def create_user(
    request: Request,
    user_req: CreateUserRequest,
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
):
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session, error = await services.async_auth_service.validate_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail=error)

    if not services.async_auth_service.has_permission(session.role, Permission.MANAGE_USERS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        user = await services.async_auth_service.create_user(
            username=user_req.username,
            email=user_req.email,
            password=user_req.password,
            role=Role(user_req.role),
            full_name=user_req.full_name,
        )
        return {
            "success": True,
            "user": {
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
                "full_name": user.full_name,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/auth/users")
async def list_users(
    request: Request,
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
):
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session, error = await services.async_auth_service.validate_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail=error)

    if not services.async_auth_service.has_permission(session.role, Permission.MANAGE_USERS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    users = await services.async_auth_service.list_users()
    return {
        "users": [
            {
                "user_id": u.user_id,
                "username": u.username,
                "email": u.email,
                "role": u.role.value,
                "full_name": u.full_name,
                "last_login": u.last_login,
                "is_active": u.is_active,
            }
            for u in users
        ],
    }


@router.post("/auth/change-password")
async def change_password(
    request: Request,
    password_req: ChangePasswordRequest,
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
):
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session, error = await services.async_auth_service.validate_session(session_id, True)
    if not session:
        raise HTTPException(status_code=401, detail=error)

    try:
        success, error = await services.async_auth_service.change_password(
            user_id=session.user_id,
            old_password=password_req.old_password,
            new_password=password_req.new_password,
        )

        if success:
            services.audit_service.log_access(
                endpoint="/auth/change-password", method="POST", status_code=200,
                user_id=session.user_id, username=session.username,
                ip_address=request.client.host if request.client else None,
            )
            return {"success": True, "message": "Password changed successfully"}
        raise HTTPException(status_code=500, detail="Failed to change password")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/auth/password-policy", response_model=PasswordPolicyResponse)
async def get_password_policy():
    from lexecon.security.password_policy import get_default_policy
    policy = get_default_policy()
    return PasswordPolicyResponse(
        min_length=policy.min_length,
        max_age_days=policy.max_age_days,
        history_count=policy.history_count,
        require_uppercase=policy.require_uppercase,
        require_lowercase=policy.require_lowercase,
        require_digits=policy.require_digits,
        require_special=policy.require_special,
        special_chars=policy.special_chars,
    )


@router.get("/auth/password-status", response_model=PasswordStatusResponse)
async def get_password_status(
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
):
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session, error = await services.async_auth_service.validate_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail=error)

    try:
        status = await services.async_auth_service.get_password_status(session.user_id)
        return PasswordStatusResponse(
            password_changed_at=status["password_changed_at"],
            password_expires_at=status["password_expires_at"],
            days_until_expiration=status["days_until_expiration"],
            is_expired=status["is_expired"],
            force_password_change=status["force_password_change"],
            password_age_days=status["password_age_days"],
            policy=PasswordPolicyResponse(**status["policy"]),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── OIDC OAuth Endpoints ──

@router.get("/auth/oidc/providers", response_model=List[OIDCProviderInfo])
async def list_oidc_providers(services: ServiceRegistry = Depends(get_services)):
    providers = services.oidc_service.list_providers()
    return [OIDCProviderInfo(**provider) for provider in providers]


@router.get("/auth/oidc/login/{provider_name}")
async def oidc_login(
    provider_name: str,
    services: ServiceRegistry = Depends(get_services),
):
    try:
        auth_url, state = services.oidc_service.initiate_login(provider_name)
        return {"authorization_url": auth_url, "state": state}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/auth/oidc/callback/{provider_name}")
async def oidc_callback(
    provider_name: str,
    code: str,
    state: str,
    request: Request,
    services: ServiceRegistry = Depends(get_services),
):
    try:
        user_id, error = services.oidc_service.handle_callback(provider_name, code, state)
        if error:
            raise HTTPException(status_code=400, detail=error)

        user = services.auth_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account disabled")

        if services.auth_service.user_requires_mfa(user.user_id):
            raise HTTPException(status_code=403, detail="MFA-enabled accounts are unsupported by this local API")

        if services.auth_service.password_change_required(user.user_id):
            raise HTTPException(status_code=403, detail="Password change required")

        ip_address = request.client.host if request.client else None
        session = services.auth_service.create_session(user, ip_address)

        services.audit_service.log_access(
            endpoint=f"/auth/oidc/callback/{provider_name}", method="GET",
            status_code=200, user_id=user.user_id, username=user.username,
            ip_address=ip_address,
        )

        return {
            "success": True,
            "session_id": session.session_id,
            "user": {
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
                "full_name": user.full_name,
            },
        }
    except StaleCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth callback failed: {e!s}")


@router.get("/auth/oidc/linked", response_model=List[OIDCLinkedProvider])
async def get_linked_providers(
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
):
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session, error = services.auth_service.validate_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail=error)

    providers = services.oidc_service.get_linked_providers(session.user_id)
    return [OIDCLinkedProvider(**provider) for provider in providers]


@router.post("/auth/oidc/unlink")
async def unlink_oidc_provider(
    request: Request,
    unlink_req: OIDCUnlinkRequest,
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
):
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session, error = services.auth_service.validate_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail=error)

    success = services.oidc_service.unlink_provider(session.user_id, unlink_req.provider_name)
    if not success:
        raise HTTPException(status_code=404, detail="Provider not linked")

    return {"success": True, "message": f"Unlinked {unlink_req.provider_name}"}
