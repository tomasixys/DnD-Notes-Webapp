import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.auth.enums import SystemRole
from app.authorization.context import CampaignContext
from app.authorization.enums import (
    CampaignRole,
    ResourceGrantPermission,
    ResourceVisibility,
)
from app.authorization.models import CampaignMembership
from app.models.api import (
    CharacterCreate,
    CharacterNoteData,
    CharacterNoteGrantData,
    PersonData,
    SearchQueryDto,
)
from app.models.database import Campaign, CharacterNote, Person
from app.models.enums import ResourceType
from app.services.campaign_backups import CampaignBackupService
from app.services.character_notes import (
    BackstoryNoteService,
    CharacterNoteService,
)
from app.services.characters import CharacterService
from app.services.people import PersonService
from app.services.search import SearchService
from tests.authorization_helpers import campaign_context, create_user


class ResourceVisibilityTests(unittest.TestCase):
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

    def test_member_export_contains_own_private_notes_but_excludes_others(self):
        with tempfile.TemporaryDirectory() as directory, Session(self.engine) as db:
            owner, member, viewer, person_id = self._campaign_actors(db)
            for context, title in ((owner, "Owner secret"), (member, "Member secret")):
                CharacterNoteService(context).create(person_id, CharacterNoteData(
                    title=title, visibility=ResourceVisibility.PRIVATE,
                ))
            CharacterNoteService(member).create(person_id, CharacterNoteData(title="Shared"))
            path = Path(directory) / "member.zip"
            with patch("app.services.campaign_backups.make_backup_archive_path", return_value=(path, "member.zip")):
                CampaignBackupService(db, member.user).export(member)
            with ZipFile(path) as archive:
                manifest = json.loads(archive.read("backup.json"))
            self.assertTrue(manifest["access_filtered"])
            titles = {note["title"] for character in manifest["characters"] for note in character["notes"]}
            self.assertEqual({"Member secret", "Shared"}, titles)
            with self.assertRaises(HTTPException) as denied:
                CampaignBackupService(db, viewer.user).export(viewer)
            self.assertEqual(403, denied.exception.status_code)

    def tearDown(self):
        self.engine.dispose()

    @staticmethod
    def _member_context(
        db: Session,
        campaign: Campaign,
        *,
        role: CampaignRole,
        assigned_character_person_id: int | None = None,
    ) -> CampaignContext:
        user = create_user(db)
        membership = CampaignMembership(
            campaign_id=campaign.id,
            user_id=user.id,
            role=role,
            assigned_character_person_id=assigned_character_person_id,
            active_character_person_id=assigned_character_person_id,
        )
        db.add(membership)
        db.flush()
        return CampaignContext(db, campaign, user, membership)

    def _campaign_actors(
        self,
        db: Session,
    ) -> tuple[CampaignContext, CampaignContext, CampaignContext, int]:
        campaign = Campaign(name="Private campaign")
        db.add(campaign)
        db.flush()
        owner = campaign_context(db, campaign)
        character = CharacterService(owner).create(
            CharacterCreate(person=PersonData(name="Nalia"))
        )
        owner.membership.assigned_character_person_id = None
        owner.membership.active_character_person_id = None
        db.add(owner.membership)
        db.flush()
        member = self._member_context(
            db,
            campaign,
            role=CampaignRole.MEMBER,
            assigned_character_person_id=character.person.id,
        )
        viewer = self._member_context(
            db,
            campaign,
            role=CampaignRole.VIEWER,
        )
        db.commit()
        return owner, member, viewer, character.person.id

    def test_private_and_restricted_notes_compose_with_campaign_roles(self):
        with Session(self.engine) as db:
            owner, member, viewer, person_id = self._campaign_actors(db)
            member_notes = CharacterNoteService(member)
            private_note = member_notes.create(
                person_id,
                CharacterNoteData(
                    title="Private plan",
                    content="Nobody else should see this.",
                    visibility=ResourceVisibility.PRIVATE,
                ),
            )
            restricted_note = member_notes.create(
                person_id,
                CharacterNoteData(
                    title="Shared confidence",
                    visibility=ResourceVisibility.RESTRICTED,
                    grants=[
                        CharacterNoteGrantData(
                            user_id=viewer.user.id,
                            permission=ResourceGrantPermission.WRITE,
                        )
                    ],
                ),
            )
            BackstoryNoteService(member).create(
                person_id,
                CharacterNoteData(
                    title="Hidden history",
                    visibility=ResourceVisibility.PRIVATE,
                ),
            )

            self.assertEqual(
                {"Private plan", "Shared confidence"},
                {
                    note.title
                    for note in member_notes.list_for_character(person_id)
                },
            )
            self.assertEqual(
                [],
                CharacterNoteService(owner).list_for_character(person_id),
            )
            self.assertEqual(
                [],
                BackstoryNoteService(owner).list_for_character(person_id),
            )
            viewer_reads = CharacterNoteService(viewer).list_for_character(
                person_id
            )
            self.assertEqual(
                ["Shared confidence"],
                [note.title for note in viewer_reads],
            )
            self.assertFalse(viewer_reads[0].can_write)
            self.assertFalse(viewer_reads[0].can_manage_access)

            with self.assertRaises(HTTPException) as hidden:
                CharacterNoteService(owner).get(
                    person_id,
                    private_note.id,
                )
            self.assertEqual(404, hidden.exception.status_code)

            owner_grant = CharacterNoteData(
                title=restricted_note.title,
                visibility=ResourceVisibility.RESTRICTED,
                grants=[
                    CharacterNoteGrantData(
                        user_id=owner.user.id,
                        permission=ResourceGrantPermission.WRITE,
                    )
                ],
            )
            updated_by_member = member_notes.update(
                person_id,
                restricted_note.id,
                owner_grant,
            )
            self.assertEqual(owner.user.id, updated_by_member.grants[0].user_id)
            updated_by_owner = CharacterNoteService(owner).update(
                person_id,
                restricted_note.id,
                CharacterNoteData(
                    title="Owner was explicitly invited",
                    visibility=ResourceVisibility.RESTRICTED,
                    grants=owner_grant.grants,
                ),
            )
            self.assertEqual(
                "Owner was explicitly invited",
                updated_by_owner.title,
            )

    def test_search_tags_and_counts_do_not_reveal_hidden_notes(self):
        with Session(self.engine) as db:
            owner, member, _, person_id = self._campaign_actors(db)
            note = CharacterNoteService(member).create(
                person_id,
                CharacterNoteData(
                    title="Moonfall password",
                    content="quiet secret",
                    visibility=ResourceVisibility.PRIVATE,
                ),
            )
            public_person = PersonService(owner).create(
                PersonData(
                    name="Public witness",
                    tags=["character_note:Moonfall password"],
                )
            )

            owner_search = SearchService(owner).search(
                SearchQueryDto(query="Moonfall")
            )
            self.assertEqual(0, owner_search.total_count)
            public_read = PersonService(owner).to_read(
                db.get(Person, public_person.id)
            )
            self.assertEqual([], public_read.tags)

            member_search = SearchService(member).search(
                SearchQueryDto(
                    query="Moonfall",
                    resource_types=[
                        ResourceType.PERSON.value,
                        ResourceType.CHARACTER_NOTE.value,
                    ],
                )
            )
            self.assertEqual(
                {
                    (ResourceType.PERSON, public_person.id),
                    (ResourceType.CHARACTER_NOTE, note.id),
                },
                {
                    (result.resource_type, result.resource_id)
                    for result in member_search.results
                },
            )

    def test_owner_export_is_filtered_and_import_reowns_private_records(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "filtered.backup"
            with Session(self.engine) as db:
                owner, member, _, person_id = self._campaign_actors(db)
                CharacterNoteService(member).create(
                    person_id,
                    CharacterNoteData(
                        title="Member private",
                        visibility=ResourceVisibility.PRIVATE,
                    ),
                )
                CharacterNoteService(owner).create(
                    person_id,
                    CharacterNoteData(
                        title="Owner private",
                        visibility=ResourceVisibility.PRIVATE,
                    ),
                )

                with patch(
                    "app.services.campaign_backups."
                    "make_backup_archive_path",
                    return_value=(archive_path, "filtered.backup"),
                ):
                    CampaignBackupService(db, owner.user).export(owner)

                with ZipFile(archive_path, "r") as archive:
                    manifest = json.loads(
                        archive.read("backup.json").decode("utf-8")
                    )
                exported_notes = manifest["characters"][0]["notes"]
                self.assertTrue(manifest["access_filtered"])
                self.assertEqual(
                    ["Owner private"],
                    [note["title"] for note in exported_notes],
                )
                self.assertEqual(
                    ResourceVisibility.PRIVATE.value,
                    exported_notes[0]["visibility"],
                )

                imported = CampaignBackupService(
                    db,
                    owner.user,
                ).import_archive(archive_path.read_bytes())
                imported_note = db.exec(
                    select(CharacterNote).where(
                        CharacterNote.campaign_id == imported.id
                    )
                ).one()
                self.assertEqual(
                    ResourceVisibility.PRIVATE,
                    imported_note.visibility,
                )
                self.assertEqual(
                    owner.user.id,
                    imported_note.access_owner_user_id,
                )
                self.assertIsNone(imported_note.created_by_user_id)

    def test_membership_removal_revokes_grants_and_assigns_private_custody(self):
        with Session(self.engine) as db:
            owner, member, viewer, person_id = self._campaign_actors(db)
            custodian = create_user(
                db,
                role=SystemRole.CUSTODIAN,
                can_login=False,
            )
            private_note = CharacterNoteService(member).create(
                person_id,
                CharacterNoteData(
                    title="Custodial note",
                    visibility=ResourceVisibility.RESTRICTED,
                    grants=[
                        CharacterNoteGrantData(
                            user_id=viewer.user.id,
                        )
                    ],
                ),
            )

            from app.authorization.memberships import (
                CampaignMembershipService,
            )

            CampaignMembershipService(owner).remove_user(member.user.id)
            stored = db.get(CharacterNote, private_note.id)
            self.assertEqual(
                custodian.id,
                stored.access_owner_user_id,
            )
            self.assertEqual(
                ["Custodial note"],
                [
                    note.title
                    for note in CharacterNoteService(
                        viewer
                    ).list_for_character(person_id)
                ],
            )
            CampaignMembershipService(owner).remove_user(viewer.user.id)
            self.assertEqual(
                [],
                CharacterNoteService(viewer).list_for_character(person_id),
            )


if __name__ == "__main__":
    unittest.main()
