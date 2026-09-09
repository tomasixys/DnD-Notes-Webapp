<script setup lang="ts">
import { useResourceEditor } from "@/composables/useResourceEditor"
import { reactive, computed, ref, onBeforeMount } from "vue"
import type {
  CampaignCapability,
  CampaignsDto,
  DeleteResponseDto,
} from "@/types/DataTransferObjects";
import { ViewModes } from "@/types/viewTypes";
import {
  apiUrl,
  DeleteAPI,
  DownloadAPI,
  GetAPI,
  isApiFailure,
  PostFormDataAPI,
  PutFormDataAPI,
} from "@/apihelpers";
import { useCampaignStore } from "@/stores/campaignStore";
import { withExpectedRevision } from "@/utils/concurrency";
import ConfirmationPopup from "../components/ConfirmationPopup.vue";

import { useAuthStore } from "@/stores/authStore"
const auth = useAuthStore()

const {
  campaigns,
    selectedCampaignId,
    selectedCampaign,
    selectedCampaignImageUrl,
    selectedCampaignBannerUrl,
    hasSelectedCampaign,
    setCampaigns,
    upsertCampaign,
    removeCampaign,
    selectCampaign,
    clearSelectedCampaign,
} = useCampaignStore()

const defaultCampaigndto: CampaignsDto = {
  revision: 1,
  updatedAt: "",
  id: 0,
  name: "",
  playerCharacter: "",
  description: "",
  sessionCount: 0,
  imageUrl: "",
  bannerImageUrl: "",
  activeCharacterPersonId: null,
  assignedCharacterPersonId: null,
  membershipRole: "owner",
  capabilities: [],
}

const viewMode = ref<ViewModes>(ViewModes.Current)
const newCampaign = reactive<CampaignsDto>({ ...defaultCampaigndto })
const editingCampaignId = ref<number | null>(null)

const newCampaignImageFile = ref<File | null>(null)
const newCampaignBannerFile = ref<File | null>(null)

const showDeleteCampaignPopup = ref(false)

function campaignCan(
  campaign: CampaignsDto,
  capability: CampaignCapability,
): boolean {
  return campaign.capabilities.includes(capability)
}

function clearNewCampaignForm() {
  Object.assign(newCampaign, defaultCampaigndto)
  newCampaignImageFile.value = null
  newCampaignBannerFile.value = null
}


onBeforeMount(async () => {
  await fetchCampaigns();
})

function showCurrentCampaign() {
  viewMode.value = ViewModes.Current
}

function showCampaignList() {
  viewMode.value = ViewModes.Selection
}

function showNewCampaignForm() {
  clearNewCampaignForm()
  editingCampaignId.value = null
  viewMode.value = ViewModes.Create
}

function showEditCampaignForm(campaignId: number) {
  selectCampaign(campaignId)

  editingCampaignId.value = campaignId

  newCampaign.revision = selectedCampaign.value?.revision ?? 1
  newCampaign.name = selectedCampaign.value?.name ?? ""
  newCampaign.playerCharacter = selectedCampaign.value?.playerCharacter ?? ""
  newCampaign.description = selectedCampaign.value?.description ?? ""
  newCampaignImageFile.value = null
  newCampaignBannerFile.value = null

  viewMode.value = ViewModes.Edit
}

function switchCampaign(campaignId: number) {
  selectCampaign(campaignId)
  viewMode.value = ViewModes.Current
}



async function submitCampaign() {
  if (viewMode.value === ViewModes.Create) {
    await createCampaign()
    return
  } else if (viewMode.value === ViewModes.Edit) {
    if (editingCampaignId.value === null) {
      console.error("Cannot update campaign: no campaign is being edited")
      return
    }
    await updateCampaign(editingCampaignId.value)
  }
}

