export const currencyDenominations = ["cp", "sp", "ep", "gp", "pp"] as const
export type CurrencyDenomination = typeof currencyDenominations[number]

export const inventoryAccessRoles = ["owner", "manager"] as const
export type InventoryAccessRole = typeof inventoryAccessRoles[number]

export const itemCategories = [
  "equipment",
  "valuable",
  "consumable",
] as const
export type ItemCategory = typeof itemCategories[number]

export const itemRarities = [
  "common",
  "uncommon",
  "rare",
  "very_rare",
  "legendary",
  "artifact",
] as const
export type ItemRarity = typeof itemRarities[number]
