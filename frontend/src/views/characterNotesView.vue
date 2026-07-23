<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue"
import { RouterLink, useRoute, useRouter } from "vue-router"

import { DeleteAPI, GetAPI, PostAPI, PutAPI } from "@/apihelpers"
import ResourceTag from "@/components/ResourceTag.vue"
import { useCharacterContext } from "@/composables/useCharacterContext"
import { useCampaignStore } from "@/stores/campaignStore"
import type {
  CharacterNoteDataDto,
  CharacterNoteDto,
  DeleteResponseDto,
} from "@/types/DataTransferObjects"
import {
  compareByUpdatedAtDescending,
  removeById,
  upsertById,
} from "@/utils/resourceCollections"

const props = defineProps<{
  kind: "notes" | "backstory"
}>()

const route = useRoute()
const router = useRouter()
const { selectedCampaignId } = useCampaignStore()
const { character, loading } = useCharacterContext()

const entries = ref<CharacterNoteDto[]>([])
const mode = ref<"details" | "create" | "edit">("details")
const requestError = ref("")

const form = reactive({
  title: "",
  content: "",
  tags: "",
})

const routeName = computed(() =>
  props.kind === "notes" ? "CharacterNotes" : "CharacterBackstory",
)
const sectionTitle = computed(() =>
  props.kind === "notes" ? "Notes" : "Backstory",
)
const singularTitle = computed(() =>
  props.kind === "notes" ? "note" : "backstory entry",
)
const sectionDescription = computed(() =>
  props.kind === "notes"
    ? "Keep personal lists, plans, reminders, and anything else your character needs."
    : "Build the character's history through freely named entries such as family, work, and motivation.",
)

const noteIdFromRoute = computed(() => {
  const rawValue = Array.isArray(route.params.noteId)
    ? route.params.noteId[0]
    : route.params.noteId
  const noteId = Number(rawValue)
  return Number.isInteger(noteId) && noteId > 0 ? noteId : null
})

const selectedEntry = computed(() =>
  entries.value.find((entry) => entry.id === noteIdFromRoute.value) ?? null,
)

function routeParams(noteId: number | "" = "") {
  return {
    ...(route.params.personId
      ? { personId: route.params.personId }
      : {}),
    ...(noteId === "" ? {} : { noteId }),
  }
}

async function openEntry(noteId: number, replace = false) {
  const destination = {
    name: routeName.value,
    params: routeParams(noteId),
  }
  if (replace) await router.replace(destination)
  else await router.push(destination)
}

async function ensureDefaultEntry() {
  if (noteIdFromRoute.value !== null || entries.value.length === 0) return
  await openEntry(entries.value[0].id, true)
}

function resetForm() {
  form.title = ""
  form.content = ""
  form.tags = ""
  requestError.value = ""
}

function showCreateForm() {
  resetForm()
  mode.value = "create"
}

function showEditForm() {
  if (!selectedEntry.value) return
  form.title = selectedEntry.value.title
  form.content = selectedEntry.value.content
  form.tags = selectedEntry.value.tags.map((tag) => tag.value).join(", ")
  mode.value = "edit"
}

function cancelForm() {
  resetForm()
  mode.value = "details"
}

function parseTags(value: string) {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean)
}

function notePayload(): CharacterNoteDataDto {
  return {
    title: form.title.trim(),
    content: form.content.trim(),
    tags: parseTags(form.tags),
  }
}

function notesEndpoint() {
  return `campaigns/${selectedCampaignId.value}/characters/${character.value?.person.id}/${props.kind}`
}

async function fetchEntries() {
  entries.value = []
  mode.value = "details"
  requestError.value = ""
  if (!selectedCampaignId.value || !character.value) return
  const response = await GetAPI(notesEndpoint())
  if (!Array.isArray(response)) {
    requestError.value = `The ${sectionTitle.value.toLowerCase()} could not be loaded.`
    return
  }
  entries.value = response as CharacterNoteDto[]
  await ensureDefaultEntry()
}

async function createEntry() {
  if (!form.title.trim() || !character.value) return
  const response = await PostAPI(notesEndpoint(), notePayload())
  if (response?.success === false) {
    requestError.value = `The ${singularTitle.value} could not be created.`
    return
  }
  const created = response as CharacterNoteDto
  entries.value = upsertById(
    entries.value,
    created,
    compareByUpdatedAtDescending,
  )
  mode.value = "details"
  resetForm()
  await openEntry(created.id)
}

async function updateEntry() {
  if (!form.title.trim() || !selectedEntry.value) return
  const response = await PutAPI(
    `${notesEndpoint()}/${selectedEntry.value.id}`,
    notePayload(),
  )
  if (response?.success === false) {
    requestError.value = `The ${singularTitle.value} could not be updated.`
    return
  }
  const updated = response as CharacterNoteDto
  entries.value = upsertById(
    entries.value,
    updated,
    compareByUpdatedAtDescending,
  )
  mode.value = "details"
  resetForm()
}

