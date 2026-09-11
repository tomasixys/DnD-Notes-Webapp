from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.auth.dependencies import require_current_user
from app.auth.models import User
from app.database import get_session
from app.models.api import (
    AdminIssueRead,
    IssueModerationUpdate,
    IssueReportCreate,
    KnownIssueRead,
    UserIssueRead,
)
from app.services.issues import IssueReportService


router = APIRouter(prefix="/api/issues", tags=["issues"])


@router.get("/known")
def list_known_issues(
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
) -> list[KnownIssueRead]:
    return IssueReportService(db, user).list_known()


@router.get("/mine")
def list_my_issue_reports(
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
) -> list[UserIssueRead]:
    return IssueReportService(db, user).list_mine()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_issue_report(
    payload: IssueReportCreate,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
) -> UserIssueRead:
    return IssueReportService(db, user).create(payload)


@router.get("/admin")
def list_issue_reports_for_admin(
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
) -> list[AdminIssueRead]:
    return IssueReportService(db, user).list_for_admin()


@router.put("/admin/{report_id}")
def moderate_issue_report(
    report_id: int,
    payload: IssueModerationUpdate,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
) -> AdminIssueRead:
    return IssueReportService(db, user).moderate(report_id, payload)
