from app.authorization.enums import CampaignCapability, CampaignRole


ROLE_CAPABILITIES: dict[
    CampaignRole,
    frozenset[CampaignCapability],
] = {
    CampaignRole.VIEWER: frozenset(
        {
            CampaignCapability.CAMPAIGN_READ,
            CampaignCapability.MEMBERSHIP_READ,
            CampaignCapability.SHARED_RESOURCE_READ,
        }
    ),
    CampaignRole.MEMBER: frozenset(
        {
            CampaignCapability.CAMPAIGN_EXPORT,
            CampaignCapability.CAMPAIGN_READ,
            CampaignCapability.MEMBERSHIP_READ,
            CampaignCapability.CHARACTER_SELF_CREATE,
            CampaignCapability.SHARED_RESOURCE_READ,
            CampaignCapability.SHARED_RESOURCE_WRITE,
            CampaignCapability.ASSIGNED_CHARACTER_WRITE,
        }
    ),
    CampaignRole.OWNER: frozenset(CampaignCapability),
}


def role_has_capability(
    role: CampaignRole,
    capability: CampaignCapability,
) -> bool:
    return capability in ROLE_CAPABILITIES[role]
