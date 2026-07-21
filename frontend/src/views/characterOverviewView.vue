<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from "vue"
import { useRouter } from "vue-router"

import {
  DeleteAPI,
  GetAPI,
  PostAPI,
  PutAPI,
  PutFormDataAPI,
  apiUrl,
} from "@/apihelpers"
import ConfirmationPopup from "@/components/ConfirmationPopup.vue"
import ResourceTag from "@/components/ResourceTag.vue"
import { useCharacterContext } from "@/composables/useCharacterContext"
import { useCampaignStore } from "@/stores/campaignStore"
import type {
  CharacterCreateDto,
  CharacterDto,
  CharacterUpdateDto,
  PersonDataDto,
  PersonDto,
} from "@/types/DataTransferObjects"

const router = useRouter()
const { selectedCampaignId } = useCampaignStore()
const {
  character,
  loading,
  errorMessage,
  loadCharacter,
  setCharacter,
} = useCharacterContext()

const mode = ref<"details" | "create" | "edit">("details")
const people = ref<PersonDto[]>([])
const sourcePersonId = ref<number | "">("")
const portraitFile = ref<File | null>(null)
const portraitPreviewUrl = ref("")
const formError = ref("")
const showDeletePopup = ref(false)

const form = reactive({
  name: "",
  role: "",
  faction: "",
  location: "",
  description: "",
  tags: "",
  shortBio: "",
  appearance: "",
})

const availablePeople = computed(() =>
  people.value.filter((person) => !person.characterProfileAvailable),
)

const selectedSourcePerson = computed(() =>
  people.value.find((person) => person.id === sourcePersonId.value) ?? null,
)

const portraitUrl = computed(() => {
  if (portraitPreviewUrl.value) {
    return portraitPreviewUrl.value
  }
  if (mode.value === "create") {
    return ""
  }
  return character.value?.imageUrl
    ? apiUrl + character.value.imageUrl
    : ""
})

function parseTags(value: string) {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean)
}

function resetPortraitPreview() {
  if (portraitPreviewUrl.value) {
    URL.revokeObjectURL(portraitPreviewUrl.value)
  }
  portraitPreviewUrl.value = ""
  portraitFile.value = null
}

function resetForm() {
  form.name = ""
  form.role = ""
  form.faction = ""
  form.location = ""
  form.description = ""
  form.tags = ""
  form.shortBio = ""
  form.appearance = ""
  sourcePersonId.value = ""
  formError.value = ""
  resetPortraitPreview()
}

async function fetchPeople() {
  if (!selectedCampaignId.value) return
  const response = await GetAPI(`campaigns/${selectedCampaignId.value}/people`)
  if (Array.isArray(response)) {
    people.value = response as PersonDto[]
  }
}

async function showCreateForm() {
  resetForm()
  await fetchPeople()
  mode.value = "create"
}

function showEditForm() {
  if (!character.value) return
  resetForm()
  const person = character.value.person
  form.name = person.name
  form.role = person.role
  form.faction = person.faction?.label ?? ""
  form.location = person.location?.label ?? ""
  form.description = person.description
  form.tags = person.tags.map((tag) => tag.value).join(", ")
  form.shortBio = character.value.shortBio
  form.appearance = character.value.appearance
  mode.value = "edit"
}

function cancelForm() {
  resetForm()
  mode.value = "details"
}

function onPortraitSelected(event: Event) {
  resetPortraitPreview()
  const input = event.target as HTMLInputElement
  portraitFile.value = input.files?.[0] ?? null
  if (portraitFile.value) {
    portraitPreviewUrl.value = URL.createObjectURL(portraitFile.value)
  }
}

function buildPersonData(): PersonDataDto {
  return {
    name: form.name.trim(),
    role: form.role.trim(),
    faction: form.faction.trim(),
    location: form.location.trim(),
    description: form.description.trim(),
    tags: parseTags(form.tags),
  }
}

async function uploadPortrait(personId: number): Promise<CharacterDto | null> {
  if (!portraitFile.value || !selectedCampaignId.value) {
    return null
  }
  const data = new FormData()
  data.append("image", portraitFile.value)
  const response = await PutFormDataAPI(
    `campaigns/${selectedCampaignId.value}/characters/${personId}/image`,
    data,
  )
  if (response?.success === false) {
    formError.value = "The character was saved, but the portrait upload failed."
    return null
  }
  return response as CharacterDto
}

