from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import SecretStr
from sqlmodel import SQLModel

from app.auth.enums import SystemRole, UserStatus

if TYPE_CHECKING:
    from app.auth.models import User


class LoginRequest(SQLModel):
    username: str
    password: SecretStr


class AuthUserRead(SQLModel):
    id: int
    username: str
    display_name: str
    status: UserStatus
    system_role: SystemRole

    @classmethod
    def from_user(cls, user: "User") -> "AuthUserRead":
        return cls(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            status=user.status,
            system_role=user.system_role,
        )


class AuthSessionRead(SQLModel):
    user: AuthUserRead
    csrf_token: str
    authentication_required: bool = True


class SessionMutationRead(SQLModel):
    message: str
    revoked_sessions: int


class AdminUserRead(AuthUserRead):
    active_sessions: int
    campaign_memberships: int

    @classmethod
    def from_user(
        cls,
        user: "User",
        *,
        active_sessions: int,
        campaign_memberships: int,
    ) -> "AdminUserRead":
        return cls(
            **AuthUserRead.from_user(user).model_dump(),
            active_sessions=active_sessions,
            campaign_memberships=campaign_memberships,
        )


class AdminUserStatusUpdate(SQLModel):
    status: UserStatus
    reason: str


class AdminSessionRevocationRequest(SQLModel):
    reason: str


class AdminUserRoleUpdate(SQLModel):
    system_role: SystemRole
    reason: str


class InviteUserRequest(SQLModel):
    username: str = ""
    display_name: str = ""


class AccountTokenRequest(SQLModel):
    token: SecretStr
    password: SecretStr


class AccountActivationRequest(AccountTokenRequest):
    username: str | None = None
    display_name: str = ""


class IssuedAccountTokenRead(SQLModel):
    user: AuthUserRead
    token: str
    expires_at: datetime


class AccountMutationRead(SQLModel):
    user: AuthUserRead
    message: str
