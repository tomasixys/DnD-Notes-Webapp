from datetime import datetime, timedelta, timezone
import unittest

from argon2 import PasswordHasher
from fastapi import HTTPException, Response
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from starlette.requests import Request

from app import database as database_module
from app.auth.administration import IdentityBootstrapService
from app.auth.dependencies import AuthContext, require_csrf_context
from app.auth.enums import SystemRole, UserStatus
from app.auth.login import AuthenticationService
from app.auth.middleware import authorize_hosted_api_request
from app.auth.models import AuthSession, PasswordCredential, User
from app.auth.passwords import CredentialService
from app.auth.router import INVALID_CREDENTIALS, current_session, login
from app.auth.schemas import LoginRequest
from app.auth.sessions import AuthSessionService, token_digest
from app.config import ApplicationSettings


NOW = datetime(2026, 7, 25, 18, 0, tzinfo=timezone.utc)
PASSWORD = "correct horse battery staple"


def test_hasher() -> PasswordHasher:
    return PasswordHasher(
        time_cost=1,
        memory_cost=8192,
        parallelism=1,
    )


def hosted_settings() -> ApplicationSettings:
    return ApplicationSettings.model_validate(
        {
            "installation": {"mode": "hosted"},
            "database": {"url_env": "DND_NOTES_DATABASE_URL"},
            "storage": {
                "backend": "object",
                "endpoint": "https://objects.example.test",
                "bucket": "dnd-notes",
                "access_key_env": "DND_NOTES_STORAGE_ACCESS_KEY",
                "secret_key_env": "DND_NOTES_STORAGE_SECRET_KEY",
            },
            "security": {
                "session_secret_env": "DND_NOTES_SESSION_SECRET",
            },
            "server": {
                "public_origin": "https://notes.example.test",
                "open_browser": False,
                "trusted_hosts": ["notes.example.test"],
            },
        }
    )


def request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/login",
            "headers": [(b"user-agent", b"auth-test")],
            "client": ("192.0.2.10", 12345),
            "scheme": "https",
            "server": ("notes.example.test", 443),
        }
    )


def protected_request(
    method: str,
    *,
    cookie: str | None = None,
    csrf_token: str | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookie is not None:
        headers.append((b"cookie", cookie.encode("ascii")))
    if csrf_token is not None:
        headers.append(
            (b"x-csrf-token", csrf_token.encode("ascii"))
        )
    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/api/protected",
            "headers": headers,
            "client": ("192.0.2.10", 12345),
            "scheme": "https",
            "server": ("notes.example.test", 443),
        }
    )


class AuthenticationDatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        SQLModel.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def add_user(
        self,
        db: Session,
        *,
        username: str = "keeper",
        status: UserStatus = UserStatus.ACTIVE,
    ) -> tuple[User, PasswordCredential]:
        user = User(
            username=username,
            normalized_username=username.casefold(),
            status=status,
            system_role=SystemRole.ADMIN,
        )
        db.add(user)
        db.flush()
        credential = CredentialService(
            db,
            password_hasher=test_hasher(),
            clock=lambda: NOW,
        ).set_password(
            user,
            PASSWORD,
            revoke_sessions=False,
        )
        db.commit()
        return user, credential


