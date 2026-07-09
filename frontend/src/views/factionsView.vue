<script setup lang="ts">
import { computed, reactive, ref, onBeforeMount } from "vue"
import { GetAPI, PostAPI, PutAPI, DeleteAPI } from "@/apihelpers";
import { useCampaignStore } from "@/stores/campaignStore";
import { ViewModes } from "@/types/viewTypes"
import { FactionDto } from "@/types/DataTransferObjects"

const {
  campaigns,
  selectedCampaignId,
  selectedCampaign,
  hasSelectedCampaign,
  setCampaigns,
  selectCampaign,
  clearSelectedCampaign,
} = useCampaignStore()

onBeforeMount(async () => {
  await fetchFactions()
  selectFaction()
})

const viewMode = ref<ViewModes>(ViewModes.Details)
const selectedFactionId = ref<number | null>(null)
const factions = ref<FactionDto[]>([])

const factionForm = reactive({
  name: "",
  type: "",
  location: "",
  description: "",
  tags: "",
})


const selectedFaction = computed(() => {
  if (factions.value.length === 0) return null
  return (
    factions.value.find(
      (faction) => faction.id === selectedFactionId.value,
    ) ?? factions.value[0]
  )
})

function selectFaction(factionId: number | null = null) {
  if (factionId === null && factions.value.length > 0) {
    selectedFactionId.value = factions.value[0].id
  } else {
    selectedFactionId.value = factionId
  }
  viewMode.value = ViewModes.Details
}

function resetFactionForm() {
  factionForm.name = ""
  factionForm.type = ""
  factionForm.location = ""
  factionForm.description = ""
  factionForm.tags = ""
}

function showAddFactionForm() {
  resetFactionForm()
  viewMode.value = ViewModes.Create
}

function showEditFactionForm() {
  if (!selectedFaction.value) {
    return
  }

  factionForm.name = selectedFaction.value.name
  factionForm.type = selectedFaction.value.type
  factionForm.location = selectedFaction.value.location
  factionForm.description = selectedFaction.value.description
  factionForm.tags = selectedFaction.value.tags.join(", ")

  viewMode.value = ViewModes.Edit
}

function cancelFactionForm() {
  viewMode.value = ViewModes.Details
}

function parseTags(tags: string) {
  return tags
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean)
}

async function fetchFactions() {
  if (!selectedCampaignId.value) {
    console.error("No campaign selected. Cannot fetch factions.")
    return
  }

  const response = await GetAPI(`campaigns/${selectedCampaignId.value}/factions`)
  if (response.success === false || !Array.isArray(response)) {
    console.error("Failed to fetch locations:", response.error ?? "Response is not an array")
    return
  } 
  factions.value = response as FactionDto[]
}

async function createFaction() {
  const name = factionForm.name.trim()
  if (!name || !selectedCampaignId.value) {
    return
  }

  const faction: FactionDto = {
    campaignId: selectedCampaignId.value,
    id: 0,
    name: name,
    type: factionForm.type.trim(),
    location: factionForm.location.trim(),
    description: factionForm.description.trim(),
    tags: parseTags(factionForm.tags),
  }

  const response = await PostAPI(`campaigns/${selectedCampaignId.value}/factions`, faction)
  if (response.success === false) {
    console.error("Failed to create faction:", response.error)
    return
  }
  const createdFaction = response as FactionDto

  factions.value = [...factions.value, createdFaction].sort((a, b) =>
    a.name.localeCompare(b.name),
  )
  resetFactionForm()
  selectFaction(createdFaction.id)
}

async function updateFaction() {
  const name = factionForm.name.trim()

  if (!name || !selectedFaction.value) {
    return
  }

  const updatedFaction: FactionDto = {
    ...selectedFaction.value,
    name: name,
    type: factionForm.type.trim(),
    location: factionForm.location.trim(),
    description: factionForm.description.trim(),
    tags: parseTags(factionForm.tags),
  }

  const response = await PutAPI(`campaigns/${selectedCampaignId.value}/factions/${updatedFaction.id}`, updatedFaction)
  if (response.success === false) {
    console.error("Failed to update faction:", response.error)
    return
  }

  await fetchFactions()
  resetFactionForm()
  selectFaction(updatedFaction.id)
}

async function deleteFaction(factionId: number) {
  if (!selectedCampaignId.value) {
    console.error("No campaign selected. Cannot delete faction.")
    return
  }

  const response = await DeleteAPI(`campaigns/${selectedCampaignId.value}/factions/${factionId}`)
  if (response.success === false) {
    console.error("Failed to delete faction:", response.error)
    return
  }

  await fetchFactions()
  selectFaction()
}

