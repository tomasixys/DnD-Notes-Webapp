from fastapi import HTTPException
from scipy.stats import norm
from sqlmodel import select

from app.models.api import (
    CampaignRollStats,
    RollCreate,
    RollMutationResponse,
    SessionRollStats,
)
from app.models.database import RollEntry, SessionNote
from app.services.campaign_context import CampaignContext


class RollService:
    def __init__(self, context: CampaignContext):
        self.context = context
        self.db = context.db

    def _get_session(
        self,
        session_note_id: int,
    ) -> SessionNote:
        session_note = self.db.get(SessionNote, session_note_id)
        if session_note is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if session_note.campaign_id != self.context.campaign_id:
            raise HTTPException(
                status_code=404,
                detail="Session not found for this campaign",
            )
        return session_note

    @staticmethod
    def calculate_average(rolls: list[int]) -> float:
        if not rolls:
            return 0
        return sum(rolls) / len(rolls)

    @staticmethod
    def calculate_luck(rolls: list[int], die_sides: int = 20) -> float:
        if not rolls:
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

    def get_entries_for_session(
        self,
        session_note_id: int,
    ) -> list[RollEntry]:
        self._get_session(session_note_id)
        statement = select(RollEntry).where(
            RollEntry.session_id == session_note_id
        )
        return list(self.db.exec(statement).all())

    def get_values_for_session(self, session_note_id: int) -> list[int]:
        entries = self.db.exec(
            select(RollEntry)
            .where(RollEntry.session_id == session_note_id)
            .order_by(RollEntry.id)
        ).all()
        return [entry.roll for entry in entries]

    def get_campaign_stats(self) -> CampaignRollStats:
        statement = (
            select(RollEntry)
            .join(SessionNote, RollEntry.session_id == SessionNote.id)
            .where(SessionNote.campaign_id == self.context.campaign_id)
        )
        rolls = [entry.roll for entry in self.db.exec(statement).all()]
        return CampaignRollStats(
            campaign_id=self.context.campaign_id,
            num_rolls=len(rolls),
            roll_avg=self.calculate_average(rolls),
            roll_luck=self.calculate_luck(rolls),
        )

    def get_session_stats(
        self,
        session_note_id: int,
    ) -> SessionRollStats:
        rolls = [
            entry.roll
            for entry in self.get_entries_for_session(
                session_note_id,
            )
        ]
        return SessionRollStats(
            campaign_id=self.context.campaign_id,
            session_id=session_note_id,
            rolls=rolls,
            average=self.calculate_average(rolls),
            roll_luck=self.calculate_luck(rolls),
        )

    def stage_create(
        self,
        roll_create: RollCreate,
    ) -> RollEntry:
        self._get_session(roll_create.session_id)
        if roll_create.roll < 1 or roll_create.roll > 20:
            raise HTTPException(
                status_code=400,
                detail="Roll must be between 1 and 20",
            )

        roll_entry = RollEntry(
            session_id=roll_create.session_id,
            roll=roll_create.roll,
        )
        self.db.add(roll_entry)
        self.db.flush()
        return roll_entry

    def create(
        self,
        roll_create: RollCreate,
    ) -> RollMutationResponse:
        try:
            self.stage_create(roll_create)
            response = RollMutationResponse(
                campaign_stats=self.get_campaign_stats(),
                session_stats=self.get_session_stats(
                    roll_create.session_id,
                ),
            )
            self.db.commit()
            return response
        except Exception:
            self.db.rollback()
            raise

    def stage_delete_for_session(
        self,
        session_note_id: int,
    ) -> None:
        entries = self.get_entries_for_session(session_note_id)
        for entry in entries:
            self.db.delete(entry)
        self.db.flush()

    def delete_for_session(
        self,
        session_note_id: int,
    ) -> RollMutationResponse:
        try:
            self.stage_delete_for_session(session_note_id)
            response = RollMutationResponse(
                campaign_stats=self.get_campaign_stats(),
                session_stats=self.get_session_stats(
                    session_note_id,
                ),
            )
            self.db.commit()
            return response
        except Exception:
            self.db.rollback()
            raise

    def stage_restore_for_session(
        self,
        session_note: SessionNote,
        rolls: list[int],
    ) -> None:
        """Restore stored roll values in the caller-owned transaction."""
        for roll in rolls:
            self.db.add(
                RollEntry(
                    session_id=session_note.id,
                    roll=roll,
                )
            )
        self.db.flush()