async function deleteEntry() {
  if (!selectedEntry.value) return
  const deletedId = selectedEntry.value.id
  const response = await DeleteAPI(`${notesEndpoint()}/${deletedId}`)
  if (response?.success === false) {
    requestError.value = `The ${singularTitle.value} could not be deleted.`
    return
  }
  const deleted = response as DeleteResponseDto
  entries.value = removeById(entries.value, deleted.deletedId)
  const firstEntry = entries.value[0]
  await router.replace({
    name: routeName.value,
    params: routeParams(firstEntry?.id ?? ""),
  })
}

function formatUpdatedAt(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
  }).format(date)
}

watch(
  () => [character.value?.person.id, props.kind],
  () => void fetchEntries(),
  { immediate: true },
)

watch(noteIdFromRoute, () => {
  mode.value = "details"
})
</script>

<template>
  <section class="resource-view">
    <header class="view-header with-actions">
      <div class="view-header-copy">
        <h2>{{ sectionTitle }}</h2>
        <p>{{ sectionDescription }}</p>
      </div>
      <button v-if="character" type="button" @click="showCreateForm">
        Add {{ singularTitle }}
      </button>
    </header>

    <article v-if="loading" class="resource-detail-panel">
      <p class="empty-text">Loading character…</p>
    </article>

    <article v-else-if="!character" class="resource-detail-panel character-empty-state">
      <p class="empty-text">Create or open a character before adding {{ sectionTitle.toLowerCase() }}.</p>
      <RouterLink
        class="button-link"
        :to="{
          name: 'CharacterOverview',
          params: route.params.personId ? { personId: route.params.personId } : {},
        }"
      >
        Open overview
      </RouterLink>
    </article>

    <div v-else class="resource-layout">
      <aside class="resource-list-panel">
        <div class="resource-list-header">
          <h3>{{ sectionTitle }} list</h3>
          <span>{{ entries.length }}</span>
        </div>

        <ul v-if="entries.length" class="resource-list">
          <li v-for="entry in entries" :key="entry.id">
            <button
              type="button"
              class="resource-list-item"
              :class="{ selected: selectedEntry?.id === entry.id && mode === 'details' }"
              @click="openEntry(entry.id)"
            >
              <span class="resource-list-kicker">{{ singularTitle }}</span>
              <span class="resource-list-title">{{ entry.title }}</span>
              <span class="resource-list-meta">Updated {{ formatUpdatedAt(entry.updatedAt) }}</span>
            </button>
          </li>
        </ul>
        <p v-else class="empty-text">No {{ sectionTitle.toLowerCase() }} entries yet.</p>
      </aside>

      <article class="resource-detail-panel">
        <template v-if="mode === 'create' || mode === 'edit'">
          <header class="resource-detail-header">
            <p class="resource-detail-kicker">
              {{ mode === "create" ? `New ${singularTitle}` : `Edit ${singularTitle}` }}
            </p>
            <h3>{{ mode === "create" ? `Add ${singularTitle}` : selectedEntry?.title }}</h3>
          </header>

          <form
            class="resource-form"
            @submit.prevent="mode === 'create' ? createEntry() : updateEntry()"
          >
            <label>
              Name
              <input v-model="form.title" type="text" required placeholder="Shopping list, family, motivation…" />
            </label>
            <label>
              Notes
              <textarea v-model="form.content" rows="14" placeholder="Write here…" />
            </label>
            <label>
              Tags
              <input v-model="form.tags" type="text" placeholder="urgent, person:Nalia, location:Gernanti" />
            </label>
            <p v-if="requestError" class="form-error">{{ requestError }}</p>
            <div class="resource-form-actions">
              <button type="submit">{{ mode === "create" ? "Save" : "Update" }}</button>
              <button type="button" class="secondary" @click="cancelForm">Cancel</button>
            </div>
          </form>
        </template>

        <template v-else-if="selectedEntry">
          <header class="resource-detail-header with-actions">
            <div class="resource-detail-title">
              <p class="resource-detail-kicker">
                Updated {{ formatUpdatedAt(selectedEntry.updatedAt) }}
              </p>
              <h3>{{ selectedEntry.title }}</h3>
            </div>
            <div class="resource-detail-actions">
              <button type="button" class="secondary" @click="showEditForm">Edit</button>
              <button type="button" class="danger" @click="deleteEntry">Delete</button>
            </div>
          </header>

          <p class="resource-description">
            {{ selectedEntry.content || "This entry is empty." }}
          </p>
          <div v-if="selectedEntry.tags.length" class="tag-list">
            <ResourceTag
              v-for="tag in selectedEntry.tags"
              :key="tag.value"
              :tag="tag"
            />
          </div>
        </template>

        <p v-else-if="requestError" class="form-error">{{ requestError }}</p>
        <p v-else class="empty-text">
          Select an entry or add a new {{ singularTitle }}.
        </p>
      </article>
    </div>
  </section>
</template>
