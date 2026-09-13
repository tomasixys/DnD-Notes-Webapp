import unittest
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from sqlalchemy import event, inspect, text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.auth.enums import SystemRole
from app.authorization.route_audit import audit_campaign_route_authorization
from app.migrations import PORTABLE_HEAD_REVISION, run_database_migrations
from app.migrations.v7 import migrate_to_v7
from app.models.api import IssueModerationUpdate, IssueReportCreate
from app.models.enums import IssueStatus
from app.routers import issues
from app.services.issues import IssueReportService
from tests.authorization_helpers import create_user


NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


class IssueReportServiceTests(unittest.TestCase):
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

    @staticmethod
    def payload() -> IssueReportCreate:
        return IssueReportCreate(
            title="Session list does not scroll",
            description="The session list stops at its lower boundary.",
        )

    def test_pending_report_is_private_to_reporter_and_admin(self):
        with Session(self.engine) as db:
            reporter = create_user(db)
            reporter.display_name = "Nalia Player"
            other = create_user(db)
            admin = create_user(db, role=SystemRole.ADMIN)

            created = IssueReportService(
                db,
                reporter,
                clock=lambda: NOW,
            ).create(self.payload())

            self.assertEqual(IssueStatus.PENDING, created.status)
            self.assertEqual([], IssueReportService(db, other).list_mine())
            self.assertEqual([], IssueReportService(db, other).list_known())
            self.assertEqual(
                [created.id],
                [item.id for item in IssueReportService(db, reporter).list_mine()],
            )
            admin_report = IssueReportService(db, admin).list_for_admin()[0]
            self.assertEqual("Nalia Player", admin_report.reporter_display_name)
            self.assertEqual(reporter.username, admin_report.reporter_username)

    def test_acknowledged_report_is_public_without_reporter_identity(self):
        with Session(self.engine) as db:
            reporter = create_user(db)
            reader = create_user(db)
            admin = create_user(db, role=SystemRole.ADMIN)
            created = IssueReportService(
                db,
                reporter,
                clock=lambda: NOW,
            ).create(self.payload())

            reviewed_at = NOW + timedelta(minutes=5)
            IssueReportService(
                db,
                admin,
                clock=lambda: reviewed_at,
            ).moderate(
                created.id,
                IssueModerationUpdate(
                    status=IssueStatus.ACKNOWLEDGED,
                    review_note="Confirmed in Firefox.",
                ),
            )

            known = IssueReportService(db, reader).list_known()
            self.assertEqual([created.id], [item.id for item in known])
            self.assertEqual(
                reviewed_at.replace(tzinfo=None),
                known[0].acknowledged_at,
            )
            public_fields = known[0].model_dump()
            self.assertNotIn("reporter_username", public_fields)
            self.assertNotIn("reporter_user_id", public_fields)
            self.assertNotIn("review_note", public_fields)
            mine = IssueReportService(db, reporter).list_mine()[0]
            self.assertEqual("Confirmed in Firefox.", mine.review_note)

    def test_resolved_or_rejected_reports_are_not_known_issues(self):
        with Session(self.engine) as db:
            reporter = create_user(db)
            admin = create_user(db, role=SystemRole.ADMIN)
            service = IssueReportService(db, reporter, clock=lambda: NOW)
            resolved = service.create(self.payload())
            rejected = service.create(IssueReportCreate(
                title="Expected behavior",
                description="This report is not actually a product defect.",
            ))
            admin_service = IssueReportService(db, admin, clock=lambda: NOW)
            admin_service.moderate(
                resolved.id,
                IssueModerationUpdate(status=IssueStatus.RESOLVED),
            )
            admin_service.moderate(
                rejected.id,
                IssueModerationUpdate(status=IssueStatus.REJECTED),
            )

            self.assertEqual([], service.list_known())

    def test_non_admin_cannot_moderate_or_list_all_reports(self):
        with Session(self.engine) as db:
            reporter = create_user(db)
            created = IssueReportService(db, reporter).create(self.payload())
            service = IssueReportService(db, reporter)

            with self.assertRaises(HTTPException) as list_error:
                service.list_for_admin()
            self.assertEqual(403, list_error.exception.status_code)

            with self.assertRaises(HTTPException) as update_error:
                service.moderate(
                    created.id,
                    IssueModerationUpdate(
                        status=IssueStatus.ACKNOWLEDGED,
                    ),
                )
            self.assertEqual(403, update_error.exception.status_code)

    def test_trimmed_content_must_still_meet_minimum_length(self):
        with Session(self.engine) as db:
            reporter = create_user(db)
            service = IssueReportService(db, reporter)

            with self.assertRaises(HTTPException) as error:
                service.create(IssueReportCreate(
                    title="   ",
                    description="A sufficiently long description.",
                ))
            self.assertEqual(400, error.exception.status_code)


class IssueReportMigrationTests(unittest.TestCase):
    def test_v7_creates_issue_report_table_and_indexes(self):
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                connection.execute(text(
                    "CREATE TABLE app_user (id INTEGER NOT NULL PRIMARY KEY)"
                ))
                migrate_to_v7(connection)

                inspector = inspect(connection)
                self.assertIn("issue_report", inspector.get_table_names())
                self.assertEqual(
                    {
                        "ix_issue_report_status",
                        "ix_issue_report_reporter_user_id",
                        "ix_issue_report_reviewed_by_user_id",
                    },
                    {
                        index["name"]
                        for index in inspector.get_indexes("issue_report")
                    },
                )
        finally:
            engine.dispose()

    def test_portable_upgrade_adds_issue_reports_after_roll_migration(self):
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                connection.execute(text(
                    "CREATE TABLE app_user (id INTEGER NOT NULL PRIMARY KEY)"
                ))
                connection.execute(text(
                    "CREATE TABLE alembic_version ("
                    "version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
                ))
                connection.execute(text(
                    "INSERT INTO alembic_version (version_num) "
                    "VALUES ('0003_add_roll_user')"
                ))

            run_database_migrations(engine)

            self.assertIn("issue_report", inspect(engine).get_table_names())
            with engine.begin() as connection:
                revision = connection.execute(text(
                    "SELECT version_num FROM alembic_version"
                )).scalar_one()
            self.assertEqual(PORTABLE_HEAD_REVISION, revision)
        finally:
            engine.dispose()

    def test_issue_routes_pass_authentication_audit(self):
        application = FastAPI()
        application.include_router(issues.router)
        audit_campaign_route_authorization(application)


if __name__ == "__main__":
    unittest.main()
