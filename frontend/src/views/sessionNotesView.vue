<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue"

import { DeleteAPI, PostAPI, PutAPI } from "@/apihelpers"
import ResourceTag from "@/components/ResourceTag.vue"
import { useSessionContext } from "@/composables/useSessionContext"
import { useCampaignStore } from "@/stores/campaignStore"
import type { SessionDataDto } from "@/types/DataTransferObjects"
import { ViewModes } from "@/types/viewTypes"

const { selectedCampaignId } = useCampaignStore()
const {
  sessions,
  selectedSession,
  selectionRevision,
  loadSessions,
  openSession,
  replaceWithFirstSession,
} = useSessionContext()

const viewMode = ref<ViewModes>(ViewModes.Details)
const requestError = ref("")

const sessionForm = reactive({
  date: new Date().toISOString().slice(0, 10),
  title: "",
  description: "",
  tags: "",
})

const nextSessionNumber = computed(() =>
  Math.max(0, ...sessions.value.map((session) => session.sessionNumber)) + 1,
)

function resetSessionForm() {
  sessionForm.date = new Date().toISOString().slice(0, 10)
  sessionForm.title = ""
  sessionForm.description = ""
  sessionForm.tags = ""
  requestError.value = ""
}

function showAddSessionForm() {
  resetSessionForm()
  viewMode.value = ViewModes.Create
}

function showEditSessionForm() {
  if (!selectedSession.value) return
  sessionForm.date = selectedSession.value.date
  sessionForm.title = selectedSession.value.title
  sessionForm.description = selectedSession.value.description
  sessionForm.tags = selectedSession.value.tags.map((tag) => tag.value).join(", ")
  requestError.value = ""
  viewMode.value = ViewModes.Edit
}

function cancelSessionForm() {
  resetSessionForm()
  viewMode.value = ViewModes.Details
}

function sessionPayload(sessionNumber: number): SessionDataDto {
  return {
    sessionNumber,
    date: sessionForm.date,
    title: sessionForm.title.trim(),
    description: sessionForm.description.trim(),
    tags: sessionForm.tags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean),
  }
}

async function createSession() {
  if (!selectedCampaignId.value || !sessionForm.title.trim()) return
  const response = await PostAPI(
    `campaigns/${selectedCampaignId.value}/sessions`,
    sessionPayload(nextSessionNumber.value),
  )
  if (response?.success === false) {
    requestError.value = "The session could not be created."
    return
  }

  const sessionId = Number(response.id)
  await loadSessions()
  resetSessionForm()
  viewMode.value = ViewModes.Details
  if (Number.isInteger(sessionId)) await openSession(sessionId)
}

async function updateSession() {
  if (!selectedCampaignId.value || !selectedSession.value || !sessionForm.title.trim()) return
  const sessionId = selectedSession.value.id
  const response = await PutAPI(
    `campaigns/${selectedCampaignId.value}/sessions/${sessionId}`,
    sessionPayload(selectedSession.value.sessionNumber),
  )
  if (response?.success === false) {
    requestError.value = "The session could not be updated."
    return
  }

  await loadSessions()
  resetSessionForm()
  viewMode.value = ViewModes.Details
  await openSession(sessionId)
}

async function deleteSession() {
  if (!selectedCampaignId.value || !selectedSession.value) return
  const response = await DeleteAPI(
    `campaigns/${selectedCampaignId.value}/sessions/${selectedSession.value.id}`,
  )
  if (response?.success === false) {
    requestError.value = "The session could not be deleted."
    return
  }

  await loadSessions()
  await replaceWithFirstSession()
}

watch(selectionRevision, () => {
  cancelSessionForm()
})
</script>

<template>
  <article class="resource-detail-panel">
    <template v-if="viewMode === ViewModes.Create || viewMode === ViewModes.Edit">
      <header class="resource-detail-header">
        <p class="resource-detail-kicker">
          {{ viewMode === ViewModes.Create ? "New session" : "Edit session notes" }}
        </p>
        <h3>
          Session {{ viewMode === ViewModes.Create
            ? nextSessionNumber
            : selectedSession?.sessionNumber }}
        </h3>
      </header>

      <form
        class="resource-form"
        @submit.prevent="viewMode === ViewModes.Create ? createSession() : updateSession()"
      >
        <label>
          Date
          <input v-model="sessionForm.date" type="date" required />
        </label>
        <label>
          Title
          <input v-model="sessionForm.title" type="text" placeholder="Session title" required />
        </label>
        <label>
          Notes
          <textarea
            v-model="sessionForm.description"
            rows="12"
            placeholder="Write the session summary here…"
          />
        </label>
        <label>
          Tags
          <input v-model="sessionForm.tags" type="text" placeholder="Gernanti, cult, Nalia" />
        </label>

        <p v-if="requestError" class="form-error">{{ requestError }}</p>

        <div class="resource-form-actions">
          <button type="submit">
            {{ viewMode === ViewModes.Create ? "Save session" : "Update session" }}
          </button>
          <button type="button" class="secondary" @click="cancelSessionForm">
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
          <button type="button" @click="showAddSessionForm">Add session</button>
          <button type="button" class="secondary" @click="showEditSessionForm">Edit</button>
          <button type="button" class="danger" @click="deleteSession">Delete</button>
        </div>
      </header>

      <p class="resource-description">
        {{ selectedSession.description || "No notes have been added for this session." }}
      </p>

      <div v-if="selectedSession.tags.length" class="tag-list">
        <ResourceTag
          v-for="tag in selectedSession.tags"
          :key="tag.value"
          :tag="tag"
        />
      </div>
      <p v-if="requestError" class="form-error">{{ requestError }}</p>
    </template>

    <div v-else class="character-empty-state">
      <p class="resource-detail-kicker">No sessions yet</p>
      <h3>Add the first session</h3>
      <p class="empty-text">Create a session before adding notes or rolls.</p>
      <button type="button" @click="showAddSessionForm">Add session</button>
    </div>
  </article>
</template>
