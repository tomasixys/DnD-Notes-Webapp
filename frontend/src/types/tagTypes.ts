export const tagResolutionStates = [
  "passive",
  "resolved",
  "unresolved",
  "ambiguous",
] as const
export type TagResolutionState = typeof tagResolutionStates[number]

export const relationshipTypes = [
  "associated_with",
  "member_of",
  "located_in",
  "part_of",
  "based_in",
] as const
export type RelationshipType = typeof relationshipTypes[number]
