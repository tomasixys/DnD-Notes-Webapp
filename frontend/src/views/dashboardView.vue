<script setup lang="ts">
import { ref, onBeforeMount } from "vue"
import type {
  CampaignsDto,
  DeleteResponseDto,
  ExportResponse,
} from "@/types/DataTransferObjects"
import { ViewModes } from "@/types/viewTypes"
import { GetAPI, DeleteAPI, DownloadAPI, PostFormDataAPI } from "@/apihelpers"
import { useCampaignStore } from "@/stores/campaignStore"
import ConfirmationPopup from "../components/ConfirmationPopup.vue"
import CampaignForm from "../components/CampaignForm.vue"

const {
  campaigns,
  selectedCampaignId,
  selectedCampaign,
  selectedCampaignImageUrl,
  setCampaigns,
  upsertCampaign,
  removeCampaign,
  selectCampaign,
} = useCampaignStore()

const viewMode = ref<ViewModes>(ViewModes.Current)
const editingCampaignId = ref<number | null>(null)
const showDeleteCampaignPopup = ref(false)

async function fetchCampaigns() {
  const response = await GetAPI("campaigns")

  if (response.success === false) {
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

onBeforeMount(async () => {
  await fetchCampaigns()
})

function showCurrentCampaign() {
  viewMode.value = ViewModes.Current
}

function showCampaignList() {
  viewMode.value = ViewModes.Selection
}

function showNewCampaignForm() {
  editingCampaignId.value = null
  viewMode.value = ViewModes.Create
}

function showEditCampaignForm(campaignId: number) {
  selectCampaign(campaignId)
  editingCampaignId.value = campaignId
  viewMode.value = ViewModes.Edit
}

function switchCampaign(campaignId: number) {
  selectCampaign(campaignId)
  viewMode.value = ViewModes.Current
}

function onSelectCampaignChange(event: Event) {
  const target = event.target as HTMLInputElement
  const id = Number(target.value)
  if (id > 0) {
    switchCampaign(id)
  }
}

function onCampaignSubmitted(savedCampaign: CampaignsDto) {
  upsertCampaign(savedCampaign)
  switchCampaign(savedCampaign.id)
}

async function deleteCampaign(campaignId: number) {
  const response = await DeleteAPI(`campaigns/${campaignId}`)

  if (response.success === false) {
    console.error("Failed to delete campaign:", response.error)
    return
  }
  const deleted = response as DeleteResponseDto
  removeCampaign(deleted.deletedId)
}

async function exportCampaign(campaignId: number) {
  const response = await GetAPI(`campaigns/${campaignId}/backup/export`)
  if (response.success === false) {
    console.error("Failed to export campaign:", response.error)
    return
  }
  console.log("Exported campaign:", response)
  const exportResponse = response as ExportResponse

  const downloadResponse = await DownloadAPI(exportResponse.backupUrl)
  if (!downloadResponse.success) {
    console.error("Failed to download campaign backup:", downloadResponse.error)
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

    const response = await PostFormDataAPI("campaigns/backup/import", formData)
    if (response.success === false) {
      console.error("Failed to import campaign:", response.error)
      return
    }
    console.log("Imported campaign:", response)
    const importedCampaign = response as CampaignsDto
    upsertCampaign(importedCampaign)
    switchCampaign(importedCampaign.id)
  }
  input.click()
}
</script>

<template>
  <section class="dashboard-view">
    <header class="view-header">
      <p>
        {{ selectedCampaign
          ? "Manage your active campaign or switch to a different one."
          : "Choose a campaign or start a new one."
        }}
      </p>
    </header>

    <article v-if="viewMode === ViewModes.Current" class="dashboard-card relative-card">
      <template v-if="selectedCampaign">
        <button
          type="button"
          class="edit-icon-btn"
          aria-label="Edit campaign"
          title="Edit campaign"
          @click="showEditCampaignForm(selectedCampaign.id)"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path>
          </svg>
        </button>

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
              <strong>Active character:</strong>
              {{ selectedCampaign.activeCharacter ? selectedCampaign.activeCharacter.name : "None registered yet" }}
            </p>

            <p>
              {{ selectedCampaign.description || "No campaign description has been added yet." }}
            </p>

            <p class="session-count">
              <strong>Sessions:</strong>
              {{ selectedCampaign.sessionCount }}
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

    <CampaignForm
      v-else-if="viewMode === ViewModes.Create || viewMode === ViewModes.Edit"
      :mode="viewMode"
      :campaign-id="editingCampaignId"
      :initial-campaign="selectedCampaign"
      @submitted="onCampaignSubmitted"
      @cancel="showCurrentCampaign"
    />

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
            <small v-if="campaign.activeCharacter">{{ campaign.activeCharacter.name }}</small>
            <p>
              {{ campaign.description || "No description." }}
            </p>
            <small>
              {{ campaign.sessionCount }} sessions
            </small>

          </div>

          <div class="campaign-list-actions">
            <button
              type="button"
              @click="switchCampaign(campaign.id)"
            >
              Select Campaign
            </button>

            <button
              type="button"
              class="secondary"
              @click="showEditCampaignForm(campaign.id)"
            >
              Edit
            </button>

            <button
              type="button"
              class="secondary"
              @click="exportCampaign(campaign.id)"
            >
              Export
            </button>

            <button
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
      v-if="showDeleteCampaignPopup && selectedCampaign"
      title="Delete session?"
      :message="`Delete campaign ${selectedCampaign.name} and all associated entries? This cannot be undone.`"
      confirm-text="Delete session"
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

.header-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.header-title-row h2 {
  margin: 0;
}

.campaign-select-dropdown {
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid var(--color-border);
  color: var(--color-text);
  font-size: 0.95rem;
  cursor: pointer;
  min-width: 14rem;
}

.campaign-select-dropdown:hover {
  border-color: var(--color-accent, #646cff);
}

.dashboard-card {
  padding: 1.5rem;
  border: 1px solid var(--color-border);
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.035);
}

.relative-card {
  position: relative;
}

.edit-icon-btn {
  position: absolute;
  top: 1.25rem;
  right: 1.25rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  padding: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid var(--color-border);
  color: var(--color-text);
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, transform 0.15s ease;
}

.edit-icon-btn:hover {
  background: rgba(255, 255, 255, 0.18);
  border-color: var(--color-accent, #646cff);
  transform: scale(1.05);
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
