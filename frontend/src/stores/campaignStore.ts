import { computed, ref } from "vue"
import type { CampaignsDto } from "@/types/DataTransferObjects"
import { apiUrl } from "@/apihelpers"

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
    selectCampaign,
    clearSelectedCampaign,
  }
}