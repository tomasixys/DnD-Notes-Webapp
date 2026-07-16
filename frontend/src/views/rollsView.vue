<script setup lang="ts">
import { ref, onBeforeMount } from "vue"
import { CampaignRollDto, SessionListItemDto, SessionRollDto, RollEntryDto } from "@/types/DataTransferObjects"
import { GetAPI, PostAPI, PutAPI, DeleteAPI } from "@/apihelpers";
import { useCampaignStore } from "@/stores/campaignStore";
import { useRouteEntrySelection } from "@/composables/useRouteEntrySelection"

const {
  campaigns,
  selectedCampaignId,
  selectedCampaign,
  hasSelectedCampaign,
  setCampaigns,
  selectCampaign,
  clearSelectedCampaign,
} = useCampaignStore()


const sessions = ref<SessionListItemDto[]>([])
const rollInput = ref<number | null>(null)

const sessionRolls = ref<SessionRollDto>()
const campaignRollStats = ref<CampaignRollDto>({
  campaignId: selectedCampaignId.value ?? 0,
  numRolls: 0,
  rollAvg: 0,
  rollLuck: 0,
})

const {
  entryIdFromUrl,
  selectedEntry,
  openEntry,
  ensureDefaultEntry,
  replaceWithFirstEntry,
} = useRouteEntrySelection({
  entries: sessions,
  routeName: "Rolls",
  onRouteEntryChange: () => { fetchSessionRolls()},
})


onBeforeMount(async () => {
  await fetchSessionList()
  await fetchCampaignStats()
  await ensureDefaultEntry()
})




function formatRollLuck(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

async function fetchSessionList() {
  if (!selectedCampaignId.value) {
    console.error("No campaign selected. Cannot fetch session list.")
    return
  }

  const response = await GetAPI(`campaigns/${selectedCampaignId.value}/sessions`)
  if (response.success === false) {
    console.error("Failed to fetch session list:", response.error)
    return
  }
  sessions.value = response as SessionListItemDto[]
}

async function fetchCampaignStats()
{
  const response = await GetAPI(`campaigns/${selectedCampaignId.value}/rolls/campaign-stats`)

  if (response.success === false) {
    console.error("Failed to fetch campaign stats:", response.error)
    return
  }

  campaignRollStats.value = response as CampaignRollDto
}

async function fetchSessionRolls()
{
  const response = await GetAPI(`campaigns/${selectedCampaignId.value}/rolls/sessions/${entryIdFromUrl.value}`)

  if (response.success === false) {
    console.error("Failed to fetch session rolls:", response.error)
    return
  }

  sessionRolls.value = response as SessionRollDto
}

async function addRoll() {
  if (!selectedEntry.value || rollInput.value === null) return

  const roll = Number(rollInput.value)
  if (roll < 1 || roll > 20 || roll % 1 !== 0) return

  const rolldto: RollEntryDto = {
    sessionId: selectedEntry.value.id,
    roll: roll,
  }
  const response = await PostAPI(`campaigns/${selectedCampaignId.value}/rolls`, rolldto)
  if (response.success === false) {
    console.error("Failed to add roll:", response.error)
    return
  }
  await fetchSessionRolls();
  await fetchCampaignStats();

  rollInput.value = null
}

async function deleteRolls() {
  if (!selectedEntry.value || (sessionRolls.value?.rolls.length ?? 0) < 1) return 

  const response = await DeleteAPI(`campaigns/${selectedCampaignId.value}/rolls/sessions/${selectedEntry.value.id}`)
  if (response.success === false) {
    console.error("Failed to delete roll:", response.error)
    return
  }
  await fetchSessionRolls();
  await fetchCampaignStats();

  rollInput.value = null
}
</script>

<template>
  <section class="resource-view">
    <header class="view-header">
      <h2>Rolls</h2>
      <p>Track simple d20 rolls for the active player character.</p>
    </header>

    <div class="resource-layout">
      <aside class="resource-list-panel">
        <div class="resource-list-header">
          <h3>Sessions</h3>
        </div>

        <ul v-if="sessions.length > 0" class="resource-list">
          <li
            v-for="session in sessions"
            :key="session.sessionNumber"
          >
            <button
              type="button"
              class="resource-list-item"
              :class="{
                selected: selectedEntry?.id === session.id,
              }"
              @click="openEntry(session.id)"
            >
              <span class="resource-list-kicker">
                Session {{ session.sessionNumber }}
              </span>

              <span class="resource-list-meta">
                {{ session.date }}
              </span>

              <span class="resource-list-title">
                {{ session.title }}
              </span>
            </button>
          </li>
        </ul>

        <p v-else class="empty-text">
          No sessions have been registered for this campaign yet.
        </p>
      </aside>

      <article class="resource-detail-panel">
        <section class="rolls-section">
          <header class="resource-detail-header">
            <p class="resource-detail-kicker">
              Overall statistics
            </p>

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

        <section v-if="selectedEntry" class="rolls-section">
          <header class="resource-detail-header">
            <p class="resource-detail-kicker">
              Session {{ selectedEntry.sessionNumber }} · {{ selectedEntry.date }}
            </p>

            <h3>{{ selectedEntry.title }}</h3>
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

          <p v-else class="empty-text">
            No rolls have been registered for this session yet.
          </p>

          <form class="roll-input-form" @submit.prevent="addRoll">
            <label>
              Add d20 roll
              <input
                v-model.number="rollInput"
                type="number"
                min="1"
                max="20"
                placeholder="1-20"
                required
              />
            </label>

            <button type="submit">
              Add roll
            </button>
            <button
              v-if="sessionRolls && sessionRolls.rolls.length > 0"
              type="button"
              class="danger"
              @click="deleteRolls"
            >
              Delete rolls
            </button>
          </form>

          <div
            v-if="sessionRolls && sessionRolls.rolls.length > 0"
            class="roll-list"
          >
            <span
              v-for="(roll, index) in sessionRolls.rolls"
              :key="index"
              class="roll-pill"
            >
              {{ roll }}
            </span>
          </div>
        </section>

        <p v-else class="empty-text">
          Select a session to view and register rolls.
        </p>
      </article>
    </div>
  </section>
</template>