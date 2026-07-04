<script setup lang="ts">
import { computed, reactive, ref } from "vue"
import { CampaignsDto } from "@/assets/DataTransferObjects";
import { campaignsExample } from "@/assets/exampleData"



const newCampaign = reactive<CampaignsDto>({
  id: 0,
  name: "",
  playerCharacter: "",
  description: "",
  sessionCount: 0,
  imageUrl: "",
})

const campaigns = ref<CampaignsDto[]>(campaignsExample)

enum ViewModes {
  Current,
  Create,
  Selection,
}

const viewMode = ref<ViewModes>(ViewModes.Current)

const selectedCampaignId = ref(1)

const selectedCampaign = computed(() => {
  return campaigns.value.find((campaign) => campaign.id === selectedCampaignId.value) ?? null
})


function showCurrentCampaign() {
  viewMode.value = ViewModes.Current
}

function showNewCampaignForm() {
  viewMode.value = ViewModes.Create
}

function showCampaignList() {
  viewMode.value = ViewModes.Selection
}

function createCampaign() {
  const nextId = Math.max(0, ...campaigns.value.map((campaign) => campaign.id)) + 1

  const campaign = <CampaignsDto>{
    id: nextId,
    name: newCampaign.name.trim(),
    playerCharacter: newCampaign.playerCharacter.trim(),
    description: newCampaign.description.trim(),
    sessionCount: 0,
    imageUrl: newCampaign.imageUrl.trim(),
  }

  if (!campaign.name) {
    return
  }

  campaigns.value.push(campaign)
  selectedCampaignId.value = campaign.id

  newCampaign.name = ""
  newCampaign.playerCharacter = ""
  newCampaign.description = ""
  newCampaign.imageUrl = ""

  viewMode.value = ViewModes.Current
}

function switchCampaign(campaignId) {
  selectedCampaignId.value = campaignId
  viewMode.value = ViewModes.Current
}

function deleteCampaign(campaignId) {
  campaigns.value = campaigns.value.filter((campaign) => campaign.id !== campaignId)

  if (selectedCampaignId.value === campaignId) {
    selectedCampaignId.value = campaigns.value[0]?.id ?? null
  }

  if (campaigns.value.length === 0) {
    viewMode.value = ViewModes.Create
  }
}
</script>

<template>
  <section class="dashboard-view">
    <header class="view-header">
      <h2>Dashboard</h2>
      <p>Choose the active campaign or create a new one.</p>
    </header>

    <article v-if="viewMode === ViewModes.Current" class="dashboard-card">
      <template v-if="selectedCampaign">
        <div class="campaign-summary">
          <img
            v-if="selectedCampaign.imageUrl"
            class="campaign-image"
            :src="selectedCampaign.imageUrl"
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

      <form class="campaign-form" @submit.prevent="createCampaign">
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
            v-model="newCampaign.imageUrl"
            type="text"
            placeholder="/src/assets/banner.png"
          />
        </label>

        <div class="dashboard-actions">
          <button type="submit">
            Create campaign
          </button>

          <button type="button" class="secondary" @click="showCurrentCampaign">
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
              {{ campaign.sessionCount }} sessions
            </small>

          </div>

          <div class="campaign-list-actions">
            <button type="button" @click="switchCampaign(campaign.id)">
              Switch to campaign
            </button>

            <button
              type="button"
              class="danger"
              @click="deleteCampaign(campaign.id)"
            >
              Delete campaign
            </button>
          </div>
        </li>
      </ul>

      <p v-else>No campaigns have been created yet.</p>

      <div class="dashboard-actions">
        <button type="button" @click="showNewCampaignForm">
          Start new campaign
        </button>

        <button type="button" class="secondary" @click="showCurrentCampaign">
          Back
        </button>
      </div>
    </article>
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