import * as dto from "@/types/DataTransferObjects"

function passiveTags(...values: string[]): dto.ResourceTagDto[] {
  return values.map((value) => ({
    value,
    label: value,
    referenceType: null,
    referenceId: null,
    resolutionState: "passive",
  }))
}


export const sessionListExample: dto.SessionListItemDto[] = [
  {
    id: 1,
    campaignId: 1,
    sessionNumber: 1,
    date: "2026-01-12",
    title: "New Year, Old Trouble",
    description:
      "The campaign begins in Gernanti. The party wakes after a strange night, with missing time, unclear memories, and signs that someone or something has interfered with them.",
    tags: passiveTags("opening", "Gernanti", "mystery"),
  },
  {
    id: 2,
    campaignId: 1,
    sessionNumber: 2,
    date: "2026-01-19",
    title: "Bones Beneath the City",
    description:
      "The party escapes from the cave system and returns to the streets. They begin piecing together who may have drugged them and why they were taken below the city.",
    tags: passiveTags("caves", "undead", "investigation"),
  },
  {
    id: 3,
    campaignId: 1,
    sessionNumber: 3,
    date: "2026-01-26",
    title: "The Thieves' Hideout",
    description:
      "Following leads from the tavern confrontation, the party tracks the criminals to a hideout. Inside, Nalia discovers a grimoire that may be tied to deeper forces moving beneath Gernanti.",
    tags: passiveTags("hideout", "grimoire", "Nalia"),
  },
]

export const campaignRollStatsExample: dto.CampaignRollDto = {
  campaignId: 1,
  numRolls: 18,
  rollAvg: 10.72,
  rollLuck: 0.58,
}

export const sessionRollsExample: dto.SessionRollDto[] = [
  {
    id: 1,
    campaignId: 1,
    sessionNumber: 1,
    rolls: [12, 4, 16, 7, 11],
    average: 10,
    rollLuck: 0.5,
  },
  {
    id: 2,
    campaignId: 1,
    sessionNumber: 2,
    rolls: [3, 8, 14, 19, 9, 6],
    average: 9.83,
    rollLuck: 0.42,
  },
  {
    id: 3,
    campaignId: 1,
    sessionNumber: 3,
    rolls: [18, 15, 2, 13, 11, 20, 5],
    average: 12,
    rollLuck: 0.66,
  }
]

export const peopleExample: dto.PersonDto[] = [
  {
    id: 1,
    campaignId: 1,
    name: "Skiv Whistler",
    role: "Lookout and street contact",
    faction: "Beggars",
    location: "Gernanti mainland",
    description:
      "A street-level contact who warns Nalia and Elira about patrols, trouble, and useful rumors. Paid through coin, favors, or by being worked into their scams as a supposed recipient of charity.",
    tags: passiveTags("contact", "street", "lookout"),
  },
  {
    id: 2,
    campaignId: 1,
    name: "Eryn Marrowell",
    role: "Assistant librarian",
    faction: "Talmira's Church",
    location: "Gernanti magic academy",
    description:
      "One of the few people at the academy who believed Nalia during the scandal. Eryn did not have enough influence to protect her, but may still be a useful contact for books, rumors, and restricted academic information.",
    tags: passiveTags("ally", "academy", "library"),
  },
  {
    id: 3,
    campaignId: 1,
    name: "Velcor Thanes",
    role: "Professor of magical history",
    faction: "Dragon Order",
    location: "Gernanti magic academy",
    description:
      "The professor who discredited Nalia after she uncovered favoritism and corruption. Still active, still protected, and still a problem.",
    tags: passiveTags("enemy", "academic", "corrupt"),
  },
]

export const locationsExample: dto.LocationDto[] = [
  {
    id: 1,
    campaignId: 1,
    name: "Gernanti",
    type: "City",
    parentLocation: "",
    description:
      "A magical free city built across islands and mainland districts, governed through the academy, noble houses, and arcane factions.",
    tags: passiveTags("city", "magic", "campaign-hub"),
  },
  {
    id: 2,
    campaignId: 1,
    name: "Gernanti Mainland",
    type: "District",
    parentLocation: "Gernanti",
    description:
      "The mainland part of Gernanti, where many poorer residents, lodgings, markets, and street-level contacts are found.",
    tags: passiveTags("district", "street-level", "lower-city"),
  },
  {
    id: 3,
    campaignId: 1,
    name: "Nalia and Elira's Lodging House",
    type: "Building",
    parentLocation: "Gernanti Mainland",
    description:
      "A modest lodging house where Nalia and Elira live at the start of the campaign. Safer than the street, but not truly safe.",
    tags: passiveTags("home", "lodging", "safe-ish"),
  },
]

export const factionsExample: dto.FactionDto[] = [
  {
    id: 1,
    campaignId: 1,
    name: "The Dragon Order",
    type: "Arcane order",
    location: "Gernanti Magic Academy",
    description:
      "A powerful academic order studying dragons, draconic magic, and how to reproduce or exploit that power through wizardry.",
    tags: passiveTags("academy", "dragons", "magic", "political"),
  },
  {
    id: 2,
    campaignId: 1,
    name: "Talmira's Church",
    type: "Temple institution",
    location: "Gernanti Magic Academy",
    description:
      "The main religious institution in Gernanti, tied closely to knowledge, discipline, study, and the academy library.",
    tags: passiveTags("religion", "knowledge", "library", "academy"),
  },
  {
    id: 3,
    campaignId: 1,
    name: "The Beggars",
    type: "Street faction",
    location: "Gernanti Mainland",
    description:
      "A loose but guarded street-level faction made up of beggars, informants, and people pushed to the margins by magical experiments and city politics.",
    tags: passiveTags("street", "informants", "poor", "contacts"),
  },
]

export const campaignsExample: dto.CampaignsDto[] = [
  {
    id: 1,
    name: "Streets of Gernanti",
    playerCharacter: "Nalyathina Calemdor",
    description:
    "A street-level Pathfinder 2e campaign set in the magical free city of Gernanti, where ambition, corruption, arcane politics, and survival all collide.",
    sessionCount: 0,
    imageUrl: "/src/assets/banner.png",
    bannerImageUrl: "/src/assets/banner.png",
  },
]
