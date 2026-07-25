from pydantic import SecretStr
from sqlmodel import SQLModel

from app.models.enums import SystemRole, UserStatus


class LoginRequest(SQLModel):
    username: str
    password: SecretStr


class AuthUserRead(SQLModel):
    id: int
    username: str
    display_name: str
    status: UserStatus
    system_role: SystemRole


class AuthSessionRead(SQLModel):
    user: AuthUserRead
    csrf_token: str


class SessionMutationRead(SQLModel):
    message: str
    revoked_sessions: int
