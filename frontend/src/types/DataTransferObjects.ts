import type {
  CurrencyDenomination,
  InventoryAccessRole,
  ItemCategory,
  ItemRarity,
} from "./inventoryTypes"
import type { ResourceType } from "./resourceTypes"
import type {
  RelationshipType,
  TagResolutionState,
} from "./tagTypes"

export type RevisionDto = {
  revision: number
  updatedAt: string
}

export type CampaignsDto = RevisionDto & {
  id: number
  name: string
  playerCharacter: string
  description: string
  sessionCount: number
  imageUrl: string
  bannerImageUrl: string
  activeCharacterPersonId: number | null
  assignedCharacterPersonId: number | null
  membershipRole: CampaignRole
  capabilities: CampaignCapability[]
}

export type CampaignRole = "owner" | "member" | "viewer"

export type CampaignCapability =
  | "campaign.read"
  | "campaign.update"
  | "campaign.delete"
  | "campaign.export"
  | "membership.read"
  | "membership.manage"
  | "character.assign"
  | "character.self_create"
  | "shared_resource.read"
  | "shared_resource.write"
  | "assigned_character.write"

export type AuthUserDto = {
  id: number
  username: string
  displayName: string
  status: "pending" | "active" | "suspended" | "deleted"
  systemRole: "user" | "admin" | "custodian"
}

export type AdminUserDto = AuthUserDto & {
  activeSessions: number
  campaignMemberships: number
}

export type AdminCampaignDto = {
  id: number
  name: string
  orphaned: boolean
}

export type AuthSessionDto = {
  user: AuthUserDto
  csrfToken: string
  authenticationRequired: boolean
}

export type AccountMutationDto = {
  user: AuthUserDto
  message: string
}

export type SessionMutationDto = {
  message: string
  revokedSessions: number
}

export type IssuedAccountTokenDto = {
  user: AuthUserDto
  token: string
  expiresAt: string
}

export type CampaignMembershipDto = {
  id: number
  userId: number
  username: string
  displayName: string
  role: CampaignRole
  assignedCharacterPersonId: number | null
  activeCharacterPersonId: number | null
  capabilities: CampaignCapability[]
}

export type CampaignInvitationStatus =
  | "pending"
  | "accepted"
  | "revoked"
  | "expired"

export type CampaignInvitationDto = {
  id: number
  campaignId: number
  campaignName: string
  invitedUserId: number
  username: string
  displayName: string
  role: CampaignRole
  status: CampaignInvitationStatus
  createdAt: string
  expiresAt: string
}

export type IssuedCampaignInvitationDto = {
  invitation: CampaignInvitationDto
  token: string
}

export type CampaignInvitationAcceptanceDto = {
  invitation: CampaignInvitationDto
  membership: CampaignMembershipDto
}

export type CampaignOwnershipTransferDto = {
  previousOwner: CampaignMembershipDto
  newOwner: CampaignMembershipDto
}

export type DeleteResponseDto = {
  deletedId: number
}

export type ResourceTagDto = {
  value: string
  label: string
  referenceType: ResourceType | null
  referenceId: number | null
  relationshipType: RelationshipType | null
  resolutionState: TagResolutionState
}

export type SessionListItemDto = RevisionDto & {
  id: number
  campaignId: number
  date: string
  title: string
  description: string
  tags: ResourceTagDto[]
}

export type SessionDataDto = Omit<
  SessionListItemDto,
  "id" | "campaignId" | "tags" | "revision" | "updatedAt"
> & {
  tags: string[]
}
  
export type SessionRollDto = {
  sessionId: number
  campaignId: number
  userId: number
  rolls: number[]
  average: number
  rollLuck: number
  revision: number
  otherContributors: RollContributorStatsDto[]
}

export type RollContributorStatsDto = {
  userId: number | null
  displayName: string
  numRolls: number
  average: number
  rollLuck: number
}
  
export type CampaignRollDto = {
  campaignId: number
  numRolls: number
  rollAvg: number
  rollLuck: number
}

export type RollEntryDto = {
  sessionId: number
  roll: number
}

export type RollMutationDto = {
  campaignStats: CampaignRollDto
  sessionStats: SessionRollDto
}

export type PersonDto = RevisionDto & {
  id: number
  campaignId: number
  name: string
  role: string
  faction: ResourceTagDto | null
  location: ResourceTagDto | null
  description: string
  tags: ResourceTagDto[]
  characterProfileAvailable: boolean
  isActiveCharacter: boolean
}

export type PersonDataDto = Omit<
  PersonDto,
  | "id"
  | "campaignId"
  | "faction"
  | "location"
  | "tags"
  | "characterProfileAvailable"
  | "isActiveCharacter"
  | "revision"
  | "updatedAt"
> & {
  faction: string
  location: string
  tags: string[]
}