class AuthenticationServiceTests(AuthenticationDatabaseTestCase):
    def test_repeated_failures_lock_then_allow_login_after_expiry(self):
        current_time = [NOW]
        with Session(self.engine) as db:
            user, credential = self.add_user(db)
            hasher = test_hasher()
            service = AuthenticationService(
                db,
                password_hasher=hasher,
                dummy_password_hash=hasher.hash("dummy password value"),
                clock=lambda: current_time[0],
                failure_limit=3,
                initial_lock_seconds=30,
                maximum_lock_seconds=60,
            )

            for _ in range(3):
                self.assertIsNone(
                    service.authenticate("keeper", "wrong password")
                )
            db.commit()
            db.refresh(credential)

            self.assertIsNotNone(credential.locked_until)
            self.assertIsNone(
                service.authenticate("keeper", PASSWORD)
            )

            current_time[0] = NOW + timedelta(seconds=31)
            self.assertEqual(
                user.id,
                service.authenticate("KEEPER", PASSWORD).id,
            )
            db.commit()
            db.refresh(credential)
            self.assertEqual(0, credential.failed_attempts)
            self.assertIsNone(credential.locked_until)

    def test_unknown_and_suspended_users_receive_no_identity(self):
        with Session(self.engine) as db:
            self.add_user(
                db,
                username="suspended",
                status=UserStatus.SUSPENDED,
            )
            hasher = test_hasher()
            service = AuthenticationService(
                db,
                password_hasher=hasher,
                dummy_password_hash=hasher.hash("dummy password value"),
                clock=lambda: NOW,
            )

            self.assertIsNone(
                service.authenticate("missing-user", PASSWORD)
            )
            self.assertIsNone(
                service.authenticate("suspended", PASSWORD)
            )

    def test_lock_growth_is_capped(self):
        with Session(self.engine) as db:
            _, credential = self.add_user(db)
            credential.failed_attempts = 1000
            hasher = test_hasher()
            service = AuthenticationService(
                db,
                password_hasher=hasher,
                dummy_password_hash=hasher.hash("dummy password value"),
                clock=lambda: NOW,
                failure_limit=3,
                initial_lock_seconds=30,
                maximum_lock_seconds=60,
            )

            self.assertIsNone(
                service.authenticate("keeper", "wrong password")
            )
            self.assertEqual(
                NOW + timedelta(seconds=60),
                credential.locked_until,
            )


class AuthSessionServiceTests(AuthenticationDatabaseTestCase):
    def test_opaque_session_is_digest_backed_idle_and_absolute_limited(self):
        current_time = [NOW]
        generated = iter(("session-secret", "csrf-secret"))
        with Session(self.engine) as db:
            user, _ = self.add_user(db)
            service = AuthSessionService(
                db,
                clock=lambda: current_time[0],
                idle_lifetime_minutes=10,
                absolute_lifetime_minutes=20,
                token_factory=lambda size: next(generated),
            )

            issued = service.create(user, client_ip="192.0.2.10")
            db.commit()

            self.assertEqual(
                token_digest("session-secret"),
                issued.session.token_digest,
            )
            self.assertNotIn(
                "session-secret",
                issued.session.token_digest,
            )
            self.assertTrue(
                service.validate_csrf(
                    issued.session,
                    "csrf-secret",
                )
            )
            self.assertFalse(
                service.validate_csrf(issued.session, "wrong")
            )

            current_time[0] = NOW + timedelta(minutes=5)
            self.assertIsNotNone(service.resolve("session-secret"))
            self.assertEqual(
                NOW + timedelta(minutes=15),
                issued.session.expires_at,
            )

            current_time[0] = NOW + timedelta(minutes=21)
            self.assertIsNone(service.resolve("session-secret"))
            self.assertIsNotNone(issued.session.revoked_at)

    def test_logout_all_revokes_only_active_user_sessions(self):
        with Session(self.engine) as db:
            user, _ = self.add_user(db)
            other, _ = self.add_user(db, username="other")
            generated = iter(
                (
                    "session-one",
                    "csrf-one",
                    "session-two",
                    "csrf-two",
                )
            )
            service = AuthSessionService(
                db,
                clock=lambda: NOW,
                token_factory=lambda size: next(generated),
            )
            first = service.create(user)
            second = service.create(other)

            self.assertEqual(1, service.revoke_all(user.id))
            self.assertIsNotNone(first.session.revoked_at)
            self.assertIsNone(second.session.revoked_at)


