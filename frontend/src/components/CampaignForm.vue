<script setup lang="ts">
import { reactive, computed, ref, onMounted, watch } from "vue"
import type {
  CampaignsDto,
  FactionDto,
  PersonDto,
} from "@/types/DataTransferObjects"
import { ViewModes } from "@/types/viewTypes"
import { GetAPI, PostFormDataAPI, PutFormDataAPI } from "@/apihelpers"

const props = defineProps<{
  mode: ViewModes
  campaignId?: number | null
  initialCampaign?: CampaignsDto | null
}>()

const emit = defineEmits<{
  (e: "submitted", campaign: CampaignsDto): void
  (e: "cancel"): void
}>()

const name = ref("")
const description = ref("")
const characterName = ref("")
const factionName = ref("")

const campaignFactions = ref<FactionDto[]>([])
const campaignPeople = ref<PersonDto[]>([])
const selectedFactionId = ref<number | null>(null)
const selectedPersonId = ref<number | null>(null)

const imageFile = ref<File | null>(null)
const bannerFile = ref<File | null>(null)
const isSubmitting = ref(false)

const filteredPeople = computed(() => {
  if (!selectedFactionId.value) {
    return campaignPeople.value
  }
  return campaignPeople.value.filter(
    (person) => person.faction?.referenceId === selectedFactionId.value
  )
})

async function initForm() {
  imageFile.value = null
  bannerFile.value = null

  if (props.mode === ViewModes.Create) {
    name.value = ""
    description.value = ""
    characterName.value = ""
    factionName.value = ""
    selectedFactionId.value = null
    selectedPersonId.value = null
    campaignFactions.value = []
    campaignPeople.value = []
  } else if (props.mode === ViewModes.Edit && props.campaignId) {
    name.value = props.initialCampaign?.name ?? ""
    description.value = props.initialCampaign?.description ?? ""
    characterName.value = ""
    factionName.value = ""

    const [factionsRes, peopleRes] = await Promise.all([
      GetAPI(`campaigns/${props.campaignId}/factions`),
      GetAPI(`campaigns/${props.campaignId}/people`),
    ])

    if (Array.isArray(factionsRes)) {
      campaignFactions.value = factionsRes as FactionDto[]
    } else {
      campaignFactions.value = []
    }

    if (Array.isArray(peopleRes)) {
      campaignPeople.value = peopleRes as PersonDto[]
    } else {
      campaignPeople.value = []
    }

    selectedPersonId.value = props.initialCampaign?.activeCharacter?.id ?? null
    if (selectedPersonId.value) {
      const activePerson = campaignPeople.value.find(
        (p) => p.id === selectedPersonId.value
      )
      selectedFactionId.value = activePerson?.faction?.referenceId ?? null
    } else {
      selectedFactionId.value = null
    }
  }
}

onMounted(() => {
  initForm()
})

watch(
  () => [props.mode, props.campaignId, props.initialCampaign],
  () => {
    initForm()
  }
)

function onImageSelected(event: Event) {
  const input = event.target as HTMLInputElement
  imageFile.value = input.files?.[0] ?? null
}

function onBannerSelected(event: Event) {
  const input = event.target as HTMLInputElement
  bannerFile.value = input.files?.[0] ?? null
}

function buildFormData(): FormData {
  const formData = new FormData()
  formData.append("name", name.value.trim())
  formData.append("description", description.value.trim())

  if (props.mode === ViewModes.Create) {
    if (characterName.value.trim()) {
      formData.append("character_name", characterName.value.trim())
    }
    if (factionName.value.trim()) {
      formData.append("faction_name", factionName.value.trim())
    }
  } else if (props.mode === ViewModes.Edit) {
    formData.append(
      "active_character_person_id",
      selectedPersonId.value ? String(selectedPersonId.value) : "0"
    )
  }

  if (imageFile.value) {
    formData.append("image", imageFile.value)
  }

  if (bannerFile.value) {
    formData.append("banner", bannerFile.value)
  }

  return formData
}

async function handleSubmit() {
  if (!name.value.trim() || isSubmitting.value) return
  isSubmitting.value = true

  try {
    const formData = buildFormData()
    if (props.mode === ViewModes.Create) {
      const response = await PostFormDataAPI("campaigns", formData)
      if (response.success === false) {
        console.error("Failed to create campaign:", response.error)
        return
      }
      const created = response as CampaignsDto
      emit("submitted", created)
    } else if (props.mode === ViewModes.Edit && props.campaignId) {
      const response = await PutFormDataAPI(
        `campaigns/${props.campaignId}`,
        formData
      )
      if (response.success === false) {
        console.error("Failed to update campaign:", response.error)
        return
      }
      const updated = response as CampaignsDto
      emit("submitted", updated)
    }
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <article class="dashboard-card">
    <h3>{{ mode === ViewModes.Create ? "Start new campaign" : "Edit campaign" }}</h3>

    <form class="campaign-form" @submit.prevent="handleSubmit">
      <label>
        Campaign name
        <input
          v-model="name"
          type="text"
          placeholder="Streets of Gernanti"
          required
        />
      </label>

      <template v-if="mode === ViewModes.Create">
        <label>
          Initial character name
          <input
            v-model="characterName"
            type="text"
            placeholder="Nalyathina Calemdor"
          />
        </label>

        <label>
          Initial faction name
          <input
            v-model="factionName"
            type="text"
            placeholder="Gernanti Watch"
          />
        </label>
      </template>

      <template v-else-if="mode === ViewModes.Edit">
        <label>
          Faction filter
          <select v-model="selectedFactionId">
            <option :value="null">All factions / No filter</option>
            <option
              v-for="faction in campaignFactions"
              :key="faction.id"
              :value="faction.id"
            >
              {{ faction.name }}
            </option>
          </select>
        </label>

        <label>
          Active Character / Person
          <select v-model="selectedPersonId">
            <option :value="null">No active character</option>
            <option
              v-for="person in filteredPeople"
              :key="person.id"
              :value="person.id"
            >
              {{ person.name }} {{ person.characterProfileAvailable ? '' : '(No character sheet yet)' }}
            </option>
          </select>
        </label>
      </template>

      <label>
        Campaign description
        <textarea
          v-model="description"
          rows="4"
          placeholder="A short description of the campaign..."
        />
      </label>

      <label>
        Campaign image URL
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          @change="onImageSelected"
        />
      </label>
      <label>
        Campaign banner URL
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          @change="onBannerSelected"
        />
      </label>

      <div class="dashboard-actions">
        <button type="submit" :disabled="isSubmitting">
          {{ mode === ViewModes.Create ? "Create campaign" : "Update campaign" }}
        </button>

        <button
          type="button"
          class="secondary"
          @click="emit('cancel')"
        >
          Cancel
        </button>
      </div>
    </form>
  </article>
</template>

<style scoped>
.dashboard-card {
  padding: 1.5rem;
  border: 1px solid var(--color-border);
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.035);
}

.dashboard-card h3 {
  margin-top: 0;
  font-size: 1.5rem;
}

.campaign-form {
  display: grid;
  gap: 1rem;
}

.dashboard-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-top: 1.5rem;
}
</style>
