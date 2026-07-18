<script setup lang="ts">
import { reactive, ref, onBeforeMount } from "vue"
import { GetAPI, PostAPI, PutAPI, DeleteAPI } from "@/apihelpers";
import { useCampaignStore } from "@/stores/campaignStore";
import { ViewModes } from "@/types/viewTypes"
import type { FactionDataDto, FactionDto } from "@/types/DataTransferObjects"
import { useRouteEntrySelection } from "@/composables/useRouteEntrySelection"
import ResourceTag from "@/components/ResourceTag.vue"


const viewMode = ref<ViewModes>(ViewModes.Details)
const factions = ref<FactionDto[]>([])

const {
  entryIdFromUrl,
  selectedEntry,
  openEntry,
  ensureDefaultEntry,
  replaceWithFirstEntry,
} = useRouteEntrySelection({
  entries: factions,
  routeName: "Factions",
  onRouteEntryChange: () => {
    viewMode.value = ViewModes.Details
  },
})

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
  await ensureDefaultEntry()
})


const factionForm = reactive({
  name: "",
  type: "",
  location: "",
  description: "",
  tags: "",
})



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
  if (!selectedEntry.value) {
    return
  }

  factionForm.name = selectedEntry.value.name
  factionForm.type = selectedEntry.value.type
  factionForm.location = selectedEntry.value.location
  factionForm.description = selectedEntry.value.description
  factionForm.tags = selectedEntry.value.tags
    .map((tag) => tag.value)
    .join(", ")

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

  const faction: FactionDataDto = {
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

  await fetchFactions()
  resetFactionForm()
  await openEntry(createdFaction.id)
}


async function updateFaction() {
  const name = factionForm.name.trim()

  if (!name || !selectedEntry.value) {
    return
  }

  const updatedFaction: FactionDataDto = {
    name: name,
    type: factionForm.type.trim(),
    location: factionForm.location.trim(),
    description: factionForm.description.trim(),
    tags: parseTags(factionForm.tags),
  }

  const response = await PutAPI(`campaigns/${selectedCampaignId.value}/factions/${selectedEntry.value.id}`, updatedFaction)
  if (response.success === false) {
    console.error("Failed to update faction:", response.error)
    return
  }

  await fetchFactions()
  resetFactionForm()
  viewMode.value = ViewModes.Details
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
  await replaceWithFirstEntry()
}


</script>

<template>
  <section class="resource-view">
    <header class="view-header with-actions">
      <div class="view-header-copy">
        <h2>Factions</h2>
        <p>Track organizations, noble houses, churches, guilds, cults, gangs, and other power groups.</p>
      </div>

      <button type="button" @click="showAddFactionForm">
        Add faction
      </button>
    </header>

    <div class="resource-layout">
      <aside class="resource-list-panel">
        <div class="resource-list-header">
          <h3>Faction list</h3>
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
                  selectedEntry?.id === faction.id,
              }"
              @click="openEntry(faction.id)"
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
              {{ viewMode === ViewModes.Create ? "New Faction " : selectedEntry?.name }}
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

        <template v-else-if="selectedEntry">
          <header class="resource-detail-header with-actions">
            <div class="resource-detail-title">
              <p class="resource-detail-kicker">
                {{ selectedEntry.type || "Faction" }}
              </p>

              <h3>{{ selectedEntry.name }}</h3>
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
                @click="deleteFaction(selectedEntry.id)"
              >
                Delete
              </button>
            </div>
          </header>

          <dl class="resource-facts">
            <div>
              <dt>Type</dt>
              <dd>{{ selectedEntry.type || "None registered" }}</dd>
            </div>

            <div>
              <dt>Location</dt>
              <dd>{{ selectedEntry.location || "None registered" }}</dd>
            </div>
          </dl>

          <p class="resource-description">
            {{ selectedEntry.description || "No description has been added yet." }}
          </p>

          <div
            v-if="selectedEntry.tags.length > 0"
            class="tag-list"
          >
            <ResourceTag
              v-for="tag in selectedEntry.tags"
              :key="tag.value"
              :tag="tag"
            />
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
