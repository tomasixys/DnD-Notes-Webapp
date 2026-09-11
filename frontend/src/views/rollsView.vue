<script setup lang="ts">
import { useResourceEditor } from "@/composables/useResourceEditor"
import { ref, watch } from "vue"

import {
  DeleteAPI,
  GetAPI,
  isApiFailure,
  PostAPI,
} from "@/apihelpers"
import { useSessionContext } from "@/composables/useSessionContext"
import { useCampaignAuthorization } from "@/composables/useCampaignAuthorization"
import { useCampaignStore } from "@/stores/campaignStore"
import type {
  CampaignRollDto,
  RollEntryDto,
  RollMutationDto,
  SessionRollDto,
} from "@/types/DataTransferObjects"
import { withExpectedRevision } from "@/utils/concurrency"

const { selectedCampaignId } = useCampaignStore()
const {
  selectedSession,
  selectedSessionNumber,
  upsertSession,
} = useSessionContext()
const { canWriteSharedResources } = useCampaignAuthorization()

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
  const response = await GetAPI<CampaignRollDto>(
    `campaigns/${selectedCampaignId.value}/rolls/campaign-stats`,
  )
  if (isApiFailure(response)) {
    console.error("Failed to fetch campaign stats:", response.error)
    return
  }
  campaignRollStats.value = response
}

async function fetchSessionRolls() {
  sessionRolls.value = null
  if (!selectedCampaignId.value || !selectedSession.value) return
  const response = await GetAPI<SessionRollDto>(
    `campaigns/${selectedCampaignId.value}/rolls/sessions/${selectedSession.value.id}`,
  )
  if (isApiFailure(response)) {
    console.error("Failed to fetch session rolls:", response.error)
    return
  }
  sessionRolls.value = response
}

async function addRoll() {
  if (!selectedCampaignId.value || !selectedSession.value || rollInput.value === null) return
  const roll = Number(rollInput.value)
  if (!Number.isInteger(roll) || roll < 1 || roll > 20) return

  const payload: RollEntryDto = {
    sessionId: selectedSession.value.id,
    roll,
  }
  const response = await PostAPI<RollMutationDto>(
    withExpectedRevision(
      `campaigns/${selectedCampaignId.value}/rolls`,
      selectedSession.value.revision,
    ),
    payload,
  )
  if (isApiFailure(response)) {
    console.error("Failed to add roll:", response.error)
    return
  }
  sessionRolls.value = response.sessionStats
  upsertSession({
    ...selectedSession.value,
    revision: response.sessionStats.revision,
  })
  campaignRollStats.value = response.campaignStats
  rollInput.value = null
}

async function deleteRolls() {
  if (
    !selectedCampaignId.value
    || !selectedSession.value
    || !sessionRolls.value?.rolls.length
  ) return

  const response = await DeleteAPI<RollMutationDto>(
    withExpectedRevision(
      `campaigns/${selectedCampaignId.value}/rolls/sessions/${selectedSession.value.id}`,
      selectedSession.value.revision,
    ),
  )
  if (isApiFailure(response)) {
    console.error("Failed to delete rolls:", response.error)
    return
  }
  sessionRolls.value = response.sessionStats
  upsertSession({
    ...selectedSession.value,
    revision: response.sessionStats.revision,
  })
  campaignRollStats.value = response.campaignStats
  rollInput.value = null
}

watch(selectedCampaignId, () => void fetchCampaignStats(), { immediate: true })
watch(
  () => selectedSession.value?.id,
  () => void fetchSessionRolls(),
  { immediate: true },
)

useResourceEditor(() => selectedCampaignId.value && rollInput.value !== null ? [{
  campaignId: selectedCampaignId.value, resourceType: "session", resourceId: null,
}] : [])
</script>

<template>
  <article class="resource-detail-panel">
    <section v-if="selectedSession" class="rolls-section">
      <header class="resource-detail-header">
        <p class="resource-detail-kicker">
          Session {{ selectedSessionNumber }} · {{ selectedSession.date }}
        </p>
        <h3>{{ selectedSession.title }}</h3>
      </header>

      <dl v-if="sessionRolls" class="resource-facts">
        <div>
          <dt>Your rolls</dt>
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

      <form
        v-if="canWriteSharedResources"
        class="roll-input-form"
        @submit.prevent="addRoll"
      >
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
          Delete your rolls
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
        You have not registered any rolls for this session yet.
      </p>

      <section
        v-if="sessionRolls?.otherContributors.length"
        class="roll-contributors"
      >
        <header class="resource-detail-header">
          <p class="resource-detail-kicker">Other players</p>
          <h3>Session statistics</h3>
        </header>

        <div class="roll-contributor-list">
          <article
            v-for="contributor in sessionRolls.otherContributors"
            :key="contributor.userId ?? 'legacy'"
            class="roll-contributor-card"
          >
            <h4>{{ contributor.displayName }}</h4>
            <dl class="resource-facts compact">
              <div>
                <dt>Rolls</dt>
                <dd>{{ contributor.numRolls }}</dd>
              </div>
              <div>
                <dt>Average</dt>
                <dd>{{ contributor.average.toFixed(2) }}</dd>
              </div>
              <div>
                <dt>Roll luck</dt>
                <dd>{{ formatRollLuck(contributor.rollLuck) }}</dd>
              </div>
            </dl>
          </article>
        </div>
      </section>
    </section>

    <p v-else class="empty-text">
      Select or create a session before registering rolls.
    </p>

    <section class="rolls-section">
      <header class="resource-detail-header">
        <p class="resource-detail-kicker">Your overall statistics</p>
        <h3>Your campaign rolls</h3>
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
