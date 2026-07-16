export type CampaignsDto = {
  id: number
  name: string
  playerCharacter: string
  description: string
  sessionCount: number
  imageUrl: string
  bannerImageUrl: string
}

export type SessionListItemDto = {
  id: number
  campaignId: number
  sessionNumber: number
  date: string
  title: string
  description: string
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
  faction: string
  location: string
  description: string
  tags: string[]
}

export type LocationDto = {
  id: number
  campaignId: number
  name: string
  type: string
  parentLocation: string
  description: string
  tags: string[]
}

export type FactionDto = {
  id: number
  campaignId: number
  name: string
  type: string
  location: string
  description: string
  tags: string[]
}

export type ExportResponse = {
  backupUrl: string
  filename: string
}

export type SearchResourceType =
  | "session"
  | "person"
  | "location"
  | "faction"

export type SearchQueryDto = {
  query: string
  resourceTypes: SearchResourceType[]
}

export type SearchResultDto = {
  campaignId: number
  resourceType: SearchResourceType
  resourceId: number
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