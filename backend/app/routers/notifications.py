from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.auth.dependencies import require_current_user
from app.auth.models import User
from app.database import get_session
from app.models.api import AccountNotificationSummaryRead
from app.services.notifications import AccountNotificationService


router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def notification_summary(
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
) -> AccountNotificationSummaryRead:
    return AccountNotificationService(db, user).summary()