export type CharacterDto = RevisionDto & {
  person: PersonDto
  shortBio: string
  appearance: string
  imageUrl: string
  isActive: boolean
}

export type CharacterDeleteResponseDto = DeleteResponseDto & {
  activeCharacter: CharacterDto | null
}

export type CharacterCreateDto = {
  personId?: number
  person?: PersonDataDto
  shortBio: string
  appearance: string
  makeActive: boolean
}

export type CharacterUpdateDto = {
  person: PersonDataDto
  shortBio: string
  appearance: string
}

export type ResourceVisibility = "campaign" | "restricted" | "private"

export type ResourceGrantPermission = "read" | "write"

export type CharacterNoteGrantDataDto = {
  userId: number
  permission: ResourceGrantPermission
}

export type CharacterNoteGrantDto = CharacterNoteGrantDataDto & {
  username: string
  displayName: string
}

export type CharacterNoteDto = {
  id: number
  campaignId: number
  characterPersonId: number
  title: string
  content: string
  createdAt: string
  updatedAt: string
  revision: number
  createdByUserId: number | null
  visibility: ResourceVisibility
  accessOwnerUserId: number | null
  grants: CharacterNoteGrantDto[]
  canWrite: boolean
  canManageAccess: boolean
  tags: ResourceTagDto[]
}

export type CharacterNoteDataDto = {
  title: string
  content: string
  tags: string[]
  visibility: ResourceVisibility
  grants: CharacterNoteGrantDataDto[]
}

export type LocationDto = RevisionDto & {
  id: number
  campaignId: number
  name: string
  type: string
  parentLocation: ResourceTagDto | null
  people: ResourceTagDto[]
  description: string
  tags: ResourceTagDto[]
}

export type LocationDataDto = Omit<
  LocationDto,
  | "id"
  | "campaignId"
  | "parentLocation"
  | "people"
  | "tags"
  | "revision"
  | "updatedAt"
> & {
  parentLocation: string
  tags: string[]
}

export type FactionDto = RevisionDto & {
  id: number
  campaignId: number
  name: string
  type: string
  location: ResourceTagDto | null
  members: ResourceTagDto[]
  description: string
  tags: ResourceTagDto[]
}

export type FactionDataDto = Omit<
  FactionDto,
  | "id"
  | "campaignId"
  | "location"
  | "members"
  | "tags"
  | "revision"
  | "updatedAt"
> & {
  location: string
  tags: string[]
}

export type MoneyAmountDto = {
  amount: string
  denomination: CurrencyDenomination
}

export type PurseBalancesDto = {
  cp: number
  sp: number
  ep: number
  gp: number
  pp: number
}

export type PurseBalancesUpdateDto = Partial<PurseBalancesDto>

export type PurseUpdateDto = {
  balances: PurseBalancesUpdateDto
}

export type PurseDto = {
  balances: PurseBalancesDto
  totalValue: MoneyAmountDto
}

export type InventoryMemberDto = {
  characterPersonId: number
  characterName: string
  role: InventoryAccessRole
  isActiveCharacter: boolean
}

export type InventoryItemDataDto = {
  name: string
  description: string
  category: ItemCategory
  rarity: ItemRarity | null
  quantity: number
  unitValue: MoneyAmountDto | null
}

export type InventoryItemCreateDto = {
  name: string
  description?: string
  category?: ItemCategory
  rarity?: ItemRarity | null
  quantity?: number
  unitValue?: MoneyAmountDto | null
}

export type InventoryItemUpdateDto = {
  name?: string
  description?: string
  category?: ItemCategory
  rarity?: ItemRarity | null
  quantity?: number
  unitValue?: MoneyAmountDto | null
}

export type InventoryItemDto = InventoryItemDataDto & {
  id: number
  totalValue: MoneyAmountDto | null
}

export type InventoryUpdateDto = {
  name?: string
  description?: string
}

export type InventoryDto = RevisionDto & {
  id: number
  campaignId: number
  name: string
  description: string
  members: InventoryMemberDto[]
  purse: PurseDto
  items: InventoryItemDto[]
}

export type CampaignChangeDto = {
  sequence: number
  resourceType: string
  resourceId: number | null
  action: "created" | "updated" | "deleted"
  revision: number | null
  createdAt: string
}

export type CampaignChangesDto = {
  cursor: number
  changes: CampaignChangeDto[]
}

export type SearchQueryDto = {
  query: string
  resourceTypes: ResourceType[]
}

export type SearchResultDto = {
  campaignId: number
  resourceType: ResourceType
  resourceId: number
  parentResourceId: number | null
  title: string
  context: string
  snippet: string
  matchedFields: string[]
  relevance: number
}

export type SearchResponseDto = {
  query: string
  searchedResourceTypes: ResourceType[]
  totalCount: number
  results: SearchResultDto[]
}
