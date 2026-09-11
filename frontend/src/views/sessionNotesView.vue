<script setup lang="ts">
import { useResourceEditor } from "@/composables/useResourceEditor"
import { reactive, ref, watch } from "vue"

import {
  DeleteAPI,
  isApiFailure,
  PostAPI,
  PutAPI,
} from "@/apihelpers"
import ResourceTag from "@/components/ResourceTag.vue"
import { useSessionContext } from "@/composables/useSessionContext"
import { useCampaignAuthorization } from "@/composables/useCampaignAuthorization"
import { useCampaignStore } from "@/stores/campaignStore"
import type {
  DeleteResponseDto,
  SessionDataDto,
  SessionListItemDto,
} from "@/types/DataTransferObjects"
import { ViewModes } from "@/types/viewTypes"
import { withExpectedRevision } from "@/utils/concurrency"

const {
  selectedCampaignId,
  adjustCampaignSessionCount,
} = useCampaignStore()
const {
  selectedSession,
  selectedSessionNumber,
  selectionRevision,
  upsertSession,
  removeSession,
  openSession,
  replaceWithFirstSession,
} = useSessionContext()

const viewMode = ref<ViewModes>(ViewModes.Details)
const requestError = ref("")
const { canWriteSharedResources } = useCampaignAuthorization()

const sessionForm = reactive({
  date: currentLocalDate(),
  title: "",
  description: "",
  tags: "",
})

function currentLocalDate() {
  const today = new Date()
  const year = today.getFullYear()
  const month = String(today.getMonth() + 1).padStart(2, "0")
  const day = String(today.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

function resetSessionForm() {
  sessionForm.date = currentLocalDate()
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

function sessionPayload(): SessionDataDto {
  return {
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
  const campaignId = selectedCampaignId.value
  const response = await PostAPI<SessionListItemDto>(
    `campaigns/${campaignId}/sessions`,
    sessionPayload(),
  )
  if (isApiFailure(response)) {
    requestError.value = "The session could not be created."
    return
  }

  const createdSession = response
  upsertSession(createdSession)
  adjustCampaignSessionCount(campaignId, 1)
  resetSessionForm()
  viewMode.value = ViewModes.Details
  await openSession(createdSession.id)
}

async function updateSession() {
  if (!selectedCampaignId.value || !selectedSession.value || !sessionForm.title.trim()) return
  const sessionId = selectedSession.value.id
  const response = await PutAPI<SessionListItemDto>(
    withExpectedRevision(
      `campaigns/${selectedCampaignId.value}/sessions/${sessionId}`,
      selectedSession.value.revision,
    ),
    sessionPayload(),
  )
  if (isApiFailure(response)) {
    requestError.value = "The session could not be updated."
    return
  }

  const updatedSession = response
  upsertSession(updatedSession)
  resetSessionForm()
  viewMode.value = ViewModes.Details
  await openSession(sessionId)
}

async function deleteSession() {
  if (!selectedCampaignId.value || !selectedSession.value) return
  const campaignId = selectedCampaignId.value
  const response = await DeleteAPI<DeleteResponseDto>(
    withExpectedRevision(
      `campaigns/${campaignId}/sessions/${selectedSession.value.id}`,
      selectedSession.value.revision,
    ),
  )
  if (isApiFailure(response)) {
    requestError.value = "The session could not be deleted."
    return
  }

  removeSession(response.deletedId)
  adjustCampaignSessionCount(campaignId, -1)
  await replaceWithFirstSession()
}

watch(selectionRevision, () => {
  cancelSessionForm()
})

useResourceEditor(() => selectedCampaignId.value && (viewMode.value === ViewModes.Edit || viewMode.value === ViewModes.Create) ? [{
  campaignId: selectedCampaignId.value,
  resourceType: "session",
  resourceId: viewMode.value === ViewModes.Edit ? selectedSession.value?.id ?? null : null,
  revision: selectedSession.value?.revision,
}] : [])
</script>

<template>
  <article class="resource-detail-panel">
    <template
      v-if="
        canWriteSharedResources
        && (viewMode === ViewModes.Create || viewMode === ViewModes.Edit)
      "
    >
      <header class="resource-detail-header">
        <p class="resource-detail-kicker">
          {{ viewMode === ViewModes.Create ? "New session" : "Edit session notes" }}
        </p>
        <h3>
          {{ viewMode === ViewModes.Create
            ? "New session"
            : `Session ${selectedSessionNumber}` }}
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
            Session {{ selectedSessionNumber }} · {{ selectedSession.date }}
          </p>
          <h3>{{ selectedSession.title }}</h3>
        </div>

        <div v-if="canWriteSharedResources" class="resource-detail-actions">
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
      <button
        v-if="canWriteSharedResources"
        type="button"
        @click="showAddSessionForm"
      >
        Add session
      </button>
    </div>
  </article>
</template>
