from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.auth.enums import (
    AccountTokenPurpose,
    SecurityEventType,
    SystemRole,
    UserStatus,
)
from app.auth.events import SecurityEventService
from app.auth.models import AccountToken, PasswordCredential, User
from app.authorization.enums import CampaignRole
from app.authorization.models import CampaignMembership
from app.models.database import Campaign
from app.auth.passwords import (
    CredentialService,
    normalize_username,
    utc_now,
)


ACCOUNT_TOKEN_BYTES = 32


class AccountLifecycleError(RuntimeError):
    """Raised when an account-management operation is invalid or unsafe."""


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def account_token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IssuedAccountToken:
    user: User
    token: str
    expires_at: datetime


class AccountLifecycleService:
    def __init__(
        self,
        db: Session,
        *,
        password_hasher: PasswordHasher | None = None,
        clock: Callable[[], datetime] | None = None,
        token_factory: Callable[[int], str] | None = None,
    ):
        self.db = db
        self.clock = clock or utc_now
        self.token_factory = token_factory or secrets.token_urlsafe
        self.credentials = CredentialService(
            db,
            password_hasher=password_hasher,
            clock=self.clock,
        )
        self.events = SecurityEventService(db, clock=self.clock)

    def invite_user(
        self,
        actor: User,
        username: str,
        *,
        display_name: str = "",
        lifetime_minutes: int,
    ) -> IssuedAccountToken:
        self._require_admin(actor)
        normalized = normalize_username(username)
        if self._find_user(normalized) is not None:
            raise AccountLifecycleError("That username is already in use.")
        now = self.clock()
        user = User(
            username=username.strip(),
            normalized_username=normalized,
            display_name=display_name.strip(),
            status=UserStatus.PENDING,
            system_role=SystemRole.USER,
            can_login=True,
            created_at=now,
            updated_at=now,
        )
        self.db.add(user)
        self.db.flush()
        issued = self._issue_token(
            user,
            AccountTokenPurpose.ACTIVATION,
            actor=actor,
            lifetime_minutes=lifetime_minutes,
        )
        self.events.record(
            SecurityEventType.USER_INVITED,
            user_id=user.id,
            actor_user_id=actor.id,
        )
        self._commit("The invitation could not be created.")
        self.db.refresh(user)
        return issued

    def activate(
        self,
        raw_token: str,
        password: str,
    ) -> User:
        token, user = self._resolve_token(
            raw_token,
            AccountTokenPurpose.ACTIVATION,
        )
        if user.status is not UserStatus.PENDING or not user.can_login:
            raise AccountLifecycleError("Invalid or expired account token.")
        self.credentials.set_password(
            user,
            password,
            revoke_sessions=False,
        )
        now = self.clock()
        user.status = UserStatus.ACTIVE
        user.updated_at = now
        token.consumed_at = now
        self.db.add(user)
        self.db.add(token)
        self.events.record(
            SecurityEventType.ACCOUNT_ACTIVATED,
            user_id=user.id,
        )
        self.db.commit()
        self.db.refresh(user)
        return user

    def issue_password_reset(
        self,
        actor: User,
        user_id: int,
        *,
        lifetime_minutes: int,
    ) -> IssuedAccountToken:
        self._require_admin(actor)
        user = self.db.exec(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
        ).first()
        if (
            user is None
            or user.status is not UserStatus.ACTIVE
            or not user.can_login
            or user.system_role is SystemRole.CUSTODIAN
        ):
            raise AccountLifecycleError(
                "No resettable account has that identifier."
            )
        issued = self._issue_token(
            user,
            AccountTokenPurpose.PASSWORD_RESET,
            actor=actor,
            lifetime_minutes=lifetime_minutes,
        )
        self.events.record(
            SecurityEventType.PASSWORD_RESET_REQUESTED,
            user_id=user.id,
            actor_user_id=actor.id,
        )
        self.db.commit()
        return issued

    def reset_password(
        self,
        raw_token: str,
        password: str,
    ) -> User:
        token, user = self._resolve_token(
            raw_token,
            AccountTokenPurpose.PASSWORD_RESET,
        )
        if (
            user.status is not UserStatus.ACTIVE
            or not user.can_login
            or user.system_role is SystemRole.CUSTODIAN
        ):
            raise AccountLifecycleError("Invalid or expired account token.")
        self.credentials.set_password(user, password)
        now = self.clock()
        user.updated_at = now
        token.consumed_at = now
        self.db.add(user)
        self.db.add(token)
        self.events.record(
            SecurityEventType.PASSWORD_RESET_COMPLETED,
            user_id=user.id,
        )
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, actor: User, user_id: int) -> User:
        self._require_admin(actor)
        if actor.id == user_id:
            raise AccountLifecycleError(
                "Administrators cannot delete their own active account."
            )
        user = self.db.exec(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
        ).first()
        if user is None or user.status is UserStatus.DELETED:
            raise AccountLifecycleError(
                "No deletable account has that identifier."
            )
        if user.system_role is SystemRole.CUSTODIAN:
            raise AccountLifecycleError(
                "The system custodian cannot be deleted."
            )

        now = self.clock()
        self._release_campaign_memberships(user, actor)
        self.credentials.revoke_sessions(user_id, revoked_at=now)
        credential = self.db.get(PasswordCredential, user_id)
        if credential is not None:
            self.db.delete(credential)
        active_tokens = self.db.exec(
            select(AccountToken).where(
                AccountToken.user_id == user_id,
                AccountToken.consumed_at.is_(None),
            )
        ).all()
        for token in active_tokens:
            token.consumed_at = now
            self.db.add(token)
        user.status = UserStatus.DELETED
        user.can_login = False
        user.deleted_at = now
        user.updated_at = now
        self.db.add(user)
        self.events.record(
            SecurityEventType.ACCOUNT_DELETED,
            user_id=user.id,
            actor_user_id=actor.id,
        )
        self.db.commit()
        self.db.refresh(user)
        return user

    def _release_campaign_memberships(
        self,
        user: User,
        actor: User,
    ) -> None:
        memberships = self.db.exec(
            select(CampaignMembership).where(
                CampaignMembership.user_id == user.id
            )
        ).all()
        for membership in memberships:
            if membership.role is CampaignRole.OWNER:
                another_owner = self.db.exec(
                    select(CampaignMembership.id)
                    .join(User, User.id == CampaignMembership.user_id)
                    .where(
                        CampaignMembership.campaign_id
                        == membership.campaign_id,
                        CampaignMembership.role == CampaignRole.OWNER,
                        CampaignMembership.is_custodial.is_(False),
                        CampaignMembership.user_id != user.id,
                        User.status == UserStatus.ACTIVE,
                        User.can_login.is_(True),
                    )
                    .limit(1)
                ).first()
                if another_owner is None:
                    self._assign_campaign_custody(
                        membership.campaign_id,
                        actor,
                    )
            self.db.delete(membership)

    def _assign_campaign_custody(
        self,
        campaign_id: int,
        actor: User,
    ) -> None:
        custodian = self.db.exec(
            select(User).where(
                User.system_role == SystemRole.CUSTODIAN,
                User.status == UserStatus.ACTIVE,
                User.can_login.is_(False),
            )
        ).first()
        campaign = self.db.get(Campaign, campaign_id)
        if custodian is None or campaign is None:
            raise AccountLifecycleError(
                "Campaign custody cannot be assigned safely."
            )
        membership = self.db.exec(
            select(CampaignMembership).where(
                CampaignMembership.campaign_id == campaign_id,
                CampaignMembership.user_id == custodian.id,
            )
        ).first()
        if membership is None:
            membership = CampaignMembership(
                campaign_id=campaign_id,
                user_id=custodian.id,
                role=CampaignRole.OWNER,
                is_custodial=True,
            )
        else:
            membership.role = CampaignRole.OWNER
            membership.is_custodial = True
            membership.assigned_character_person_id = None
            membership.active_character_person_id = None
        campaign.orphaned = True
        self.db.add(membership)
        self.db.add(campaign)
        self.events.record(
            SecurityEventType.CAMPAIGN_CUSTODY_ASSIGNED,
            user_id=custodian.id,
            actor_user_id=actor.id,
            campaign_id=campaign_id,
        )

    def _issue_token(
        self,
        user: User,
        purpose: AccountTokenPurpose,
        *,
        actor: User,
        lifetime_minutes: int,
    ) -> IssuedAccountToken:
        now = self.clock()
        previous_tokens = self.db.exec(
            select(AccountToken).where(
                AccountToken.user_id == user.id,
                AccountToken.purpose == purpose,
                AccountToken.consumed_at.is_(None),
            )
        ).all()
        for previous in previous_tokens:
            previous.consumed_at = now
            self.db.add(previous)

        raw_token = self.token_factory(ACCOUNT_TOKEN_BYTES)
        expires_at = now + timedelta(minutes=lifetime_minutes)
        token = AccountToken(
            user_id=user.id,
            purpose=purpose,
            token_digest=account_token_digest(raw_token),
            created_at=now,
            expires_at=expires_at,
            created_by_user_id=actor.id,
        )
        self.db.add(token)
        self.db.flush()
        return IssuedAccountToken(
            user=user,
            token=raw_token,
            expires_at=expires_at,
        )

    def _resolve_token(
        self,
        raw_token: str,
        purpose: AccountTokenPurpose,
    ) -> tuple[AccountToken, User]:
        if not raw_token:
            raise AccountLifecycleError("Invalid or expired account token.")
        token = self.db.exec(
            select(AccountToken)
            .where(
                AccountToken.token_digest
                == account_token_digest(raw_token),
                AccountToken.purpose == purpose,
            )
            .with_for_update()
        ).first()
        now = self.clock()
        if (
            token is None
            or token.consumed_at is not None
            or as_utc(token.expires_at) <= as_utc(now)
        ):
            raise AccountLifecycleError("Invalid or expired account token.")
        user = self.db.exec(
            select(User)
            .where(User.id == token.user_id)
            .with_for_update()
        ).first()
        if user is None:
            raise AccountLifecycleError("Invalid or expired account token.")
        return token, user

    def _find_user(self, normalized_username: str) -> User | None:
        return self.db.exec(
            select(User).where(
                User.normalized_username == normalized_username
            )
        ).first()

    @staticmethod
    def _require_admin(actor: User) -> None:
        if (
            actor.status is not UserStatus.ACTIVE
            or not actor.can_login
            or actor.system_role is not SystemRole.ADMIN
        ):
            raise AccountLifecycleError(
                "System administrator privileges are required."
            )

    def _commit(self, message: str) -> None:
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise AccountLifecycleError(message) from error
