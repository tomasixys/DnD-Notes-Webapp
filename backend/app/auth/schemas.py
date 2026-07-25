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


class SessionMutationRead(SQLModel):
    message: str
    revoked_sessions: int