</script>

<template>
  <section class="resource-view">
    <header class="view-header">
      <h2>Factions</h2>
      <p>Track organizations, noble houses, churches, guilds, cults, gangs, and other power groups.</p>
    </header>

    <div class="resource-layout">
      <aside class="resource-list-panel">
        <div class="resource-list-header">
          <h3>Faction list</h3>

          <button type="button" @click="showAddFactionForm">
            Add faction
          </button>
        </div>

        <ul v-if="factions.length > 0" class="resource-list">
          <li
            v-for="faction in factions"
            :key="faction.id"
          >
            <button
              type="button"
              class="resource-list-item"
              :class="{
                selected:
                  viewMode === ViewModes.Details &&
                  selectedFaction?.id === faction.id,
              }"
              @click="selectFaction(faction.id)"
            >
              <span class="resource-list-kicker">
                {{ faction.type || "Faction" }}
              </span>

              <span class="resource-list-title">
                {{ faction.name }}
              </span>

              <span class="resource-list-meta">
                {{ faction.location || "No location" }}
              </span>
            </button>
          </li>
        </ul>

        <p v-else class="empty-text">
          No factions have been registered for this campaign yet.
        </p>
      </aside>

      <article class="resource-detail-panel">
        <template v-if="viewMode === ViewModes.Create || viewMode === ViewModes.Edit">
          <header class="resource-detail-header">
            <p class="resource-detail-kicker">
              {{ viewMode === ViewModes.Create ? "New faction" : "Edit faction" }}
            </p>

            <h3>
              {{ viewMode === ViewModes.Create ? "New Faction " : selectedFaction?.name }}
            </h3>
          </header>

          <form
            class="resource-form"
            @submit.prevent="viewMode === ViewModes.Create ? createFaction() : updateFaction()"
          >
            <label>
              Name
              <input
                v-model="factionForm.name"
                type="text"
                placeholder="Faction name"
                required
              />
            </label>

            <label>
              Type
              <input
                v-model="factionForm.type"
                type="text"
                placeholder="Arcane order, noble house, church, gang, guild, cult..."
              />
            </label>

            <label>
              Location
              <input
                v-model="factionForm.location"
                type="text"
                placeholder="Gernanti, Magic Academy, Mainland, Docks..."
              />
            </label>

            <label>
              Description
              <textarea
                v-model="factionForm.description"
                rows="10"
                placeholder="Write notes about this faction here..."
              />
            </label>

            <label>
              Tags
              <input
                v-model="factionForm.tags"
                type="text"
                placeholder="academy, noble, hostile, ally, cult, political"
              />
            </label>

            <div class="resource-form-actions">
              <button type="submit">
                {{ viewMode === ViewModes.Create ? "Save faction" : "Update faction" }}
              </button>

              <button
                type="button"
                class="secondary"
                @click="cancelFactionForm"
              >
                Cancel
              </button>
            </div>
          </form>
        </template>

        <template v-else-if="selectedFaction">
          <header class="resource-detail-header with-actions">
            <div class="resource-detail-title">
              <p class="resource-detail-kicker">
                {{ selectedFaction.type || "Faction" }}
              </p>

              <h3>{{ selectedFaction.name }}</h3>
            </div>

            <div class="resource-detail-actions">
              <button
                type="button"
                class="secondary"
                @click="showEditFactionForm"
              >
                Edit
              </button>
              <button
                type="button"
                class="danger"
                @click="deleteFaction(selectedFaction.id)"
              >
                Delete
              </button>
            </div>
          </header>

          <dl class="resource-facts">
            <div>
              <dt>Type</dt>
              <dd>{{ selectedFaction.type || "None registered" }}</dd>
            </div>

            <div>
              <dt>Location</dt>
              <dd>{{ selectedFaction.location || "None registered" }}</dd>
            </div>
          </dl>

          <p class="resource-description">
            {{ selectedFaction.description || "No description has been added yet." }}
          </p>

          <div
            v-if="selectedFaction.tags.length > 0"
            class="tag-list"
          >
            <span
              v-for="tag in selectedFaction.tags"
              :key="tag"
              class="tag"
            >
              {{ tag }}
            </span>
          </div>
        </template>

        <template v-else>
          <p class="empty-text">
            Select a faction from the list or add a new one.
          </p>
        </template>
      </article>
    </div>
  </section>
</template>