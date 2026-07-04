<script setup lang="ts">
import { computed, reactive, ref } from "vue"
import { SessionListItemDto } from "@/assets/DataTransferObjects"
import { sessionListExample } from "@/assets/exampleData"

type SessionViewMode = "detail" | "new" | "edit"

const activeCampaignId = ref<number>(1)
const selectedSessionId = ref<number | null>(null)
const viewMode = ref<SessionViewMode>("detail")

const sessions = ref<SessionListItemDto[]>(sessionListExample)

const sessionForm = reactive({
  date: new Date().toISOString().slice(0, 10),
  title: "",
  description: "",
  tags: "",
})

const campaignSessions = computed(() => {
  return sessions.value
    .filter((session) => session.campaignId === activeCampaignId.value)
    .sort((a, b) => b.sessionId - a.sessionId)
})

const nextSessionId = computed(() => {
  const currentHighestSessionId = Math.max(
    0,
    ...sessions.value
      .filter((session) => session.campaignId === activeCampaignId.value)
      .map((session) => session.sessionId),
  )

  return currentHighestSessionId + 1
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

function selectSession(sessionId: number) {
  selectedSessionId.value = sessionId
  viewMode.value = "detail"
}

function resetSessionForm() {
  sessionForm.date = new Date().toISOString().slice(0, 10)
  sessionForm.title = ""
  sessionForm.description = ""
  sessionForm.tags = ""
}

function showAddSessionForm() {
  resetSessionForm()
  viewMode.value = "new"
}

function showEditSessionForm() {
  if (!selectedSession.value) {
    return
  }

  sessionForm.date = selectedSession.value.date
  sessionForm.title = selectedSession.value.title
  sessionForm.description = selectedSession.value.description
  sessionForm.tags = selectedSession.value.tags.join(", ")

  viewMode.value = "edit"
}

function cancelSessionForm() {
  viewMode.value = "detail"
}

function createSession() {
  const title = sessionForm.title.trim()

  if (!title) {
    return
  }

  const session: SessionListItemDto = {
    campaignId: activeCampaignId.value,
    sessionId: nextSessionId.value,
    date: sessionForm.date,
    title,
    description: sessionForm.description.trim(),
    tags: sessionForm.tags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean),
  }

  sessions.value.push(session)
  selectedSessionId.value = session.sessionId
  resetSessionForm()
  viewMode.value = "detail"
}

function updateSession() {
  if (!selectedSession.value) {
    return
  }

  const title = sessionForm.title.trim()

  if (!title) {
    return
  }

  const sessionIndex = sessions.value.findIndex(
    (session) =>
      session.campaignId === selectedSession.value?.campaignId &&
      session.sessionId === selectedSession.value?.sessionId,
  )

  if (sessionIndex === -1) {
    return
  }

  sessions.value[sessionIndex] = {
    ...sessions.value[sessionIndex],
    date: sessionForm.date,
    title,
    description: sessionForm.description.trim(),
    tags: sessionForm.tags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean),
  }

  resetSessionForm()
  viewMode.value = "detail"
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

        <ul v-if="campaignSessions.length > 0" class="resource-list">
          <li
            v-for="session in campaignSessions"
            :key="session.sessionId"
          >
            <button
              type="button"
              class="resource-list-item"
              :class="{
                selected:
                  viewMode === 'detail' &&
                  selectedSession?.sessionId === session.sessionId,
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
        <template v-if="viewMode === 'new' || viewMode === 'edit'">
          <header class="resource-detail-header">
            <p class="resource-detail-kicker">
              {{ viewMode === "new" ? "New session" : "Edit session" }}
            </p>

            <h3>
              Session {{ viewMode === "new" ? nextSessionId : selectedSession?.sessionId }}
            </h3>
          </header>

          <form
            class="resource-form"
            @submit.prevent="viewMode === 'new' ? createSession() : updateSession()"
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
                {{ viewMode === "new" ? "Save session" : "Update session" }}
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
            <div>
              <p class="resource-detail-kicker">
                Session {{ selectedSession.sessionId }} · {{ selectedSession.date }}
              </p>

              <h3>{{ selectedSession.title }}</h3>
            </div>

            <button
              type="button"
              class="secondary"
              @click="showEditSessionForm"
            >
              Edit
            </button>
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
