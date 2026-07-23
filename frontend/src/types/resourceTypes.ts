export const resourceTypes = [
  "session",
  "person",
  "location",
  "faction",
  "character_note",
  "backstory_note",
] as const
export type ResourceType = typeof resourceTypes[number]
