<script setup lang="ts">
import { computed, provide, ref, watch } from "vue"
import { RouterView, useRoute, useRouter } from "vue-router"

import { GetAPI } from "@/apihelpers"
import { sessionContextKey } from "@/composables/useSessionContext"
import { useCampaignStore } from "@/stores/campaignStore"
import type { SessionListItemDto } from "@/types/DataTransferObjects"
import {
  compareBySessionNumberDescending,
  removeById,
  upsertById,
} from "@/utils/resourceCollections"

const route = useRoute()
const router = useRouter()
const { selectedCampaignId } = useCampaignStore()

const sessions = ref<SessionListItemDto[]>([])
const selectionRevision = ref(0)

const selectedSessionId = computed(() => {
  const rawValue = Array.isArray(route.params.id)
    ? route.params.id[0]
    : route.params.id
  const sessionId = Number(rawValue)
  return Number.isInteger(sessionId) && sessionId > 0 ? sessionId : null
})

const selectedSession = computed(() =>
  sessions.value.find((session) => session.id === selectedSessionId.value) ?? null,
)

const showingRolls = computed(() => route.name === "SessionRolls")

function childRouteName() {
  return route.name === "SessionRolls" ? "SessionRolls" : "SessionNotes"
}

function routeParams(sessionId: number | "" = "") {
  return sessionId === "" ? {} : { id: sessionId }
}

async function loadSessions() {
  sessions.value = []
  if (!selectedCampaignId.value) return

  const response = await GetAPI(`campaigns/${selectedCampaignId.value}/sessions`)
  if (!Array.isArray(response)) {
    console.error("Failed to fetch sessions:", response?.error ?? "Response is not an array")
    return
  }
  sessions.value = response as SessionListItemDto[]
}

function upsertSession(session: SessionListItemDto) {
  sessions.value = upsertById(
    sessions.value,
    session,
    compareBySessionNumberDescending,
  )
}

function removeSession(sessionId: number) {
  sessions.value = removeById(sessions.value, sessionId)
}

async function openSession(sessionId: number, replace = false) {
  selectionRevision.value += 1
  if (selectedSessionId.value === sessionId) return

  const destination = {
    name: childRouteName(),
    params: routeParams(sessionId),
  }
  if (replace) await router.replace(destination)
  else await router.push(destination)
}

async function ensureDefaultSession() {
  if (selectedSessionId.value !== null || sessions.value.length === 0) return
  await openSession(sessions.value[0].id, true)
}

async function replaceWithFirstSession() {
  const firstSession = sessions.value[0]
  selectionRevision.value += 1
  await router.replace({
    name: childRouteName(),
    params: routeParams(firstSession?.id ?? ""),
  })
}

provide(sessionContextKey, {
  sessions,
  selectedSession,
  selectedSessionId,
  selectionRevision,
  loadSessions,
  upsertSession,
  removeSession,
  openSession,
  replaceWithFirstSession,
})

watch(
  selectedCampaignId,
  async () => {
    await loadSessions()
    await ensureDefaultSession()
  },
  { immediate: true },
)
</script>

<template>
  <section class="resource-view">
    <header class="view-header">
      <div class="view-header-copy">
        <h2>Sessions</h2>
        <p>
          {{ showingRolls
            ? "Track d20 rolls for the selected session."
            : "Review and maintain session notes for the active campaign." }}
        </p>
      </div>
    </header>

    <div class="resource-layout">
      <aside class="resource-list-panel">
        <div class="resource-list-header">
          <h3>Session list</h3>
          <span>{{ sessions.length }}</span>
        </div>

        <ul v-if="sessions.length" class="resource-list">
          <li v-for="session in sessions" :key="session.id">
            <button
              type="button"
              class="resource-list-item"
              :class="{ selected: selectedSession?.id === session.id }"
              @click="openSession(session.id)"
            >
              <span class="resource-list-kicker">
                Session #{{ session.sessionNumber }}
              </span>
              <span class="resource-list-meta">{{ session.date }}</span>
              <span class="resource-list-title">{{ session.title }}</span>
            </button>
          </li>
        </ul>

        <p v-else class="empty-text">
          No sessions have been registered for this campaign yet.
        </p>
      </aside>

      <RouterView />
    </div>
  </section>
</template>
