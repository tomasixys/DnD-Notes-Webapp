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

export type CampaignsDto = {
  id: number
  name: string
  playerCharacter: string
  description: string
  sessionCount: number
  imageUrl: string
  bannerImageUrl: string
  activeCharacterPersonId: number | null
}

export type ResourceTagDto = {
  value: string
  label: string
  referenceType: ResourceType | null
  referenceId: number | null
  relationshipType: RelationshipType | null
  resolutionState: TagResolutionState
}

export type SessionListItemDto = {
  id: number
  campaignId: number
  sessionNumber: number
  date: string
  title: string
  description: string
  tags: ResourceTagDto[]
}

export type SessionDataDto = Omit<
  SessionListItemDto,
  "id" | "campaignId" | "tags"
> & {
  tags: string[]
}
  
export type SessionRollDto = {
  id: number
  campaignId: number
  sessionNumber: number
  rolls: number[]
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

export type PersonDto = {
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
> & {
  faction: string
  location: string
  tags: string[]
}

export type CharacterDto = {
  person: PersonDto
  shortBio: string
  appearance: string
  imageUrl: string
  isActive: boolean
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

export type CharacterNoteDto = {
  id: number
  campaignId: number
  characterPersonId: number
  title: string
  content: string
  createdAt: string
  updatedAt: string
  tags: ResourceTagDto[]
}

export type CharacterNoteDataDto = {
  title: string
  content: string
  tags: string[]
}

export type LocationDto = {
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
  "id" | "campaignId" | "parentLocation" | "people" | "tags"
> & {
  parentLocation: string
  tags: string[]
}

export type FactionDto = {
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
  "id" | "campaignId" | "location" | "members" | "tags"
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

export type InventoryDto = {
  id: number
  campaignId: number
  name: string
  description: string
  members: InventoryMemberDto[]
  purse: PurseDto
  items: InventoryItemDto[]
}

export type ExportResponse = {
  backupUrl: string
  filename: string
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