async function createCharacter() {
  if (!selectedCampaignId.value) return
  if (sourcePersonId.value === "" && !form.name.trim()) {
    formError.value = "Enter a character name or select an existing person."
    return
  }

  const payload: CharacterCreateDto = {
    ...(sourcePersonId.value === ""
      ? { person: buildPersonData() }
      : { personId: sourcePersonId.value }),
    shortBio: form.shortBio.trim(),
    appearance: form.appearance.trim(),
    makeActive: true,
  }
  const response = await PostAPI(
    `campaigns/${selectedCampaignId.value}/characters`,
    payload,
  )
  if (response?.success === false) {
    formError.value = "The character could not be created."
    return
  }

  let savedCharacter = response as CharacterDto
  const uploadedCharacter = await uploadPortrait(savedCharacter.person.id)
  if (uploadedCharacter) savedCharacter = uploadedCharacter
  setCharacter(savedCharacter)
  mode.value = "details"
  resetPortraitPreview()
  await router.replace({
    name: "CharacterOverview",
    params: { personId: "" },
  })
  await loadCharacter()
}

async function updateCharacter() {
  if (!selectedCampaignId.value || !character.value || !form.name.trim()) return
  const payload: CharacterUpdateDto = {
    person: buildPersonData(),
    shortBio: form.shortBio.trim(),
    appearance: form.appearance.trim(),
  }
  const response = await PutAPI(
    `campaigns/${selectedCampaignId.value}/characters/${character.value.person.id}`,
    payload,
  )
  if (response?.success === false) {
    formError.value = "The character could not be updated."
    return
  }

  let savedCharacter = response as CharacterDto
  const uploadedCharacter = await uploadPortrait(savedCharacter.person.id)
  if (uploadedCharacter) savedCharacter = uploadedCharacter
  setCharacter(savedCharacter)
  mode.value = "details"
  resetPortraitPreview()
}

async function activateCharacter() {
  if (!selectedCampaignId.value || !character.value) return
  const response = await PostAPI(
    `campaigns/${selectedCampaignId.value}/characters/${character.value.person.id}/activate`,
    {},
  )
  if (response?.success !== false) {
    setCharacter(response as CharacterDto)
  }
}

async function removePortrait() {
  if (!selectedCampaignId.value || !character.value) return
  const response = await DeleteAPI(
    `campaigns/${selectedCampaignId.value}/characters/${character.value.person.id}/image`,
  )
  if (response?.success !== false) {
    setCharacter(response as CharacterDto)
  }
}

async function deleteProfile() {
  showDeletePopup.value = false
  if (!selectedCampaignId.value || !character.value) return
  const response = await DeleteAPI(
    `campaigns/${selectedCampaignId.value}/characters/${character.value.person.id}`,
  )
  if (response?.success === false) return
  setCharacter(null)
  await router.replace({
    name: "CharacterOverview",
    params: { personId: "" },
  })
  await loadCharacter()
}

onBeforeUnmount(resetPortraitPreview)
</script>

