<script setup lang="ts">
import { computed, reactive, ref } from "vue"
import { FactionDto } from "@/assets/DataTransferObjects"
import { factionsExample } from "@/assets/exampleData"



type FactionViewMode = "detail" | "new" | "edit"

const activeCampaignId = ref<number>(1)
const selectedFactionId = ref<number | null>(null)
const viewMode = ref<FactionViewMode>("detail")

const factions = ref<FactionDto[]>(factionsExample)

const factionForm = reactive({
  name: "",
  type: "",
  location: "",
  description: "",
  tags: "",
})

const campaignFactions = computed(() => {
  return factions.value
    .filter((faction) => faction.campaignId === activeCampaignId.value)
    .sort((a, b) => a.name.localeCompare(b.name))
})

const nextFactionId = computed(() => {
  const currentHighestFactionId = Math.max(
    0,
    ...factions.value
      .filter((faction) => faction.campaignId === activeCampaignId.value)
      .map((faction) => faction.factionId),
  )

  return currentHighestFactionId + 1
})

const selectedFaction = computed(() => {
  if (campaignFactions.value.length === 0) {
    return null
  }

  return (
    campaignFactions.value.find(
      (faction) => faction.factionId === selectedFactionId.value,
    ) ?? campaignFactions.value[0]
  )
})

function selectFaction(factionId: number) {
  selectedFactionId.value = factionId
  viewMode.value = "detail"
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
  viewMode.value = "new"
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

  viewMode.value = "edit"
}

function cancelFactionForm() {
  viewMode.value = "detail"
}

function parseTags(tags: string) {
  return tags
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean)
}

function createFaction() {
  const name = factionForm.name.trim()

  if (!name) {
    return
  }

  const faction: FactionDto = {
    campaignId: activeCampaignId.value,
    factionId: nextFactionId.value,
    name,
    type: factionForm.type.trim(),
    location: factionForm.location.trim(),
    description: factionForm.description.trim(),
    tags: parseTags(factionForm.tags),
  }

  factions.value.push(faction)
  selectedFactionId.value = faction.factionId
  resetFactionForm()
  viewMode.value = "detail"
}

function updateFaction() {
  if (!selectedFaction.value) {
    return
  }

  const name = factionForm.name.trim()

  if (!name) {
    return
  }

  const factionIndex = factions.value.findIndex(
    (faction) =>
      faction.campaignId === selectedFaction.value?.campaignId &&
      faction.factionId === selectedFaction.value?.factionId,
  )

  if (factionIndex === -1) {
    return
  }

  factions.value[factionIndex] = {
    ...factions.value[factionIndex],
    name,
    type: factionForm.type.trim(),
    location: factionForm.location.trim(),
    description: factionForm.description.trim(),
    tags: parseTags(factionForm.tags),
  }

  resetFactionForm()
  viewMode.value = "detail"
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

        <ul v-if="campaignFactions.length > 0" class="resource-list">
          <li
            v-for="faction in campaignFactions"
            :key="faction.factionId"
          >
            <button
              type="button"
              class="resource-list-item"
              :class="{
                selected:
                  viewMode === 'detail' &&
                  selectedFaction?.factionId === faction.factionId,
              }"
              @click="selectFaction(faction.factionId)"
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
        <template v-if="viewMode === 'new' || viewMode === 'edit'">
          <header class="resource-detail-header">
            <p class="resource-detail-kicker">
              {{ viewMode === "new" ? "New faction" : "Edit faction" }}
            </p>

            <h3>
              {{ viewMode === "new" ? "Faction " + nextFactionId : selectedFaction?.name }}
            </h3>
          </header>

          <form
            class="resource-form"
            @submit.prevent="viewMode === 'new' ? createFaction() : updateFaction()"
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
                {{ viewMode === "new" ? "Save faction" : "Update faction" }}
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
            <div>
              <p class="resource-detail-kicker">
                {{ selectedFaction.type || "Faction" }}
              </p>

              <h3>{{ selectedFaction.name }}</h3>
            </div>

            <button
              type="button"
              class="secondary"
              @click="showEditFactionForm"
            >
              Edit
            </button>
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