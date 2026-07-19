from fastapi import APIRouter, Depends, HTTPException
from scipy.stats import norm
from sqlmodel import SQLModel, Session, select

from app.database import get_session
from app.database.models import Campaign, RollEntry, SessionNote
from app.routers.campaigns import verify_campaign

router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/rolls",
    tags=["rolls"],
)


class RollCreate(SQLModel):
    session_id: int
    roll: int


class SessionRollStats(SQLModel):
    campaign_id: int
    session_id: int
    rolls: list[int]
    average: float
    roll_luck: float


class CampaignRollStats(SQLModel):
    campaign_id: int
    num_rolls: int
    roll_avg: float
    roll_luck: float


class RollCreateResponse(SQLModel):
    campaign_stats: CampaignRollStats
    session_stats: SessionRollStats


def verify_campaign_and_session(
    campaign_id: int,
    session_id: int,
    db: Session,
) -> None:
    verify_campaign(campaign_id, db)
    session_note = db.get(SessionNote, session_id)

    if session_note is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session_note.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Session not found for this campaign")


def calculate_average(rolls: list[int]) -> float:
    if len(rolls) == 0:
        return 0

    return sum(rolls) / len(rolls)


def calculate_roll_luck(rolls: list[int], die_sides: int = 20) -> float:
    if len(rolls) == 0:
        return 0

    if any(roll < 1 or roll > die_sides for roll in rolls):
        raise ValueError(f"Rolls must be between 1 and {die_sides}")

    num_rolls = len(rolls)
    rolled_total = sum(rolls)

    expected_total = num_rolls * (die_sides + 1) / 2
    standard_deviation = (
        num_rolls * (die_sides**2 - 1) / 12
    ) ** 0.5

    z_value = (rolled_total - expected_total) / standard_deviation

    return float(norm.cdf(z_value))


def build_campaign_roll_stats(
    campaign_id: int,
    db: Session,
) -> CampaignRollStats:
    verify_campaign(campaign_id, db)
    statement = (
        select(RollEntry)
        .join(SessionNote, RollEntry.session_id == SessionNote.id)
        .where(SessionNote.campaign_id == campaign_id)
    )
    roll_entries = list(db.exec(statement).all())
    rolls = [entry.roll for entry in roll_entries]

    return CampaignRollStats(
        campaign_id=campaign_id,
        num_rolls=len(rolls),
        roll_avg=calculate_average(rolls),
        roll_luck=calculate_roll_luck(rolls),
    )


def build_session_roll_stats(
    campaign_id: int,
    session_id: int,
    db: Session,
) -> SessionRollStats:
    roll_entries = get_session_roll_entries(campaign_id, session_id, db)
    rolls = [entry.roll for entry in roll_entries]

    return SessionRollStats(
        campaign_id=campaign_id,
        session_id=session_id,
        rolls=rolls,
        average=calculate_average(rolls),
        roll_luck=calculate_roll_luck(rolls),
    )


def get_session_roll_entries(campaign_id: int, session_id: int, db: Session) -> list[RollEntry]:
    verify_campaign_and_session(campaign_id, session_id, db)
    statement = (
        select(RollEntry)
        .where(RollEntry.session_id == session_id)
    )
    return list(db.exec(statement).all())



@router.get("/campaign-stats")
def get_campaign_roll_stats(
    campaign_id: int,
    db: Session = Depends(get_session),
) -> CampaignRollStats:
    return build_campaign_roll_stats(campaign_id, db)


@router.get("/sessions/{session_id}")
def get_session_roll_stats(
    campaign_id: int,
    session_id: int,
    db: Session = Depends(get_session),
) -> SessionRollStats:
    return build_session_roll_stats(campaign_id, session_id, db)


@router.post("")
def create_roll(
    campaign_id: int,
    roll_create: RollCreate,
    db: Session = Depends(get_session),
) -> RollCreateResponse:
    verify_campaign_and_session(campaign_id, roll_create.session_id, db)

    if roll_create.roll < 1 or roll_create.roll > 20:
        raise HTTPException(
            status_code=400,
            detail="Roll must be between 1 and 20",
        )

    roll_entry = RollEntry(
        session_id=roll_create.session_id,
        roll=roll_create.roll,
    )

    db.add(roll_entry)
    db.commit()
    db.refresh(roll_entry)

    return RollCreateResponse(
        campaign_stats=build_campaign_roll_stats(campaign_id, db),
        session_stats=build_session_roll_stats(
            campaign_id=campaign_id,
            session_id=roll_create.session_id,
            db=db,
        ),
    )


@router.delete("/sessions/{session_id}")
def delete_session_rolls(
    campaign_id: int,
    session_id: int,
    db: Session = Depends(get_session),
) -> dict[str, bool]:
    for entry in get_session_roll_entries(campaign_id, session_id, db):
        db.delete(entry)

    db.commit()
    return {"deleted": True}