<template>
  <section class="resource-view character-overview">
    <header class="view-header with-actions">
      <div class="view-header-copy">
        <h2>Character</h2>
        <p>Your current character and personal campaign record.</p>
      </div>

      <button
        v-if="mode === 'details' && character"
        type="button"
        @click="showCreateForm"
      >
        New character
      </button>
    </header>

    <article v-if="loading" class="resource-detail-panel">
      <p class="empty-text">Loading character…</p>
    </article>

    <article
      v-else-if="mode === 'create' || mode === 'edit'"
      class="resource-detail-panel character-editor"
    >
      <header class="resource-detail-header">
        <p class="resource-detail-kicker">
          {{ mode === "create" ? "New active character" : "Edit character" }}
        </p>
        <h3>{{ mode === "create" ? "Character profile" : character?.person.name }}</h3>
      </header>

      <form
        class="resource-form character-form"
        @submit.prevent="mode === 'create' ? createCharacter() : updateCharacter()"
      >
        <label v-if="mode === 'create'">
          People entry
          <select v-model="sourcePersonId">
            <option value="">Create a new People entry</option>
            <option
              v-for="person in availablePeople"
              :key="person.id"
              :value="person.id"
            >
              Use {{ person.name }}
            </option>
          </select>
        </label>

        <div v-if="mode === 'create' && selectedSourcePerson" class="selected-person-summary">
          <strong>{{ selectedSourcePerson.name }}</strong>
          <span>{{ selectedSourcePerson.role || "No role registered" }}</span>
        </div>

        <template v-if="mode === 'edit' || sourcePersonId === ''">
          <div class="character-form-grid">
            <label>
              Name
              <input v-model="form.name" type="text" required />
            </label>
            <label>
              Role
              <input v-model="form.role" type="text" placeholder="Wizard, fighter, cleric…" />
            </label>
            <label>
              Faction
              <input v-model="form.faction" type="text" />
            </label>
            <label>
              Location
              <input v-model="form.location" type="text" />
            </label>
          </div>

          <label>
            Public description
            <textarea v-model="form.description" rows="5" />
          </label>

          <label>
            Tags
            <input v-model="form.tags" type="text" placeholder="player character, wizard, academy" />
          </label>
        </template>

        <label>
          Short biography
          <textarea v-model="form.shortBio" rows="4" placeholder="A concise introduction to the character…" />
        </label>

        <label>
          Appearance
          <textarea v-model="form.appearance" rows="6" placeholder="Describe their appearance, mannerisms, and equipment…" />
        </label>

        <label>
          Portrait
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            @change="onPortraitSelected"
          />
        </label>

        <img
          v-if="portraitUrl"
          class="character-form-portrait"
          :src="portraitUrl"
          alt="Character portrait preview"
        />

        <p v-if="formError" class="form-error">{{ formError }}</p>

        <div class="resource-form-actions">
          <button type="submit">
            {{ mode === "create" ? "Create character" : "Update character" }}
          </button>
          <button type="button" class="secondary" @click="cancelForm">Cancel</button>
          <button
            v-if="mode === 'edit' && character?.imageUrl"
            type="button"
            class="secondary"
            @click="removePortrait"
          >
            Remove portrait
          </button>
        </div>
      </form>
    </article>

    <article v-else-if="character" class="resource-detail-panel character-profile-card">
      <div class="character-profile-layout">
        <div class="character-portrait-frame">
          <img
            v-if="portraitUrl"
            class="character-portrait"
            :src="portraitUrl"
            :alt="character.person.name"
          />
          <span v-else class="character-portrait-placeholder">
            {{ character.person.name.slice(0, 1).toUpperCase() }}
          </span>
        </div>

        <div class="character-profile-copy">
          <header class="resource-detail-header with-actions">
            <div class="resource-detail-title">
              <p class="resource-detail-kicker">
                {{ character.isActive ? "Active character" : "Former character" }}
              </p>
              <h3>{{ character.person.name }}</h3>
              <p class="character-role">{{ character.person.role || "Adventurer" }}</p>
            </div>

            <div class="resource-detail-actions">
              <button type="button" class="secondary" @click="showEditForm">Edit</button>
              <button
                v-if="!character.isActive"
                type="button"
                @click="activateCharacter"
              >
                Make active
              </button>
              <button type="button" class="danger" @click="showDeletePopup = true">
                Delete profile
              </button>
            </div>
          </header>

          <p class="character-bio">
            {{ character.shortBio || "No biography has been added yet." }}
          </p>

          <dl class="resource-facts character-facts">
            <div>
              <dt>Faction</dt>
              <dd>
                <ResourceTag v-if="character.person.faction" :tag="character.person.faction" />
                <template v-else>None registered</template>
              </dd>
            </div>
            <div>
              <dt>Location</dt>
              <dd>
                <ResourceTag v-if="character.person.location" :tag="character.person.location" />
                <template v-else>None registered</template>
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <section class="character-copy-section">
        <h4>Appearance</h4>
        <p class="resource-description">
          {{ character.appearance || "No appearance description has been added yet." }}
        </p>
      </section>

      <section class="character-copy-section">
        <h4>Public description</h4>
        <p class="resource-description">
          {{ character.person.description || "No public description has been added yet." }}
        </p>
      </section>

      <div v-if="character.person.tags.length" class="tag-list">
        <ResourceTag
          v-for="tag in character.person.tags"
          :key="tag.value"
          :tag="tag"
        />
      </div>
    </article>

    <article v-else class="resource-detail-panel character-empty-state">
      <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>
      <template v-else>
        <p class="resource-detail-kicker">No active character</p>
        <h3>Create your campaign character</h3>
        <p class="empty-text">
          The character profile will also appear in People and can be retained when a new character becomes active.
        </p>
        <button type="button" @click="showCreateForm">Create character</button>
      </template>
    </article>

    <ConfirmationPopup
      v-if="showDeletePopup && character"
      title="Delete character profile?"
      :message="`Delete ${character.person.name}'s private profile, notes, and backstory? The People entry will remain.`"
      confirm-text="Delete profile"
      @confirm="deleteProfile"
      @cancel="showDeletePopup = false"
    />
  </section>
</template>
