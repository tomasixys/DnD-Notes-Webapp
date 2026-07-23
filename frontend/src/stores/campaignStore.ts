import { computed, ref } from "vue"
import type { CampaignsDto } from "@/types/DataTransferObjects"
import { apiUrl } from "@/apihelpers"
import {
  compareById,
  removeById,
  upsertById,
} from "@/utils/resourceCollections"

const SELECTED_CAMPAIGN_KEY = "selectedCampaignId"

function readStoredCampaignId(): number | null {
  const storedValue = localStorage.getItem(SELECTED_CAMPAIGN_KEY)

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
const selectedCampaignId = ref<number | null>(readStoredCampaignId())

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
) {
  campaigns.value = campaigns.value.map((campaign) =>
    campaign.id === campaignId
      ? { ...campaign, activeCharacterPersonId: personId }
      : campaign
  )
}

function selectCampaign(campaignId: number) {
  selectedCampaignId.value = campaignId
  persistSelectedCampaign()
}

function clearSelectedCampaign() {
  selectedCampaignId.value = null
  localStorage.removeItem(SELECTED_CAMPAIGN_KEY)
}

function persistSelectedCampaign(campaignId?: number | null) {
  if (campaignId === null) {
    localStorage.removeItem(SELECTED_CAMPAIGN_KEY)
    return
  }

  localStorage.setItem(SELECTED_CAMPAIGN_KEY, String(selectedCampaignId.value))
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
    selectCampaign,
    clearSelectedCampaign,
  }
}
