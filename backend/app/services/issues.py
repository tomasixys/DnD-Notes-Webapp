from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.auth.enums import SystemRole, UserStatus
from app.auth.models import User
from app.models.api import (
    AdminIssueRead,
    IssueModerationUpdate,
    IssueReportCreate,
    KnownIssueRead,
    UserIssueRead,
)
from app.models.database import IssueReport
from app.models.enums import IssueStatus


class IssueReportService:
    def __init__(
        self,
        db: Session,
        user: User,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self.db = db
        self.user = user
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def list_known(self) -> list[KnownIssueRead]:
        reports = self.db.exec(
            select(IssueReport)
            .where(IssueReport.status == IssueStatus.ACKNOWLEDGED)
            .order_by(IssueReport.reviewed_at.desc(), IssueReport.id.desc())
        ).all()
        return [self._to_known_read(report) for report in reports]

    def list_mine(self) -> list[UserIssueRead]:
        reports = self.db.exec(
            select(IssueReport)
            .where(IssueReport.reporter_user_id == self.user.id)
            .order_by(IssueReport.created_at.desc(), IssueReport.id.desc())
        ).all()
        return [self._to_user_read(report) for report in reports]

    def list_for_admin(self) -> list[AdminIssueRead]:
        self._require_admin()
        reports = list(
            self.db.exec(
                select(IssueReport).order_by(
                    IssueReport.created_at.desc(),
                    IssueReport.id.desc(),
                )
            ).all()
        )
        status_order = {
            IssueStatus.PENDING: 0,
            IssueStatus.ACKNOWLEDGED: 1,
            IssueStatus.RESOLVED: 2,
            IssueStatus.REJECTED: 3,
        }
        reports.sort(key=lambda report: status_order[report.status])
        return [self._to_admin_read(report) for report in reports]

    def create(self, payload: IssueReportCreate) -> UserIssueRead:
        title = payload.title.strip()
        description = payload.description.strip()
        if len(title) < 3:
            raise HTTPException(
                status_code=400,
                detail="Issue title must contain at least 3 characters.",
            )
        if len(description) < 10:
            raise HTTPException(
                status_code=400,
                detail="Issue description must contain at least 10 characters.",
            )

        now = self.clock()
        report = IssueReport(
            title=title,
            description=description,
            reporter_user_id=self.user.id,
            created_at=now,
            updated_at=now,
        )
        self.db.add(report)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(report)
        return self._to_user_read(report)

    def moderate(
        self,
        report_id: int,
        payload: IssueModerationUpdate,
    ) -> AdminIssueRead:
        self._require_admin()
        report = self.db.exec(
            select(IssueReport)
            .where(IssueReport.id == report_id)
            .with_for_update()
        ).first()
        if report is None:
            raise HTTPException(status_code=404, detail="Issue report not found.")

        now = self.clock()
        report.status = payload.status
        report.review_note = payload.review_note.strip()
        report.reviewed_by_user_id = self.user.id
        report.reviewed_at = now
        report.updated_at = now
        self.db.add(report)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(report)
        return self._to_admin_read(report)

    def _require_admin(self) -> None:
        if (
            self.user.status is not UserStatus.ACTIVE
            or self.user.system_role is not SystemRole.ADMIN
        ):
            raise HTTPException(
                status_code=403,
                detail="System administrator privileges are required.",
            )

    @staticmethod
    def _to_known_read(report: IssueReport) -> KnownIssueRead:
        if report.id is None or report.reviewed_at is None:
            raise RuntimeError("Acknowledged issue is missing persisted metadata.")
        return KnownIssueRead(
            id=report.id,
            title=report.title,
            description=report.description,
            created_at=report.created_at,
            acknowledged_at=report.reviewed_at,
        )

    @staticmethod
    def _to_user_read(report: IssueReport) -> UserIssueRead:
        if report.id is None:
            raise RuntimeError("Issue report has not been persisted.")
        return UserIssueRead(
            id=report.id,
            title=report.title,
            description=report.description,
            status=report.status,
            review_note=report.review_note,
            created_at=report.created_at,
            updated_at=report.updated_at,
            reviewed_at=report.reviewed_at,
        )

    def _to_admin_read(self, report: IssueReport) -> AdminIssueRead:
        user = (
            self.db.get(User, report.reporter_user_id)
            if report.reporter_user_id is not None
            else None
        )
        reporter_username = user.username if user is not None else "deleted-user"
        reporter_display_name = (
            (user.display_name.strip() or user.username)
            if user is not None
            else "Deleted user"
        )
        return AdminIssueRead(
            **self._to_user_read(report).model_dump(),
            reporter_username=reporter_username,
            reporter_display_name=reporter_display_name,
        )
