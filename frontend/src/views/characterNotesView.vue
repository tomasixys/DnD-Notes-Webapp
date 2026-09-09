<script setup lang="ts">
import { useResourceEditor } from "@/composables/useResourceEditor"
import { computed, reactive, ref, watch } from "vue"
import { RouterLink, useRoute, useRouter } from "vue-router"

import {
  DeleteAPI,
  GetAPI,
  isApiFailure,
  PostAPI,
  PutAPI,
} from "@/apihelpers"
import ResourceTag from "@/components/ResourceTag.vue"
import { useCharacterContext } from "@/composables/useCharacterContext"
import { useCampaignAuthorization } from "@/composables/useCampaignAuthorization"
import { useAuthStore } from "@/stores/authStore"
import { useCampaignStore } from "@/stores/campaignStore"
import type {
  CampaignMembershipDto,
  CharacterNoteDataDto,
  CharacterNoteDto,
  DeleteResponseDto,
  ResourceGrantPermission,
  ResourceVisibility,
} from "@/types/DataTransferObjects"
import {
  compareByUpdatedAtDescending,
  removeById,
  upsertById,
} from "@/utils/resourceCollections"
import { withExpectedRevision } from "@/utils/concurrency"

const props = defineProps<{
  kind: "notes" | "backstory"
}>()

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { selectedCampaignId } = useCampaignStore()
const { character, loading } = useCharacterContext()

const entries = ref<CharacterNoteDto[]>([])
const members = ref<CampaignMembershipDto[]>([])
const entriesLoading = ref(false)
const mode = ref<"details" | "create" | "edit">("details")
const requestError = ref("")
let entriesRequestGeneration = 0
let membersCampaignId: number | null = null
const { canWriteCharacter } = useCampaignAuthorization(
  () => character.value?.person.id,
)

