from fastapi import HTTPException
from scipy.stats import norm
from sqlalchemy import or_
from sqlmodel import select

from app.auth.models import User
from app.authorization.enums import CampaignCapability
from app.models.api import (
    CampaignRollStats,
    EpisodeRollStats,
    RollCreate,
    RollContributorStats,
    RollMutationResponse,
)
from app.models.database import Episode, RollEntry
from app.authorization.context import CampaignContext
from app.concurrency import claim_revision
from app.models.enums import ResourceType
from app.services.campaign_changes import CampaignChangeService


class RollService:
    def __init__(self, context: CampaignContext):
        self.context = context
        self.db = context.db
        self.changes = CampaignChangeService(context)

    def _get_episode(
        self,
        episode_id: int,
    ) -> Episode:
        self.context.require(CampaignCapability.SHARED_RESOURCE_READ)
        episode = self.db.get(Episode, episode_id)
        if episode is None:
            raise HTTPException(status_code=404, detail="Episode not found")
        if episode.campaign_id != self.context.campaign_id:
            raise HTTPException(
                status_code=404,
                detail="Episode not found for this campaign",
            )
        return episode

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

    def get_entries_for_episode(
        self,
        episode_id: int,
    ) -> list[RollEntry]:
        self._get_episode(episode_id)
        statement = (
            select(RollEntry)
            .where(
                RollEntry.session_id == episode_id,
                RollEntry.user_id == self.context.user.id,
            )
            .order_by(RollEntry.id)
        )
        return list(self.db.exec(statement).all())

    def get_values_for_episode(self, episode_id: int) -> list[int]:
        self.context.require(CampaignCapability.SHARED_RESOURCE_READ)
        statement = select(RollEntry).where(
            RollEntry.session_id == episode_id
        )
        if not self.context.elevated:
            statement = statement.where(
                RollEntry.user_id == self.context.user.id
            )
        entries = self.db.exec(
            statement.order_by(RollEntry.id)
        ).all()
        return [entry.roll for entry in entries]

    def get_campaign_stats(self) -> CampaignRollStats:
        self.context.require(CampaignCapability.SHARED_RESOURCE_READ)
        statement = (
            select(RollEntry)
            .join(Episode, RollEntry.session_id == Episode.id)
            .where(
                Episode.campaign_id == self.context.campaign_id,
                RollEntry.user_id == self.context.user.id,
            )
        )
        rolls = [entry.roll for entry in self.db.exec(statement).all()]
        return CampaignRollStats(
            campaign_id=self.context.campaign_id,
            num_rolls=len(rolls),
            roll_avg=self.calculate_average(rolls),
            roll_luck=self.calculate_luck(rolls),
        )

    def get_episode_stats(
        self,
        episode_id: int,
    ) -> EpisodeRollStats:
        episode = self._get_episode(episode_id)
        rolls = [
            entry.roll
            for entry in self.get_entries_for_episode(
                episode_id,
            )
        ]
        return EpisodeRollStats(
            campaign_id=self.context.campaign_id,
            session_id=episode_id,
            user_id=self.context.user.id,
            rolls=rolls,
            average=self.calculate_average(rolls),
            roll_luck=self.calculate_luck(rolls),
            revision=episode.revision,
            other_contributors=self._other_contributor_stats(
                episode_id
            ),
        )

    def _other_contributor_stats(
        self,
        episode_id: int,
    ) -> list[RollContributorStats]:
        entries = self.db.exec(
            select(RollEntry)
            .where(
                RollEntry.session_id == episode_id,
                or_(
                    RollEntry.user_id != self.context.user.id,
                    RollEntry.user_id.is_(None),
                ),
            )
            .order_by(RollEntry.id)
        ).all()
        grouped_rolls: dict[int | None, list[int]] = {}
        for entry in entries:
            grouped_rolls.setdefault(entry.user_id, []).append(entry.roll)

        user_ids = [
            user_id
            for user_id in grouped_rolls
            if user_id is not None
        ]
        users = (
            self.db.exec(
                select(User).where(User.id.in_(user_ids))
            ).all()
            if user_ids
            else []
        )
        users_by_id = {user.id: user for user in users}
        contributors: list[RollContributorStats] = []
        for user_id, rolls in grouped_rolls.items():
            user = users_by_id.get(user_id)
            display_name = (
                (user.display_name.strip() or user.username)
                if user is not None
                else "Legacy rolls"
            )
            contributors.append(
                RollContributorStats(
                    user_id=user_id,
                    display_name=display_name,
                    num_rolls=len(rolls),
                    average=self.calculate_average(rolls),
                    roll_luck=self.calculate_luck(rolls),
                )
            )
        return sorted(
            contributors,
            key=lambda contributor: (
                contributor.display_name.casefold(),
                contributor.user_id or 0,
            ),
        )

    def stage_create(
        self,
        roll_create: RollCreate,
        expected_revision: int | None = None,
    ) -> RollEntry:
        self.context.require(CampaignCapability.SHARED_RESOURCE_WRITE)
        episode = self._get_episode(roll_create.session_id)
        claim_revision(
            self.db,
            episode,
            expected_revision or episode.revision,
            resource_type=ResourceType.EPISODE.value,
        )
        if roll_create.roll < 1 or roll_create.roll > 20:
            raise HTTPException(
                status_code=400,
                detail="Roll must be between 1 and 20",
            )

        roll_entry = RollEntry(
            session_id=roll_create.session_id,
            user_id=self.context.user.id,
            roll=roll_create.roll,
        )
        self.db.add(roll_entry)
        self.db.flush()
        self.changes.stage_record(
            ResourceType.EPISODE.value,
            episode.id,
            action="updated",
            revision=episode.revision,
        )
        return roll_entry

    def create(
        self,
        roll_create: RollCreate,
        expected_revision: int | None = None,
    ) -> RollMutationResponse:
        try:
            self.stage_create(roll_create, expected_revision)
            response = RollMutationResponse(
                campaign_stats=self.get_campaign_stats(),
                session_stats=self.get_episode_stats(
                    roll_create.session_id,
                ),
            )
            self.db.commit()
            return response
        except Exception:
            self.db.rollback()
            raise

    def stage_delete_for_episode(
        self,
        episode_id: int,
        expected_revision: int | None = None,
    ) -> None:
        self.context.require(CampaignCapability.SHARED_RESOURCE_WRITE)
        episode = self._get_episode(episode_id)
        claim_revision(
            self.db,
            episode,
            expected_revision or episode.revision,
            resource_type=ResourceType.EPISODE.value,
        )
        entries = self.get_entries_for_episode(episode_id)
        for entry in entries:
            self.db.delete(entry)
        self.db.flush()
        self.changes.stage_record(
            ResourceType.EPISODE.value,
            episode.id,
            action="updated",
            revision=episode.revision,
        )

    def delete_for_episode(
        self,
        episode_id: int,
        expected_revision: int | None = None,
    ) -> RollMutationResponse:
        try:
            self.stage_delete_for_episode(
                episode_id,
                expected_revision,
            )
            response = RollMutationResponse(
                campaign_stats=self.get_campaign_stats(),
                session_stats=self.get_episode_stats(
                    episode_id,
                ),
            )
            self.db.commit()
            return response
        except Exception:
            self.db.rollback()
            raise

    def stage_restore_for_episode(
        self,
        episode: Episode,
        rolls: list[int],
    ) -> None:
        """Restore stored roll values in the caller-owned transaction."""
        self.context.require(CampaignCapability.SHARED_RESOURCE_WRITE)
        for roll in rolls:
            self.db.add(
                RollEntry(
                    session_id=episode.id,
                    user_id=self.context.user.id,
                    roll=roll,
                )
            )
        self.db.flush()