class AuthenticationRouterFoundationTests(
    AuthenticationDatabaseTestCase
):
    def test_local_session_bootstraps_without_login_or_csrf(self):
        with Session(self.engine) as db:
            local_user = IdentityBootstrapService(db).ensure_local_user()
            result = current_session(
                request=protected_request("GET"),
                settings=ApplicationSettings(),
                db=db,
            )

            self.assertEqual(local_user.id, result.user.id)
            self.assertFalse(result.authentication_required)
            self.assertEqual("", result.csrf_token)

    def test_login_sets_host_only_secure_http_only_cookie(self):
        with Session(self.engine) as db:
            user, credential = self.add_user(db)
            response = Response()

            result = login(
                payload=LoginRequest(
                    username=user.username,
                    password=PASSWORD,
                ),
                request=request(),
                response=response,
                settings=hosted_settings(),
                session_secret="s" * 32,
                db=db,
            )

            self.assertEqual(user.id, result.user.id)
            self.assertTrue(result.authentication_required)
            self.assertTrue(result.csrf_token)
            set_cookie = response.headers["set-cookie"]
            self.assertIn("__Host-dnd_notes_session=", set_cookie)
            self.assertIn("HttpOnly", set_cookie)
            self.assertIn("Secure", set_cookie)
            self.assertIn("SameSite=lax", set_cookie)
            self.assertNotIn(PASSWORD, set_cookie)
            db.refresh(credential)
            self.assertTrue(
                credential.password_hash.startswith("$argon2id$")
            )

    def test_login_error_is_generic_and_csrf_is_session_bound(self):
        with Session(self.engine) as db:
            user, _ = self.add_user(db)
            with self.assertRaises(HTTPException) as error:
                login(
                    payload=LoginRequest(
                        username=user.username,
                        password="wrong password",
                    ),
                    request=request(),
                    response=Response(),
                    settings=hosted_settings(),
                    session_secret="s" * 32,
                    db=db,
                )
            self.assertEqual(401, error.exception.status_code)
            self.assertEqual(
                INVALID_CREDENTIALS,
                error.exception.detail,
            )

            generated = iter(("session-token", "csrf-token"))
            service = AuthSessionService(
                db,
                clock=lambda: NOW,
                token_factory=lambda size: next(generated),
            )
            issued = service.create(user)
            context = AuthContext(
                session=issued.session,
                user=user,
                service=service,
            )
            with self.assertRaises(HTTPException) as csrf_error:
                require_csrf_context(
                    context=context,
                    csrf_token="wrong-token",
                )
            self.assertEqual(403, csrf_error.exception.status_code)
            self.assertIs(
                context,
                require_csrf_context(
                    context=context,
                    csrf_token=issued.csrf_token,
                ),
            )


class HostedAuthenticationMiddlewareTests(
    AuthenticationDatabaseTestCase
):
    def test_data_api_requires_session_and_csrf_but_auth_api_is_public(self):
        previous_engine = database_module._engine
        database_module._engine = self.engine
        try:
            with Session(self.engine) as db:
                user, _ = self.add_user(db)
                generated = iter(("session-token", "csrf-token"))
                AuthSessionService(
                    db,
                    clock=lambda: NOW,
                    token_factory=lambda size: next(generated),
                ).create(user)
                db.commit()

            settings = hosted_settings()
            cookie = (
                f"{settings.security.cookie_name}=session-token"
            )
            anonymous = authorize_hosted_api_request(
                protected_request("GET"),
                settings,
            )
            self.assertEqual(401, anonymous.status_code)
            self.assertIsNone(
                authorize_hosted_api_request(
                    protected_request("GET", cookie=cookie),
                    settings,
                )
            )
            missing_csrf = authorize_hosted_api_request(
                protected_request("POST", cookie=cookie),
                settings,
            )
            self.assertEqual(403, missing_csrf.status_code)
            self.assertIsNone(
                authorize_hosted_api_request(
                    protected_request(
                        "POST",
                        cookie=cookie,
                        csrf_token="csrf-token",
                    ),
                    settings,
                )
            )
        finally:
            database_module._engine = previous_engine


if __name__ == "__main__":
    unittest.main()
