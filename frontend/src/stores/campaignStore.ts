import { computed, ref } from "vue"
import type {
  CampaignCapability,
  CampaignsDto,
} from "@/types/DataTransferObjects"
import { apiUrl } from "@/apihelpers"
import {
  compareById,
  removeById,
  upsertById,
} from "@/utils/resourceCollections"

const SELECTED_CAMPAIGN_KEY = "selectedCampaignId"
const userScope = ref<string | null>(null)

function storageKey(): string | null {
  return userScope.value
    ? `${SELECTED_CAMPAIGN_KEY}:${userScope.value}`
    : null
}

function readStoredCampaignId(): number | null {
  const key = storageKey()
  if (!key) return null
  const storedValue = localStorage.getItem(key)

  if (!storedValue) {
    return null
  }

  const parsedValue = Number(storedValue)
  if (parsedValue < 1 || !Number.isFinite(parsedValue)) {
    return null
  }

  return parsedValue
}

const campaigns = ref<CampaignsDto[]>([])
const selectedCampaignId = ref<number | null>(null)

const selectedCampaign = computed(() => {
  return campaigns.value.find((campaign) => campaign.id === selectedCampaignId.value) ?? null
})

const hasSelectedCampaign = computed(() => {
  return selectedCampaign.value !== null
})

const selectedCampaignImageUrl = computed(() => {
  if (!selectedCampaign.value?.imageUrl) {
    return null
  }
  return apiUrl + selectedCampaign.value.imageUrl
})

const selectedCampaignBannerUrl = computed(() => {
  if (!selectedCampaign.value?.bannerImageUrl) {
    return null
  }
  return apiUrl + selectedCampaign.value.bannerImageUrl
})

function setCampaigns(newCampaigns: CampaignsDto[]) {
  campaigns.value = newCampaigns

  const selectedCampaignStillExists = campaigns.value.some(
    (campaign) => campaign.id === selectedCampaignId.value,
  )

  if (!selectedCampaignStillExists) {
    selectedCampaignId.value = campaigns.value[0]?.id ?? null
    persistSelectedCampaign()
  }
}

function upsertCampaign(campaign: CampaignsDto) {
  campaigns.value = upsertById(
    campaigns.value,
    campaign,
    compareById,
  )
}

function removeCampaign(campaignId: number) {
  setCampaigns(removeById(campaigns.value, campaignId))
}

function setCampaignActiveCharacter(
  campaignId: number,
  personId: number | null,
  playerCharacter = "",
) {
  campaigns.value = campaigns.value.map((campaign) =>
    campaign.id === campaignId
      ? {
          ...campaign,
          assignedCharacterPersonId: personId,
          activeCharacterPersonId: personId,
          playerCharacter,
        }
      : campaign
  )
}

function adjustCampaignSessionCount(
  campaignId: number,
  amount: number,
) {
  campaigns.value = campaigns.value.map((campaign) =>
    campaign.id === campaignId
      ? {
          ...campaign,
          sessionCount: Math.max(0, campaign.sessionCount + amount),
        }
      : campaign
  )
}

function selectCampaign(campaignId: number) {
  selectedCampaignId.value = campaignId
  persistSelectedCampaign()
}

function clearSelectedCampaign() {
  selectedCampaignId.value = null
  const key = storageKey()
  if (key) localStorage.removeItem(key)
}

function persistSelectedCampaign(campaignId?: number | null) {
  const key = storageKey()
  if (!key) return
  if (campaignId === null) {
    localStorage.removeItem(key)
    return
  }

  localStorage.setItem(key, String(selectedCampaignId.value))
}

function setUserScope(userId: number | null) {
  const nextScope = userId === null ? null : String(userId)
  if (userScope.value === nextScope) return
  campaigns.value = []
  selectedCampaignId.value = null
  userScope.value = nextScope
  selectedCampaignId.value = readStoredCampaignId()
}

function clearUserState() {
  const key = storageKey()
  if (key) localStorage.removeItem(key)
  campaigns.value = []
  selectedCampaignId.value = null
  userScope.value = null
}

function hasCapability(capability: CampaignCapability): boolean {
  return selectedCampaign.value?.capabilities.includes(capability) ?? false
}

export function useCampaignStore() {
  return {
    campaigns,
    selectedCampaignId,
    selectedCampaign,
    selectedCampaignImageUrl,
    selectedCampaignBannerUrl,
    hasSelectedCampaign,
    setCampaigns,
    upsertCampaign,
    removeCampaign,
    setCampaignActiveCharacter,
    adjustCampaignSessionCount,
    selectCampaign,
    clearSelectedCampaign,
    setUserScope,
    clearUserState,
    hasCapability,
  }
}
