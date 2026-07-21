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

export type ResourceType =
  | "session"
  | "person"
  | "location"
  | "faction"
  | "character_note"
  | "backstory_note"

export type TagResolutionState =
  | "passive"
  | "resolved"
  | "unresolved"
  | "ambiguous"

export type RelationshipType =
  | "associated_with"
  | "member_of"
  | "located_in"
  | "part_of"
  | "based_in"

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

export type ExportResponse = {
  backupUrl: string
  filename: string
}

export type SearchResourceType = ResourceType

export type SearchQueryDto = {
  query: string
  resourceTypes: SearchResourceType[]
}

export type SearchResultDto = {
  campaignId: number
  resourceType: SearchResourceType
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
  searchedResourceTypes: SearchResourceType[]
  totalCount: number
  results: SearchResultDto[]
}
