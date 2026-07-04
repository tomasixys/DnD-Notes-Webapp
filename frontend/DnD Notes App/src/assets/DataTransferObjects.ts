export type CampaignsDto = {
  id: number
  name: string
  playerCharacter: string
  description: string
  sessionCount: number
  imageUrl: string
}

export type SessionListItemDto = {
  campaignId: number
  sessionId: number
  date: string
  title: string
  description: string
  tags: string[]
}
  
export type SessionRollDto = {
  campaignId: number
  sessionId: number
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

export type PersonDto = {
  campaignId: number
  personId: number
  name: string
  role: string
  faction: string
  location: string
  description: string
  tags: string[]
}

export type LocationDto = {
  campaignId: number
  locationId: number
  name: string
  type: string
  parentLocation: string
  description: string
  tags: string[]
}

export type FactionDto = {
  campaignId: number
  factionId: number
  name: string
  type: string
  location: string
  description: string
  tags: string[]
}