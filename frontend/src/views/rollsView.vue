<script setup lang="ts">
import { ref, watch } from "vue"

import { DeleteAPI, GetAPI, PostAPI } from "@/apihelpers"
import { useSessionContext } from "@/composables/useSessionContext"
import { useCampaignStore } from "@/stores/campaignStore"
import type {
  CampaignRollDto,
  RollEntryDto,
  RollMutationDto,
  SessionRollDto,
} from "@/types/DataTransferObjects"

const { selectedCampaignId } = useCampaignStore()
const { selectedSession } = useSessionContext()

const rollInput = ref<number | null>(null)
const sessionRolls = ref<SessionRollDto | null>(null)
const campaignRollStats = ref<CampaignRollDto>({
  campaignId: selectedCampaignId.value ?? 0,
  numRolls: 0,
  rollAvg: 0,
  rollLuck: 0,
})

function formatRollLuck(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

async function fetchCampaignStats() {
  if (!selectedCampaignId.value) return
  const response = await GetAPI(
    `campaigns/${selectedCampaignId.value}/rolls/campaign-stats`,
  )
  if (response?.success === false) {
    console.error("Failed to fetch campaign stats:", response.error)
    return
  }
  campaignRollStats.value = response as CampaignRollDto
}

async function fetchSessionRolls() {
  sessionRolls.value = null
  if (!selectedCampaignId.value || !selectedSession.value) return
  const response = await GetAPI(
    `campaigns/${selectedCampaignId.value}/rolls/sessions/${selectedSession.value.id}`,
  )
  if (response?.success === false) {
    console.error("Failed to fetch session rolls:", response.error)
    return
  }
  sessionRolls.value = response as SessionRollDto
}

async function addRoll() {
  if (!selectedCampaignId.value || !selectedSession.value || rollInput.value === null) return
  const roll = Number(rollInput.value)
  if (!Number.isInteger(roll) || roll < 1 || roll > 20) return

  const payload: RollEntryDto = {
    sessionId: selectedSession.value.id,
    roll,
  }
  const response = await PostAPI(
    `campaigns/${selectedCampaignId.value}/rolls`,
    payload,
  )
  if (response?.success === false) {
    console.error("Failed to add roll:", response.error)
    return
  }
  const mutation = response as RollMutationDto
  sessionRolls.value = mutation.sessionStats
  campaignRollStats.value = mutation.campaignStats
  rollInput.value = null
}

async function deleteRolls() {
  if (
    !selectedCampaignId.value
    || !selectedSession.value
    || !sessionRolls.value?.rolls.length
  ) return

  const response = await DeleteAPI(
    `campaigns/${selectedCampaignId.value}/rolls/sessions/${selectedSession.value.id}`,
  )
  if (response?.success === false) {
    console.error("Failed to delete rolls:", response.error)
    return
  }
  const mutation = response as RollMutationDto
  sessionRolls.value = mutation.sessionStats
  campaignRollStats.value = mutation.campaignStats
  rollInput.value = null
}

watch(selectedCampaignId, () => void fetchCampaignStats(), { immediate: true })
watch(
  () => selectedSession.value?.id,
  () => void fetchSessionRolls(),
  { immediate: true },
)
</script>

<template>
  <article class="resource-detail-panel">
    <section v-if="selectedSession" class="rolls-section">
      <header class="resource-detail-header">
        <p class="resource-detail-kicker">
          Session {{ selectedSession.sessionNumber }} · {{ selectedSession.date }}
        </p>
        <h3>{{ selectedSession.title }}</h3>
      </header>

      <dl v-if="sessionRolls" class="resource-facts">
        <div>
          <dt>Rolls</dt>
          <dd>{{ sessionRolls.rolls.length }}</dd>
        </div>
        <div>
          <dt>Average</dt>
          <dd>{{ sessionRolls.average.toFixed(2) }}</dd>
        </div>
        <div>
          <dt>Roll luck</dt>
          <dd>{{ formatRollLuck(sessionRolls.rollLuck) }}</dd>
        </div>
      </dl>

      <form class="roll-input-form" @submit.prevent="addRoll">
        <label>
          Add d20 roll
          <input
            v-model.number="rollInput"
            type="number"
            min="1"
            max="20"
            placeholder="1–20"
            required
          />
        </label>
        <button type="submit">Add roll</button>
        <button
          v-if="sessionRolls?.rolls.length"
          type="button"
          class="danger"
          @click="deleteRolls"
        >
          Delete rolls
        </button>
      </form>

      <div v-if="sessionRolls?.rolls.length" class="roll-list">
        <span
          v-for="(roll, index) in sessionRolls.rolls"
          :key="index"
          class="roll-pill"
        >
          {{ roll }}
        </span>
      </div>
      <p v-else class="empty-text">
        No rolls have been registered for this session yet.
      </p>
    </section>

    <p v-else class="empty-text">
      Select or create a session before registering rolls.
    </p>

    <section class="rolls-section">
      <header class="resource-detail-header">
        <p class="resource-detail-kicker">Overall statistics</p>
        <h3>Campaign rolls</h3>
      </header>

      <dl class="resource-facts">
        <div>
          <dt>Total rolls</dt>
          <dd>{{ campaignRollStats.numRolls }}</dd>
        </div>
        <div>
          <dt>Average</dt>
          <dd>{{ campaignRollStats.rollAvg.toFixed(2) }}</dd>
        </div>
        <div>
          <dt>Roll luck</dt>
          <dd>{{ formatRollLuck(campaignRollStats.rollLuck) }}</dd>
        </div>
      </dl>
    </section>
  </article>
</template>