function buildCampaignFormData(): FormData {
  const formData = new FormData()
  formData.append("name", newCampaign.name.trim())
  formData.append("player_character", newCampaign.playerCharacter.trim())
  formData.append("description", newCampaign.description.trim())

  if (newCampaignImageFile.value) {
    formData.append("image", newCampaignImageFile.value)
  }

  if (newCampaignBannerFile.value) {
    formData.append("banner", newCampaignBannerFile.value)
  }

  return formData
}

async function fetchCampaigns() {
    const response = await GetAPI<CampaignsDto[]>("campaigns")

    if (isApiFailure(response)) {
        console.error("Failed to fetch campaigns:", response.error)
        return
    }
    console.log("Fetched campaigns:", response)
    if (!Array.isArray(response)) {
        console.error("Failed to fetch campaigns: Response is not an array")
        return
    }
    setCampaigns(response)
}

async function createCampaign() {

  if (!newCampaign.name.trim()) return

  const campaign = buildCampaignFormData()

  const response = await PostFormDataAPI<CampaignsDto>(
    "campaigns",
    campaign,
  )
  if (isApiFailure(response)) {
    console.error("Failed to create campaign:", response.error)
    return
  }
  const created = response;
  if (created.id === 0) {
    console.error("Failed to create campaign: Invalid campaign ID returned")
    return
  }

  upsertCampaign(created)
  switchCampaign(created.id)

  clearNewCampaignForm()
}

async function updateCampaign(campaignId: number) {
  if (!newCampaign.name.trim()) return

  const campaign = buildCampaignFormData()
  const currentCampaign = campaigns.value.find(
    (entry) => entry.id === campaignId,
  )
  if (!currentCampaign) return
  campaign.append(
    "expected_revision",
    String(currentCampaign.revision),
  )

  const response = await PutFormDataAPI<CampaignsDto>(
    `campaigns/${campaignId}`,
    campaign,
  )
  if (isApiFailure(response)) {
    console.error("Failed to update campaign:", response.error)
    return
  }
  const updatedCampaign = response;
  upsertCampaign(updatedCampaign)
  switchCampaign(updatedCampaign.id)

  clearNewCampaignForm()
}

async function deleteCampaign(campaignId: number) {
  const campaign = campaigns.value.find((entry) => entry.id === campaignId)
  if (!campaign) return
  const response = await DeleteAPI<DeleteResponseDto>(
    withExpectedRevision(
      `campaigns/${campaignId}`,
      campaign.revision,
    ),
  )

  if (isApiFailure(response)) {
    console.error("Failed to delete campaign:", response.error)
    return
  }
  removeCampaign(response.deletedId)
}

async function exportCampaign(campaignId: number) {
  const response = await DownloadAPI(
    `campaigns/${campaignId}/backup/export`,
  )
  if (isApiFailure(response)) {
    console.error("Failed to export campaign:", response.error)
    return
  }
}

async function importCampaign() {
  const input = document.createElement("input")
  input.type = "file"
  input.accept = ".backup"
  input.onchange = async (event: Event) => {
    const target = event.target as HTMLInputElement
    const file = target.files?.[0]
    if (!file) return

    const formData = new FormData()
    formData.append("backup", file)

    const response = await PostFormDataAPI<CampaignsDto>(
      "campaigns/backup/import",
      formData,
    )
    if (isApiFailure(response)) {
      console.error("Failed to import campaign:", response.error)
      return
    }
    console.log("Imported campaign:", response)
    upsertCampaign(response)
    switchCampaign(response.id)
  }
  input.click()
}

function onCampaignImageSelected(event: Event) {
  const input = event.target as HTMLInputElement
  newCampaignImageFile.value = input.files?.[0] ?? null
}

function onCampaignBannerSelected(event: Event) {
  const input = event.target as HTMLInputElement
  newCampaignBannerFile.value = input.files?.[0] ?? null
}

const campaignImagePreviewUrl = computed(() => {
  if (newCampaignImageFile.value) {
    return URL.createObjectURL(newCampaignImageFile.value)
  }

  return selectedCampaignImageUrl.value ?? ""
})

