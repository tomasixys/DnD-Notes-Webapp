<script setup lang="ts">
import { computed, reactive, ref, onBeforeMount } from "vue"
import { GetAPI, PostAPI, PutAPI, DeleteAPI } from "@/assets/apihelpers";
import { useCampaignStore } from "@/stores/campaignStore";
import { ViewModes } from "@/types/viewTypes"
import { SessionListItemDto } from "@/types/DataTransferObjects"

const {
  campaigns,
  selectedCampaignId,
  selectedCampaign,
  hasSelectedCampaign,
  setCampaigns,
  selectCampaign,
  clearSelectedCampaign,
} = useCampaignStore()


const viewMode = ref<ViewModes>(ViewModes.Details)
const selectedSessionNumber = ref<number | null>(null)
const sessions = ref<SessionListItemDto[]>([])

const sessionForm = reactive({
  date: new Date().toISOString().slice(0, 10),
  title: "",
  description: "",
  tags: "",
})

onBeforeMount(async () => {
  await fetchSessions()
  selectSession()
})

const nextSessionId = computed(() => {
  const currentHighestSessionNumber = Math.max(
    0,
    ...sessions.value
      .filter((session) => session.campaignId === selectedCampaignId.value)
      .map((session) => session.sessionNumber),
  )
  return currentHighestSessionNumber + 1
})

const selectedSession = computed(() => {
  if (sessions.value.length === 0) {
    return null
  }
  return (
    sessions.value.find(
      (session) => session.sessionNumber === selectedSessionNumber.value,
    ) ?? sessions.value[0]
  )
})

function selectSession(sessionNumber: number | null = null) {
  if (sessionNumber === null && sessions.value.length > 0) {
    selectedSessionNumber.value = sessions.value[0].sessionNumber
  } else {
    selectedSessionNumber.value = sessionNumber
  }
  viewMode.value = ViewModes.Details
}

function resetSessionForm() {
  sessionForm.date = new Date().toISOString().slice(0, 10)
  sessionForm.title = ""
  sessionForm.description = ""
  sessionForm.tags = ""
}

function showAddSessionForm() {
  resetSessionForm()
  viewMode.value = ViewModes.Create
}

function showEditSessionForm() {
  if (!selectedSession.value) {
    return
  }

  sessionForm.date = selectedSession.value.date
  sessionForm.title = selectedSession.value.title
  sessionForm.description = selectedSession.value.description
  sessionForm.tags = selectedSession.value.tags.join(", ")

  viewMode.value = ViewModes.Edit
}

function cancelSessionForm() {
  viewMode.value = ViewModes.Details
}

async function fetchSessions() {
  if (!selectedCampaignId.value) {
    console.error("No selected campaign to fetch sessions for.")
    return
  }

  const response = await GetAPI(`campaigns/${selectedCampaignId.value}/sessions`)
  if (response.success === false || !Array.isArray(response)) {
    console.error("Failed to fetch sessions:", response.error ?? "Response is not an array")
    return
  }
  sessions.value = response as SessionListItemDto[]
}

async function createSession() {
  const title = sessionForm.title.trim()

  if (!title || !selectedCampaignId.value) {
    return
  }

  const session: SessionListItemDto = {
    id: 0,
    campaignId: selectedCampaignId.value,
    sessionNumber: nextSessionId.value,
    date: sessionForm.date,
    title,
    description: sessionForm.description.trim(),
    tags: sessionForm.tags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean),
  }
  const response = await PostAPI(`campaigns/${selectedCampaignId.value}/sessions`, session)
  if (response.success === false) {
    console.error("Failed to create session:", response.message)
    return
  }
  const createdSession = response as SessionListItemDto
  sessions.value = [...sessions.value, createdSession].sort((a, b) => a.sessionNumber - b.sessionNumber)
  resetSessionForm()
  selectSession(createdSession.sessionNumber)
}

