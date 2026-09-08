from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.auth.enums import SecurityEventType, SystemRole, UserStatus
from app.auth.events import SecurityEventService
from app.auth.models import AuthSession, User
from app.authorization.models import CampaignMembership


class IdentityAdminOperationsError(RuntimeError):
    pass


class IdentityAdminOperationsService:
    """Audited account and session controls for system administrators."""

    def __init__(self, db: Session, actor: User):
        self.db = db
        self.actor = actor
        self.events = SecurityEventService(db)

    def list_users(self) -> list[tuple[User, int, int]]:
        self._require_admin()
        users = self.db.exec(select(User).order_by(User.username)).all()
        return [
            (
                user,
                self._count_active_sessions(user.id),
                self._count_memberships(user.id),
            )
            for user in users
        ]

    def set_status(
        self,
        user_id: int,
        status: UserStatus,
        reason: str,
    ) -> tuple[User, int]:
        self._require_reason(reason)
        user = self._get_manageable_user(user_id)
        if status not in {UserStatus.ACTIVE, UserStatus.SUSPENDED}:
            raise IdentityAdminOperationsError(
                "Administrators may only activate or suspend accounts."
            )
        if user.status in {UserStatus.PENDING, UserStatus.DELETED}:
            raise IdentityAdminOperationsError(
                "Pending or deleted accounts cannot be changed here."
            )
        user.status = status
        user.updated_at = datetime.now(timezone.utc)
        revoked = 0
        if status is UserStatus.SUSPENDED:
            revoked = self._revoke_user_sessions(user.id)
        self.db.add(user)
        self._record(
            user.id,
            reason,
            f"account_status_changed:{status.value}",
        )
        self.db.commit()
        self.db.refresh(user)
        return user, revoked

    def revoke_user_sessions(self, user_id: int, reason: str) -> int:
        self._require_reason(reason)
        user = self._get_manageable_user(user_id, allow_self=True)
        revoked = self._revoke_user_sessions(user.id)
        self._record(user.id, reason, "user_sessions_revoked")
        self.db.commit()
        return revoked

    def set_role(
        self, user_id: int, role: SystemRole, reason: str,
    ) -> tuple[User, int]:
        self._require_admin()
        self._require_reason(reason)
        # Serialize role changes, then recheck the acting administrator after
        # taking the locks so concurrent demotions cannot remove every admin.
        self.db.exec(select(User).where(
            User.system_role == SystemRole.ADMIN,
        ).order_by(User.id).with_for_update()).all()
        self.db.refresh(self.actor)
        user = self._get_manageable_user(user_id)
        if role not in {SystemRole.USER, SystemRole.ADMIN}:
            raise IdentityAdminOperationsError("Choose user or administrator.")
        if user.status is not UserStatus.ACTIVE or not user.can_login:
            raise IdentityAdminOperationsError("Only active login accounts can change role.")
        user.system_role = role
        user.updated_at = datetime.now(timezone.utc)
        revoked = self._revoke_user_sessions(user.id)
        self.db.add(user)
        self._record(user.id, reason, f"system_role_changed:{role.value}")
        self.db.commit()
        self.db.refresh(user)
        return user, revoked

    def revoke_all_sessions(self, reason: str) -> int:
        self._require_admin()
        self._require_reason(reason)
        sessions = self.db.exec(
            select(AuthSession).where(AuthSession.revoked_at.is_(None))
        ).all()
        now = datetime.now(timezone.utc)
        for auth_session in sessions:
            auth_session.revoked_at = now
            self.db.add(auth_session)
        self._record(None, reason, "all_sessions_revoked")
        self.db.commit()
        return len(sessions)

    def _get_manageable_user(
        self,
        user_id: int,
        *,
        allow_self: bool = False,
    ) -> User:
        self._require_admin()
        user = self.db.exec(
            select(User).where(User.id == user_id).with_for_update()
        ).first()
        if user is None:
            raise IdentityAdminOperationsError("User not found.")
        if user.system_role is SystemRole.CUSTODIAN:
            raise IdentityAdminOperationsError(
                "The non-login custodian account cannot be changed."
            )
        if not allow_self and user.id == self.actor.id:
            raise IdentityAdminOperationsError(
                "Administrators cannot change their own status or role."
            )
        return user

    def _revoke_user_sessions(self, user_id: int) -> int:
        sessions = self.db.exec(
            select(AuthSession).where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            )
        ).all()
        now = datetime.now(timezone.utc)
        for auth_session in sessions:
            auth_session.revoked_at = now
            self.db.add(auth_session)
        return len(sessions)

    def _count_active_sessions(self, user_id: int) -> int:
        return int(
            self.db.exec(
                select(func.count(AuthSession.id)).where(
                    AuthSession.user_id == user_id,
                    AuthSession.revoked_at.is_(None),
                )
            ).one()
        )

    def _count_memberships(self, user_id: int) -> int:
        return int(
            self.db.exec(
                select(func.count(CampaignMembership.id)).where(
                    CampaignMembership.user_id == user_id
                )
            ).one()
        )

    def _require_admin(self) -> None:
        if (
            self.actor.status is not UserStatus.ACTIVE
            or self.actor.system_role is not SystemRole.ADMIN
        ):
            raise IdentityAdminOperationsError(
                "System administrator privileges are required."
            )

    @staticmethod
    def _require_reason(reason: str) -> None:
        if not reason.strip():
            raise IdentityAdminOperationsError(
                "An administrative reason is required."
            )

    def _record(
        self,
        user_id: int | None,
        reason: str,
        action: str,
    ) -> None:
        self.events.record(
            SecurityEventType.MEMBERSHIP_CHANGED,
            user_id=user_id,
            actor_user_id=self.actor.id,
            reason=f"scope=system action={action}; {reason.strip()}",
            used_elevation=True,
        )