const campaignBannerPreviewUrl = computed(() => {
  if (newCampaignBannerFile.value) {
    return URL.createObjectURL(newCampaignBannerFile.value)
  }

  return selectedCampaignBannerUrl.value ?? ""
})


useResourceEditor(() => (viewMode.value === ViewModes.Create || viewMode.value === ViewModes.Edit) ? [{
  campaignId: editingCampaignId.value ?? selectedCampaignId.value ?? 0,
  resourceType: "campaign",
  resourceId: editingCampaignId.value,
  revision: newCampaign.revision,
}] : [])
</script>

<template>
  <section class="dashboard-view">
    <header class="view-header">
      <h2>Campaign Dashboard</h2>
      <p>
        {{ selectedCampaign
          ? "Manage your campaign or switch to a different."
          : "Choose a campaign or start a new one."
        }}
      </p>
    </header>

    <article v-if="viewMode === ViewModes.Current" class="dashboard-card">
      <template v-if="selectedCampaign">
        <div class="campaign-summary">
          <img
            v-if="selectedCampaignImageUrl"
            class="campaign-image"
            :src="selectedCampaignImageUrl"
            :alt="selectedCampaign.name"
          />

          <div class="campaign-info">
            <h3>{{ selectedCampaign.name }}</h3>

            <p class="player-character">
              <strong>Player characters:</strong>
              {{ selectedCampaign.playerCharacter || "None registered yet" }}
            </p>

            <p>
              {{ selectedCampaign.description || "No campaign description has been added yet." }}
            </p>

            <p class="session-count">
              <strong>Sessions:</strong>
              {{ selectedCampaign.sessionCount }}
            </p>
            <p class="session-count">
              <strong>Access:</strong>
              {{ selectedCampaign.membershipRole }}
            </p>
          </div>
        </div>

        <div class="dashboard-actions">
          <button type="button" @click="showNewCampaignForm">
            Start new campaign
          </button>

          <button type="button" class="secondary" @click="showCampaignList">
            Campaign list
          </button>
        </div>
      </template>

      <template v-else>
        <p>No campaign selected.</p>

        <div class="dashboard-actions">
          <button type="button" @click="showNewCampaignForm">
            Start new campaign
          </button>

          <button type="button" class="secondary" @click="showCampaignList">
            Campaign list
          </button>
        </div>
      </template>
    </article>

    <article
      v-else-if="
        viewMode === ViewModes.Create
        || (
          viewMode === ViewModes.Edit
          && selectedCampaign
          && campaignCan(selectedCampaign, 'campaign.update')
        )
      "
      class="dashboard-card"
    >
      <h3>{{ viewMode === ViewModes.Create ? "Start new campaign" : "Edit campaign" }}</h3>

      <form class="campaign-form" @submit.prevent="submitCampaign">
        <label>
          Campaign name
          <input
            v-model="newCampaign.name"
            type="text"
            placeholder="Streets of Gernanti"
            required
          />
        </label>

        <label v-if="!auth.authenticationRequired.value">
          Player character
          <input
            v-model="newCampaign.playerCharacter"
            type="text"
            placeholder="Nalia"
          />
        </label>

        <label>
          Campaign description
          <textarea
            v-model="newCampaign.description"
            rows="4"
            placeholder="A short description of the campaign..."
          />
        </label>

        <label>
          Campaign image URL
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            @change="onCampaignImageSelected"
          />
        </label>
        <label>
          Campaign banner URL
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            @change="onCampaignBannerSelected"
          />
        </label>

        <div class="dashboard-actions">

          <button type="submit">
           {{ viewMode === ViewModes.Create ?  "Create campaign" : "Update campaign" }}
          </button>

          <button
            type="button"
            class="secondary"
            @click="showCurrentCampaign"
          >
            Cancel
          </button>
        </div>
      </form>
    </article>

    <article v-else-if="viewMode === ViewModes.Selection" class="dashboard-card">
      <h3>Campaign list</h3>

      <ul v-if="campaigns.length > 0" class="campaign-list">
        <li
          v-for="campaign in campaigns"
          :key="campaign.id"
          class="campaign-list-item"
        >
          <div>
            <h4>{{ campaign.name }}
            </h4>
            <small>{{ campaign.playerCharacter }} </small>
            <p>
              {{ campaign.description || "No description." }}
            </p>
            <small>
              {{ campaign.sessionCount }} sessions · {{ campaign.membershipRole }}
            </small>

          </div>

          <div class="campaign-list-actions">
            <button
              v-if="campaignCan(campaign, 'campaign.read')"
              type="button"
              @click="switchCampaign(campaign.id)"
            >
              Select Campaign
            </button>

            <button
              v-if="campaignCan(campaign, 'campaign.update')"
              type="button"
              class="secondary"
              @click="showEditCampaignForm(campaign.id)"
            >
              Edit
            </button>

            <button
              v-if="campaignCan(campaign, 'campaign.export')"
              type="button"
              class="secondary"
              @click="exportCampaign(campaign.id)"
            >
              Export
            </button>

            <button
              v-if="campaignCan(campaign, 'campaign.delete')"
              type="button"
              class="danger"
              @click="showDeleteCampaignPopup = true; selectCampaign(campaign.id)"
            >
              Delete
            </button>
          </div>
        </li>
      </ul>

      <p v-else>No campaigns have been created yet.</p>

      <div class="dashboard-actions">
        <button
          type="button"
          @click="showNewCampaignForm"
        >
          Start new campaign
        </button>

        <button
          type="button"
          class="secondary"
          @click="importCampaign"
        >
          Import
        </button>

        <button
          type="button"
          class="secondary"
          @click="showCurrentCampaign"
        >
          Back
        </button>
      </div>
    </article>

    <ConfirmationPopup
      v-if="
        showDeleteCampaignPopup
        && selectedCampaign
        && campaignCan(selectedCampaign, 'campaign.delete')
      "
      title="Delete campaign?"
      :message="`Delete campaign ${selectedCampaign.name} and all associated entries? This cannot be undone.`"
      confirm-text="Delete campaign"
      @cancel="showDeleteCampaignPopup = false"
      @confirm="deleteCampaign(selectedCampaign.id); showDeleteCampaignPopup = false"
    />

  </section>
