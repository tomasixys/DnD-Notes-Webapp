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
from app.authorization.context import CampaignContext
from app.services.rolls import RollService
from app.services.tags import TagService
from app.concurrency import claim_revision
from app.services.campaign_changes import CampaignChangeService


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
        self.changes = CampaignChangeService(context)

    def to_read(self, episode: Episode) -> EpisodeRead:
        return EpisodeRead(
            revision=episode.revision,
            updated_at=episode.updated_at,
            id=episode.id,
            campaign_id=episode.campaign_id,
            date=episode.date,
            title=episode.title,
            description=episode.content,
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

    def list_for_campaign(self) -> list[EpisodeRead]:
        statement = (
            select(Episode)
            .where(Episode.campaign_id == self.context.campaign_id)
            .order_by(Episode.id)
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
        tags: list[str],
    ) -> Episode:
        episode = Episode(
            campaign_id=self.context.campaign_id,
            date=date,
            title=title,
            content=description,
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
        self.changes.stage_record(
            ResourceType.EPISODE.value,
            episode.id,
            action="created",
            revision=episode.revision,
        )
        return episode

    def stage_create(
        self,
        episode_data: EpisodeData,
        expected_revision: int | None = None,
    ) -> Episode:
        return self._stage_insert(
            date=episode_data.date,
            title=episode_data.title,
            description=episode_data.description,
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
        expected_revision: int | None = None,
    ) -> Episode:
        episode = self.get(episode_id)
        claim_revision(
            self.db,
            episode,
            expected_revision or episode.revision,
            resource_type=ResourceType.EPISODE.value,
        )
        previous_labels = [episode.title]
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
        self.changes.stage_record(
            ResourceType.EPISODE.value,
            episode.id,
            action="updated",
            revision=episode.revision,
        )
        return episode

    def update(
        self,
        episode_id: int,
        episode_data: EpisodeData,
        expected_revision: int | None = None,
    ) -> EpisodeRead:
        try:
            episode = self.stage_update(
                episode_id,
                episode_data,
                expected_revision,
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
        expected_revision: int | None = None,
    ) -> None:
        episode = self.get(episode_id)
        claim_revision(
            self.db,
            episode,
            expected_revision or episode.revision,
            resource_type=ResourceType.EPISODE.value,
        )
        self.tags.stage_handle_resource_deletion(
            ResourceType.EPISODE,
            episode.id,
        )
        self.changes.stage_record(
            ResourceType.EPISODE.value,
            episode.id,
            action="deleted",
            revision=episode.revision,
        )
        self.db.delete(episode)
        self.db.flush()

    def delete(
        self,
        episode_id: int,
        expected_revision: int | None = None,
    ) -> DeleteResponse:
        try:
            self.stage_delete(episode_id, expected_revision)
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
            .order_by(Episode.id)
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
            tags=episode_backup.tags,
        )
        self.rolls.stage_restore_for_episode(
            episode,
            episode_backup.rolls,
        )
        return episode
