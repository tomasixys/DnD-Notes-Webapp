from fastapi import HTTPException
from sqlmodel import select

from app.models.api import (
    CampaignBackupEpisode,
    DeleteResponse,
    EpisodeData,
    EpisodeRead,
)
from app.models.database import Episode
from app.models.enums import ResourceType
from app.services.campaign_context import CampaignContext
from app.services.rolls import RollService
from app.services.tags import TagService


class EpisodeService:
    def __init__(
        self,
        context: CampaignContext,
        rolls: RollService | None = None,
    ):
        self.context = context
        self.db = context.db
        self.rolls = rolls or RollService(context)
        self.tags = TagService(context)

    def to_read(self, episode: Episode) -> EpisodeRead:
        return EpisodeRead(
            id=episode.id,
            campaign_id=episode.campaign_id,
            date=episode.date,
            title=episode.title,
            description=episode.content,
            session_number=episode.session_number,
            tags=self.tags.list_tag_reads(
                ResourceType.EPISODE,
                episode.id,
            ),
        )

    def get(
        self,
        episode_id: int,
    ) -> Episode:
        episode = self.db.get(Episode, episode_id)
        if (
            episode is None
            or episode.campaign_id != self.context.campaign_id
        ):
            raise HTTPException(status_code=404, detail="Episode not found")
        return episode

    def get_by_number(
        self,
        session_number: int,
    ) -> Episode | None:
        statement = select(Episode).where(
            Episode.campaign_id == self.context.campaign_id,
            Episode.session_number == session_number,
        )
        return self.db.exec(statement).first()

    def list_for_campaign(self) -> list[EpisodeRead]:
        statement = (
            select(Episode)
            .where(Episode.campaign_id == self.context.campaign_id)
            .order_by(Episode.session_number.desc())
        )
        return [
            self.to_read(episode)
            for episode in self.db.exec(statement).all()
        ]

    def _stage_insert(
        self,
        *,
        date: str,
        title: str,
        description: str,
        session_number: int,
        tags: list[str],
    ) -> Episode:
        if self.get_by_number(session_number) is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "An episode with this number already exists "
                    "for this campaign"
                ),
            )

        episode = Episode(
            campaign_id=self.context.campaign_id,
            date=date,
            title=title,
            content=description,
            session_number=session_number,
        )
        self.db.add(episode)
        self.db.flush()
        self.tags.stage_sync_tags(
            ResourceType.EPISODE,
            episode.id,
            tags,
        )
        self.tags.stage_refresh_references(
            ResourceType.EPISODE,
            episode.id,
        )
        return episode

    def stage_create(
        self,
        episode_data: EpisodeData,
    ) -> Episode:
        return self._stage_insert(
            date=episode_data.date,
            title=episode_data.title,
            description=episode_data.description,
            session_number=episode_data.session_number,
            tags=episode_data.tags,
        )

    def create(
        self,
        episode_data: EpisodeData,
    ) -> EpisodeRead:
        try:
            episode = self.stage_create(episode_data)
            self.db.commit()
            self.db.refresh(episode)
            return self.to_read(episode)
        except Exception:
            self.db.rollback()
            raise

    def stage_update(
        self,
        episode_id: int,
        episode_data: EpisodeData,
    ) -> Episode:
        episode = self.get(episode_id)
        previous_labels = [
            episode.title,
            str(episode.session_number),
            f"session {episode.session_number}",
            f"episode {episode.session_number}",
        ]
        existing = self.get_by_number(
            episode_data.session_number,
        )
        if existing is not None and existing.id != episode.id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "A different episode with this number already "
                    "exists for this campaign "
                    f"(Episode ID: {existing.id})"
                ),
            )

        episode.session_number = episode_data.session_number
        episode.date = episode_data.date
        episode.title = episode_data.title
        episode.content = episode_data.description
        self.db.add(episode)
        self.db.flush()
        self.tags.stage_sync_tags(
            ResourceType.EPISODE,
            episode.id,
            episode_data.tags,
        )
        self.tags.stage_refresh_references(
            ResourceType.EPISODE,
            episode.id,
            previous_labels=previous_labels,
        )
        return episode

    def update(
        self,
        episode_id: int,
        episode_data: EpisodeData,
    ) -> EpisodeRead:
        try:
            episode = self.stage_update(
                episode_id,
                episode_data,
            )
            self.db.commit()
            self.db.refresh(episode)
            return self.to_read(episode)
        except Exception:
            self.db.rollback()
            raise

    def stage_delete(
        self,
        episode_id: int,
    ) -> None:
        episode = self.get(episode_id)
        self.tags.stage_handle_resource_deletion(
            ResourceType.EPISODE,
            episode.id,
        )
        self.db.delete(episode)
        self.db.flush()

    def delete(
        self,
        episode_id: int,
    ) -> DeleteResponse:
        try:
            self.stage_delete(episode_id)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return DeleteResponse(deleted_id=episode_id)

    def to_backup(
        self,
        episode: Episode,
    ) -> CampaignBackupEpisode:
        return CampaignBackupEpisode(
            date=episode.date,
            title=episode.title,
            description=episode.content,
            session_number=episode.session_number,
            tags=self.tags.list_values(
                ResourceType.EPISODE,
                episode.id,
            ),
            rolls=self.rolls.get_values_for_episode(episode.id),
        )

    def list_backup_entries(self) -> list[CampaignBackupEpisode]:
        episodes = self.db.exec(
            select(Episode)
            .where(
                Episode.campaign_id == self.context.campaign_id
            )
            .order_by(Episode.session_number, Episode.id)
        ).all()
        return [
            self.to_backup(episode)
            for episode in episodes
        ]

    def stage_restore(
        self,
        episode_backup: CampaignBackupEpisode,
    ) -> Episode:
        episode = self._stage_insert(
            date=episode_backup.date,
            title=episode_backup.title,
            description=episode_backup.description,
            session_number=episode_backup.session_number,
            tags=episode_backup.tags,
        )
        self.rolls.stage_restore_for_episode(
            episode,
            episode_backup.rolls,
        )
        return episode