</template>

<style scoped>
.dashboard-view {
  display: grid;
  gap: 1.5rem;
}

.dashboard-card {
  padding: 1.5rem;
  border: 1px solid var(--color-border);
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.035);
}

.dashboard-card h3 {
  margin-top: 0;
  font-size: 1.5rem;
}

.campaign-summary {
  display: grid;
  grid-template-columns: minmax(12rem, 20rem) minmax(0, 1fr);
  gap: 1.5rem;
  align-items: start;
}

.campaign-image {
  width: 100%;
  max-height: 14rem;
  object-fit: cover;
  border-radius: 0.8rem;
  border: 1px solid var(--color-border);
}

.campaign-info h3 {
  margin: 0 0 0.75rem;
  font-size: 1.8rem;
}

.player-character,
.session-count {
  color: var(--color-text-muted);
}

.dashboard-actions,
.campaign-list-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.campaign-list-actions button {
  max-height: 3rem;
}

.dashboard-actions {
  margin-top: 1.5rem;
}

.campaign-form {
  display: grid;
  gap: 1rem;
}

.campaign-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 1rem;
}

.campaign-list-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1rem;
  padding: 1rem;
  border: 1px solid var(--color-border);
  border-radius: 0.75rem;
  background: rgba(0, 0, 0, 0.16);
}

.campaign-list-item h4 {
  margin: 0 0 0.35rem;
}

.campaign-list-item p {
  margin: 0 0 0.5rem;
  color: var(--color-text-muted);
}

.campaign-list-item small {
  color: var(--color-accent-soft);
}

@media (max-width: 800px) {
  .campaign-summary {
    grid-template-columns: 1fr;
  }

  .campaign-list-item {
    grid-template-columns: 1fr;
  }
}
</style>
