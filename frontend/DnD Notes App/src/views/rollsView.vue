<script setup lang="ts">
import { computed, ref } from "vue"
import { CampaignRollDto, SessionListItemDto, SessionRollDto } from "@/assets/DataTransferObjects"
import { campaignRollStatsExample, sessionRollsExample, sessionListExample} from "@/assets/exampleData"


const activeCampaignId = ref<number>(1)
const selectedSessionId = ref<number | null>(null)
const rollInput = ref<number | null>(null)

const sessions = ref<SessionListItemDto[]>(sessionListExample)
const campaignRollStats = ref<CampaignRollDto>(campaignRollStatsExample)
const sessionRolls = ref<SessionRollDto[]>(sessionRollsExample)

const campaignSessions = computed(() => {
  return sessions.value
    .filter((session) => session.campaignId === activeCampaignId.value)
    .sort((a, b) => b.sessionId - a.sessionId)
})

const selectedSession = computed(() => {
  if (campaignSessions.value.length === 0) {
    return null
  }

  return (
    campaignSessions.value.find(
      (session) => session.sessionId === selectedSessionId.value,
    ) ?? campaignSessions.value[0]
  )
})

const selectedSessionRolls = computed(() => {
  if (!selectedSession.value) {
    return null
  }

  return (
    sessionRolls.value.find(
      (sessionRoll) =>
        sessionRoll.campaignId === activeCampaignId.value &&
        sessionRoll.sessionId === selectedSession.value?.sessionId,
    ) ?? null
  )
})

function selectSession(sessionId: number) {
  selectedSessionId.value = sessionId
}

function formatRollLuck(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

function addRoll() {
  if (!selectedSession.value || rollInput.value === null) {
    return
  }

  const roll = Number(rollInput.value)

  if (roll < 1 || roll > 20 || roll % 1 !== 0) {
  return
}

  let sessionRoll = sessionRolls.value.find(
    (item) =>
      item.campaignId === activeCampaignId.value &&
      item.sessionId === selectedSession.value?.sessionId,
  )

  if (!sessionRoll) {
    sessionRoll = {
      campaignId: activeCampaignId.value,
      sessionId: selectedSession.value.sessionId,
      rolls: [],
      average: 0,
      rollLuck: 0,
    }

    sessionRolls.value.push(sessionRoll)
  }

  sessionRoll.rolls.push(roll)

  // Later:
  // POST roll to backend
  // Backend returns updated SessionRollDto and CampaignRollDto
  // Replace local stats with backend response

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

        <ul v-if="campaignSessions.length > 0" class="resource-list">
          <li
            v-for="session in campaignSessions"
            :key="session.sessionId"
          >
            <button
              type="button"
              class="resource-list-item"
              :class="{
                selected: selectedSession?.sessionId === session.sessionId,
              }"
              @click="selectSession(session.sessionId)"
            >
              <span class="resource-list-kicker">
                Session {{ session.sessionId }}
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

        <section v-if="selectedSession" class="rolls-section">
          <header class="resource-detail-header">
            <p class="resource-detail-kicker">
              Session {{ selectedSession.sessionId }} · {{ selectedSession.date }}
            </p>

            <h3>{{ selectedSession.title }}</h3>
          </header>

          <dl v-if="selectedSessionRolls" class="resource-facts">
            <div>
              <dt>Rolls</dt>
              <dd>{{ selectedSessionRolls.rolls.length }}</dd>
            </div>

            <div>
              <dt>Average</dt>
              <dd>{{ selectedSessionRolls.average.toFixed(2) }}</dd>
            </div>

            <div>
              <dt>Roll luck</dt>
              <dd>{{ formatRollLuck(selectedSessionRolls.rollLuck) }}</dd>
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
          </form>

          <div
            v-if="selectedSessionRolls && selectedSessionRolls.rolls.length > 0"
            class="roll-list"
          >
            <span
              v-for="(roll, index) in selectedSessionRolls.rolls"
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