async function updateSession() {
  const title = sessionForm.title.trim()
  if (!title || selectedSession.value?.id === undefined) {
    return
  }
  const data: SessionListItemDto = {
    ...selectedSession.value,
    date: sessionForm.date,
    title: sessionForm.title.trim(),
    description: sessionForm.description.trim(),
    tags: sessionForm.tags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean),
  }
  const response = await PutAPI(`campaigns/${selectedCampaignId.value}/sessions/${selectedSession.value?.id}`, data)
  if (response.success === false) {
    console.error("Failed to update session:", response.message)
    return
  }
  await fetchSessions()
  resetSessionForm()
  selectSession(selectedSession.value?.sessionNumber)
}

async function deleteSession() {
  if (!selectedSession.value?.id) {
    return
  }
  const response = await DeleteAPI(`campaigns/${selectedCampaignId.value}/sessions/${selectedSession.value.id}`)
  if (response.success === false) {
    console.error("Failed to delete session:", response.message)
    return
  }
  await fetchSessions()
  selectSession()
}

</script>

<template>
  <section class="resource-view">
    <header class="view-header">
      <h2>Sessions</h2>
      <p>Review session notes for the active campaign.</p>
    </header>

    <div class="resource-layout">
      <aside class="resource-list-panel">
        <div class="resource-list-header">
          <h3>Session list</h3>

          <button type="button" @click="showAddSessionForm">
            Add session
          </button>
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
                selected:
                  viewMode === ViewModes.Details &&
                  selectedSession?.sessionNumber === session.sessionNumber,
              }"
              @click="selectSession(session.sessionNumber)"
            >
              <span class="resource-list-kicker">
                Session #{{ session.sessionNumber }}
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
        <template v-if="viewMode === ViewModes.Create || viewMode === ViewModes.Edit">
          <header class="resource-detail-header">
            <p class="resource-detail-kicker">
              {{ viewMode === ViewModes.Create ? "New session" : "Edit session" }}
            </p>

            <h3>
              Session {{ viewMode === ViewModes.Create ? nextSessionId : selectedSession?.sessionNumber }}
            </h3>
          </header>

          <form
            class="resource-form"
            @submit.prevent="viewMode === ViewModes.Create ? createSession() : updateSession()"
          >
            <label>
              Date
              <input
                v-model="sessionForm.date"
                type="date"
                required
              />
            </label>

            <label>
              Title
              <input
                v-model="sessionForm.title"
                type="text"
                placeholder="Session title"
                required
              />
            </label>

            <label>
              Description
              <textarea
                v-model="sessionForm.description"
                rows="10"
                placeholder="Write the session summary here..."
              />
            </label>

            <label>
              Tags
              <input
                v-model="sessionForm.tags"
                type="text"
                placeholder="Gernanti, cult, Nalia"
              />
            </label>

            <div class="resource-form-actions">
              <button type="submit">
                {{ viewMode === ViewModes.Create ? "Save session" : "Update session" }}
              </button>

              <button
                type="button"
                class="secondary"
                @click="cancelSessionForm"
              >
                Cancel
              </button>
            </div>
          </form>
        </template>

        <template v-else-if="selectedSession">
          <header class="resource-detail-header with-actions">
            <div class="resource-detail-title">
              <p class="resource-detail-kicker">
                Session {{ selectedSession.sessionNumber }} · {{ selectedSession.date }}
              </p>

              <h3>{{ selectedSession.title }}</h3>
            </div>

            <div class="resource-detail-actions">
              <button
                type="button"
                class="secondary"
                @click="showEditSessionForm"
              >
                Edit
              </button>

              <button
                type="button"
                class="danger"
                @click="deleteSession()"
              >
                Delete
              </button>
            </div>
          </header>

          <p class="resource-description">
            {{ selectedSession.description }}
          </p>

          <div
            v-if="selectedSession.tags.length > 0"
            class="tag-list"
          >
            <span
              v-for="tag in selectedSession.tags"
              :key="tag"
              class="tag"
            >
              {{ tag }}
            </span>
          </div>
        </template>

        <template v-else>
          <p class="empty-text">
            Select a session from the list or add a new one.
          </p>
        </template>
      </article>
    </div>
  </section>
</template>
