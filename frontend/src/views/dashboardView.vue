<script setup lang="ts">
import { reactive, computed, ref, onBeforeMount } from "vue"
import type {
  CampaignsDto,
  DeleteResponseDto,
  ExportResponse,
  FactionDto,
  PersonDto,
} from "@/types/DataTransferObjects";
import { ViewModes } from "@/types/viewTypes";
import { GetAPI, PostFormDataAPI, PutFormDataAPI, DeleteAPI, DownloadAPI, apiUrl } from "@/apihelpers";
import { useCampaignStore } from "@/stores/campaignStore";
import ConfirmationPopup from "../components/ConfirmationPopup.vue";

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
  id: 0,
  name: "",
  description: "",
  sessionCount: 0,
  imageUrl: "",
  bannerImageUrl: "",
  activeCharacter: null,
}

const viewMode = ref<ViewModes>(ViewModes.Current)
const newCampaign = reactive<CampaignsDto>({ ...defaultCampaigndto })
const editingCampaignId = ref<number | null>(null)

const newCampaignCharacterName = ref("")
const newCampaignFactionName = ref("")

const campaignFactions = ref<FactionDto[]>([])
const campaignPeople = ref<PersonDto[]>([])
const selectedFactionId = ref<number | null>(null)
const selectedPersonId = ref<number | null>(null)

const filteredPeople = computed(() => {
  if (!selectedFactionId.value) {
    return campaignPeople.value
  }
  return campaignPeople.value.filter(
    (person) => person.faction?.referenceId === selectedFactionId.value
  )
})

const newCampaignImageFile = ref<File | null>(null)
const newCampaignBannerFile = ref<File | null>(null)

const showDeleteCampaignPopup = ref(false)

function clearNewCampaignForm() {
  Object.assign(newCampaign, defaultCampaigndto)
  newCampaignCharacterName.value = ""
  newCampaignFactionName.value = ""
  selectedFactionId.value = null
  selectedPersonId.value = null
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

async function showEditCampaignForm(campaignId: number) {
  selectCampaign(campaignId)

  editingCampaignId.value = campaignId

  newCampaign.name = selectedCampaign.value?.name ?? ""
  newCampaign.description = selectedCampaign.value?.description ?? ""
  newCampaignImageFile.value = null
  newCampaignBannerFile.value = null

  const factionsResponse = await GetAPI(`campaigns/${campaignId}/factions`)
  if (Array.isArray(factionsResponse)) {
    campaignFactions.value = factionsResponse as FactionDto[]
  } else {
    campaignFactions.value = []
  }

  const peopleResponse = await GetAPI(`campaigns/${campaignId}/people`)
  if (Array.isArray(peopleResponse)) {
    campaignPeople.value = peopleResponse as PersonDto[]
  } else {
    campaignPeople.value = []
  }

  selectedPersonId.value = selectedCampaign.value?.activeCharacter?.id ?? null
  if (selectedPersonId.value) {
    const activePerson = campaignPeople.value.find((p) => p.id === selectedPersonId.value)
    selectedFactionId.value = activePerson?.faction?.referenceId ?? null
  } else {
    selectedFactionId.value = null
  }

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
  formData.append("description", newCampaign.description.trim())

  if (viewMode.value === ViewModes.Create) {
    if (newCampaignCharacterName.value.trim()) {
      formData.append("character_name", newCampaignCharacterName.value.trim())
    }
    if (newCampaignFactionName.value.trim()) {
      formData.append("faction_name", newCampaignFactionName.value.trim())
    }
  } else if (viewMode.value === ViewModes.Edit) {
    formData.append(
      "active_character_person_id",
      selectedPersonId.value ? String(selectedPersonId.value) : "0"
    )
  }

  if (newCampaignImageFile.value) {
    formData.append("image", newCampaignImageFile.value)
  }

  if (newCampaignBannerFile.value) {
    formData.append("banner", newCampaignBannerFile.value)
  }

  return formData
}

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

async function createCampaign() {

  if (!newCampaign.name.trim()) return

  let campaign = buildCampaignFormData()

  const response = await PostFormDataAPI("campaigns", campaign)
  if (response.success === false) {
    console.error("Failed to create campaign:", response.error)
    return
  }
  const created = response as CampaignsDto;
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

  const response = await PutFormDataAPI(`campaigns/${campaignId}`, campaign)
  if (response.success === false) {
    console.error("Failed to update campaign:", response.error)
    return
  }
  const updatedCampaign = response as CampaignsDto;
  upsertCampaign(updatedCampaign)
  switchCampaign(updatedCampaign.id)

  clearNewCampaignForm()
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

    <article v-else-if="viewMode === ViewModes.Create" class="dashboard-card">
      <h3>Start new campaign</h3>

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

        <label>
          Initial character name
          <input
            v-model="newCampaignCharacterName"
            type="text"
            placeholder="Nalyathina Calemdor"
          />
        </label>

        <label>
          Initial faction name
          <input
            v-model="newCampaignFactionName"
            type="text"
            placeholder="Gernanti Watch"
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
            Create campaign
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

    <article v-else-if="viewMode === ViewModes.Edit" class="dashboard-card">
      <h3>Edit campaign</h3>

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

        <label>
          Faction filter
          <select v-model="selectedFactionId">
            <option :value="null">All factions / No filter</option>
            <option
              v-for="faction in campaignFactions"
              :key="faction.id"
              :value="faction.id"
            >
              {{ faction.name }}
            </option>
          </select>
        </label>

        <label>
          Active Character / Person
          <select v-model="selectedPersonId">
            <option :value="null">No active character</option>
            <option
              v-for="person in filteredPeople"
              :key="person.id"
              :value="person.id"
            >
              {{ person.name }} {{ person.characterProfileAvailable ? '' : '(No character sheet yet)' }}
            </option>
          </select>
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
            Update campaign
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
