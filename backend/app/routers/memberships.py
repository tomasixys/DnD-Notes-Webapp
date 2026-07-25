from fastapi import APIRouter, Depends

from app.authorization.context import CampaignContext
from app.authorization.dependencies import (
    get_membership_manage_context,
    get_membership_read_context,
)
from app.authorization.memberships import CampaignMembershipService
from app.authorization.schemas import (
    CampaignMemberAdd,
    CampaignMembershipRead,
    CampaignMemberRoleUpdate,
    CharacterAssignmentUpdate,
)
from app.models.api import DeleteResponse


router = APIRouter(
    prefix="/api/campaigns/{campaign_id}/members",
    tags=["campaign-memberships"],
)


@router.get("")
def list_members(
    context: CampaignContext = Depends(get_membership_read_context),
) -> list[CampaignMembershipRead]:
    return CampaignMembershipService(context).list_reads()


@router.post("")
def add_member(
    payload: CampaignMemberAdd,
    context: CampaignContext = Depends(get_membership_manage_context),
) -> CampaignMembershipRead:
    return CampaignMembershipService(context).add_user(
        payload.username,
        payload.role,
    )


@router.put("/{user_id}/role")
def change_member_role(
    user_id: int,
    payload: CampaignMemberRoleUpdate,
    context: CampaignContext = Depends(get_membership_manage_context),
) -> CampaignMembershipRead:
    return CampaignMembershipService(context).change_role(
        user_id,
        payload.role,
    )


@router.put("/{user_id}/character")
def assign_member_character(
    user_id: int,
    payload: CharacterAssignmentUpdate,
    context: CampaignContext = Depends(get_membership_manage_context),
) -> CampaignMembershipRead:
    return CampaignMembershipService(context).assign_character(
        user_id,
        payload.character_person_id,
    )


@router.delete("/self/leave")
def leave_campaign(
    context: CampaignContext = Depends(get_membership_read_context),
) -> DeleteResponse:
    user_id = context.user.id
    CampaignMembershipService(context).leave()
    return DeleteResponse(deleted_id=user_id)


@router.delete("/{user_id}")
def remove_member(
    user_id: int,
    context: CampaignContext = Depends(get_membership_manage_context),
) -> DeleteResponse:
    CampaignMembershipService(context).remove_user(user_id)
    return DeleteResponse(deleted_id=user_id)