const form = reactive({
  title: "",
  content: "",
  tags: "",
  visibility: "campaign" as ResourceVisibility,
  grantPermissions: {} as Record<
    number,
    ResourceGrantPermission | "none"
  >,
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
const formAccessOwnerId = computed(
  () => (
    mode.value === "edit"
      ? selectedEntry.value?.accessOwnerUserId
      : auth.user.value?.id
  ) ?? null,
)
const grantCandidates = computed(() =>
  members.value.filter(
    (member) => member.userId !== formAccessOwnerId.value,
  ),
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
  form.visibility = "campaign"
  form.grantPermissions = {}
  requestError.value = ""
}

async function loadMembersForEditor() {
  const campaignId = selectedCampaignId.value
  if (!campaignId || membersCampaignId === campaignId) return
  members.value = []
  const response = await GetAPI<CampaignMembershipDto[]>(
    `campaigns/${campaignId}/members`,
  )
  if (selectedCampaignId.value !== campaignId) return
  if (isApiFailure(response)) return
  members.value = response
  membersCampaignId = campaignId
}

function showCreateForm() {
  resetForm()
  mode.value = "create"
  void loadMembersForEditor()
}

function showEditForm() {
  if (!selectedEntry.value) return
  form.title = selectedEntry.value.title
  form.content = selectedEntry.value.content
  form.tags = selectedEntry.value.tags.map((tag) => tag.value).join(", ")
  form.visibility = selectedEntry.value.visibility
  form.grantPermissions = Object.fromEntries(
    selectedEntry.value.grants.map((grant) => [
      grant.userId,
      grant.permission,
    ]),
  )
  mode.value = "edit"
  void loadMembersForEditor()
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
    visibility: form.visibility,
    grants: form.visibility === "restricted"
      ? Object.entries(form.grantPermissions)
        .filter(([, permission]) => permission !== "none")
        .map(([userId, permission]) => ({
          userId: Number(userId),
          permission: permission as ResourceGrantPermission,
        }))
      : [],
  }
}

function notesEndpoint() {
  return `campaigns/${selectedCampaignId.value}/characters/${character.value?.person.id}/${props.kind}`
}

async function fetchEntries() {
  const requestGeneration = ++entriesRequestGeneration
  entries.value = []
  mode.value = "details"
  requestError.value = ""
  const campaignId = selectedCampaignId.value
  const characterId = character.value?.person.id
  const kind = props.kind
  if (!campaignId || !characterId) {
    entriesLoading.value = false
    return
  }
  entriesLoading.value = true
  const response = await GetAPI<CharacterNoteDto[]>(
    `campaigns/${campaignId}/characters/${characterId}/${kind}`,
  )
  if (requestGeneration !== entriesRequestGeneration) return
  entriesLoading.value = false
  if (isApiFailure(response)) {
    requestError.value = `The ${sectionTitle.value.toLowerCase()} could not be loaded.`
    return
  }
  if (!Array.isArray(response)) {
    requestError.value = `The ${sectionTitle.value.toLowerCase()} response was invalid.`
    return
  }
  entries.value = response
  await ensureDefaultEntry()
}

async function createEntry() {
  if (!form.title.trim() || !character.value) return
  const response = await PostAPI<CharacterNoteDto>(
    notesEndpoint(),
    notePayload(),
  )
  if (isApiFailure(response)) {
    requestError.value = `The ${singularTitle.value} could not be created.`
    return
  }
  const created = response
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
  const response = await PutAPI<CharacterNoteDto>(
    withExpectedRevision(
      `${notesEndpoint()}/${selectedEntry.value.id}`,
      selectedEntry.value.revision,
    ),
    notePayload(),
  )
  if (isApiFailure(response)) {
    requestError.value = `The ${singularTitle.value} could not be updated.`
    return
  }
  const updated = response
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
  const response = await DeleteAPI<DeleteResponseDto>(
    withExpectedRevision(
      `${notesEndpoint()}/${deletedId}`,
      selectedEntry.value.revision,
    ),
  )
  if (isApiFailure(response)) {
    requestError.value = `The ${singularTitle.value} could not be deleted.`
    return
  }
  entries.value = removeById(entries.value, response.deletedId)
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
  [
    selectedCampaignId,
    () => character.value?.person.id,
    () => props.kind,
  ],
  () => void fetchEntries(),
  { immediate: true },
)

watch(noteIdFromRoute, () => {
  mode.value = "details"
})

useResourceEditor(() => selectedCampaignId.value && mode.value !== "details" ? [{
  campaignId: selectedCampaignId.value,
  resourceType: props.kind === "notes" ? "character_note" : "backstory_note",
  resourceId: mode.value === "edit" ? selectedEntry.value?.id ?? null : null,
  revision: selectedEntry.value?.revision,
}] : [])
</script>

<template>
  <section class="resource-view">
    <header class="view-header with-actions">
      <div class="view-header-copy">
        <h2>{{ sectionTitle }}</h2>
        <p>{{ sectionDescription }}</p>
      </div>
      <button
        v-if="character && canWriteCharacter"
        type="button"
        @click="showCreateForm"
      >
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

    <article v-else-if="entriesLoading" class="resource-detail-panel">
      <p class="empty-text">Loading {{ sectionTitle.toLowerCase() }}…</p>
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
              <span class="resource-list-meta">
                {{ entry.visibility }} &middot; Updated
                {{ formatUpdatedAt(entry.updatedAt) }}
              </span>
            </button>
          </li>
        </ul>
        <p v-else class="empty-text">No {{ sectionTitle.toLowerCase() }} entries yet.</p>
      </aside>

      <article class="resource-detail-panel">
        <template
          v-if="
            (mode === 'create' && canWriteCharacter)
            || (mode === 'edit' && selectedEntry?.canWrite)
          "
        >
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
            <fieldset
              class="visibility-controls"
              :disabled="mode === 'edit' && !selectedEntry?.canManageAccess"
            >
              <legend>Who can read this entry?</legend>
              <label>
                Visibility
                <select v-model="form.visibility">
                  <option value="campaign">Everyone in the campaign</option>
                  <option value="restricted">Selected campaign members</option>
                  <option value="private">Only me</option>
                </select>
              </label>
              <p class="empty-text">
                Campaign owners do not automatically see private or restricted entries.
              </p>
              <div
                v-if="form.visibility === 'restricted'"
                class="grant-list"
              >
                <label
                  v-for="member in grantCandidates"
                  :key="member.userId"
                >
                  <span>
                    {{ member.displayName || member.username }}
                    <small>@{{ member.username }}</small>
                  </span>
                  <select
                    v-model="form.grantPermissions[member.userId]"
                    :aria-label="`Access for ${member.username}`"
                  >
                    <option value="none">No access</option>
                    <option value="read">Can read</option>
                    <option value="write">Can write</option>
                  </select>
                </label>
                <p v-if="!grantCandidates.length" class="empty-text">
                  Invite another campaign member before restricting access.
                </p>
              </div>
            </fieldset>
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
                {{ selectedEntry.visibility }} &middot;
                Updated {{ formatUpdatedAt(selectedEntry.updatedAt) }}
              </p>
              <h3>{{ selectedEntry.title }}</h3>
            </div>
            <div v-if="selectedEntry.canWrite" class="resource-detail-actions">
              <button type="button" class="secondary" @click="showEditForm">Edit</button>
              <button type="button" class="danger" @click="deleteEntry">Delete</button>
            </div>
          </header>

          <p class="resource-description">
            {{ selectedEntry.content || "This entry is empty." }}
          </p>
          <p
            v-if="selectedEntry.visibility === 'restricted'"
            class="resource-access-summary"
          >
            Shared with
            {{
              selectedEntry.grants
                .map((grant) => grant.displayName || grant.username)
                .join(", ")
                || "no other campaign members"
            }}.
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

<style scoped>
.visibility-controls {
  display: grid;
  gap: 0.75rem;
  margin: 0;
  padding: 1rem;
  border: 1px solid var(--color-border);
  border-radius: 0.75rem;
}

.visibility-controls:disabled {
  opacity: 0.7;
}

.grant-list {
  display: grid;
  gap: 0.5rem;
}

.grant-list label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.grant-list small {
  display: block;
  color: var(--color-text-muted);
}

.grant-list select {
  width: auto;
}

.resource-access-summary {
  color: var(--color-text-muted);
  font-size: 0.9rem;
}
</style>
