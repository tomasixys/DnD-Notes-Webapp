from enum import Enum


class CampaignRole(str, Enum):
    OWNER = "owner"
    MEMBER = "member"
    VIEWER = "viewer"


class CampaignCapability(str, Enum):
    CAMPAIGN_READ = "campaign.read"
    CAMPAIGN_UPDATE = "campaign.update"
    CAMPAIGN_DELETE = "campaign.delete"
    CAMPAIGN_EXPORT = "campaign.export"
    MEMBERSHIP_READ = "membership.read"
    MEMBERSHIP_MANAGE = "membership.manage"
    CHARACTER_ASSIGN = "character.assign"
    CHARACTER_SELF_CREATE = "character.self_create"
    SHARED_RESOURCE_READ = "shared_resource.read"
    SHARED_RESOURCE_WRITE = "shared_resource.write"
    ASSIGNED_CHARACTER_WRITE = "assigned_character.write"


class ResourceVisibility(str, Enum):
    CAMPAIGN = "campaign"
    RESTRICTED = "restricted"
    PRIVATE = "private"


class ResourceGrantPermission(str, Enum):
    READ = "read"
    WRITE = "write"
