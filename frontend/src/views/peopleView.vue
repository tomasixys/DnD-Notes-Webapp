<script setup lang="ts">
import { computed, reactive, ref, onBeforeMount } from "vue"
import { GetAPI, PostAPI, PutAPI, DeleteAPI } from "@/apihelpers";
import { useCampaignStore } from "@/stores/campaignStore";
import { ViewModes } from "@/types/viewTypes"
import { PersonDto } from "@/types/DataTransferObjects"

const {
  campaigns,
  selectedCampaignId,
  selectedCampaign,
  hasSelectedCampaign,
  setCampaigns,
  selectCampaign,
  clearSelectedCampaign,
} = useCampaignStore()

onBeforeMount(async () => {
  await fetchPeople()
  selectPerson()
})
const viewMode = ref<ViewModes>(ViewModes.Details)

const selectedPersonId = ref<number | null>(null)

const people = ref<PersonDto[]>([])

const personForm = reactive({
  name: "",
  role: "",
  faction: "",
  location: "",
  description: "",
  tags: "",
})

const selectedPerson = computed(() => {
  if (people.value.length === 0) return null

  return ( people.value.find(
      (person) => person.id === selectedPersonId.value,
    ) ?? people.value[0]
  )
})

function selectPerson(personId: number | null = null) {
  if (personId === null && people.value.length > 0) {
    selectedPersonId.value  = people.value[0].id
  } else {
    selectedPersonId.value = personId
  }
  viewMode.value = ViewModes.Details
}

function resetPersonForm() {
  personForm.name = ""
  personForm.role = ""
  personForm.faction = ""
  personForm.location = ""
  personForm.description = ""
  personForm.tags = ""
}

function showAddPersonForm() {
  resetPersonForm()
  viewMode.value = ViewModes.Create
}

function showEditPersonForm() {
  if (!selectedPerson.value) {
    return
  }

  personForm.name = selectedPerson.value.name
  personForm.role = selectedPerson.value.role
  personForm.faction = selectedPerson.value.faction
  personForm.location = selectedPerson.value.location
  personForm.description = selectedPerson.value.description
  personForm.tags = selectedPerson.value.tags.join(", ")

  viewMode.value = ViewModes.Edit
}

function cancelPersonForm() {
  viewMode.value = ViewModes.Details
}

function parseTags(tags: string) {
  return tags
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean)
}

async function fetchPeople() {
  if (!selectedCampaignId.value) {
    console.error("No campaign selected. Cannot fetch people.")
    return
  }

  const response = await GetAPI(`campaigns/${selectedCampaignId.value}/people`)
  if (response.success === false) {
    console.error("Failed to fetch people:", response.error)
    return
  }

  if (!Array.isArray(response)) {
    console.error("Failed to fetch people: Response is not an array")
    return
  }
  people.value = response as PersonDto[]
}

async function createPerson() {
  const name = personForm.name.trim()
  if (!name || !selectedCampaignId.value) return


  const person: PersonDto = {
    id: 0,
    campaignId: selectedCampaignId.value,
    name: name,
    role: personForm.role.trim(),
    faction: personForm.faction.trim(),
    location: personForm.location.trim(),
    description: personForm.description.trim(),
    tags: parseTags(personForm.tags),
  }

  const response = await PostAPI(`campaigns/${selectedCampaignId.value}/people`, person)
  if (response.success === false) {
    console.error("Failed to create person:", response.error)
    return
  }
  const createdPerson = response as PersonDto
  people.value = [ ...people.value, createdPerson].sort((a, b) => 
    a.name.localeCompare(b.name),
  )

  resetPersonForm()
  selectPerson(createdPerson.id)
}

async function updatePerson() {
  if (!selectedPerson.value || !selectedCampaignId.value) return

  const name = personForm.name.trim()
  if (!name) return

  const person: PersonDto = {
    id: selectedPerson.value.id,
    campaignId: selectedCampaignId.value,
    name: name,
    role: personForm.role.trim(),
    faction: personForm.faction.trim(),
    location: personForm.location.trim(),
    description: personForm.description.trim(),
    tags: parseTags(personForm.tags),
  }

  const response = await PutAPI(`campaigns/${selectedCampaignId.value}/people/${selectedPerson.value.id}`, person)
  if (response.success === false) {
    console.error("Failed to update person:", response.error)
    return
  }
  resetPersonForm()
  selectPerson(person.id)
}

async function deletePerson() {
  if (!selectedPerson.value || !selectedCampaignId.value) return

  const response = await DeleteAPI(`campaigns/${selectedCampaignId.value}/people/${selectedPerson.value.id}`)
  if (response.success === false) {
    console.error("Failed to delete person:", response.error)
    return
  }
  await fetchPeople()
  selectPerson()
}

</script>

<template>
  <section class="resource-view">
    <header class="view-header">
      <h2>People</h2>
      <p>Track player characters, NPCs, contacts, enemies, and other people of interest.</p>
    </header>

    <div class="resource-layout">
      <aside class="resource-list-panel">
        <div class="resource-list-header">
          <h3>People list</h3>

          <button type="button" @click="showAddPersonForm">
            Add person
          </button>
        </div>

        <ul v-if="people.length > 0" class="resource-list">
          <li
            v-for="person in people"
            :key="person.name"
          >
            <button
              type="button"
              class="resource-list-item"
              :class="{
                selected:
                  viewMode === ViewModes.Details &&
                  selectedPerson?.id === person.id,
              }"
              @click="selectPerson(person.id)"
            >
              <span class="resource-list-kicker">
                {{ person.role || "No role" }}
              </span>

              <span class="resource-list-title">
                {{ person.name }}
              </span>

              <span class="resource-list-meta">
                {{ person.faction || "No faction" }}
                <template v-if="person.location">
                  · {{ person.location }}
                </template>
              </span>
            </button>
          </li>
        </ul>

        <p v-else class="empty-text">
          No people have been registered for this campaign yet.
        </p>
      </aside>

      <article class="resource-detail-panel">
        <template v-if="viewMode === ViewModes.Create || viewMode === ViewModes.Edit">
          <header class="resource-detail-header">
            <p class="resource-detail-kicker">
              {{ viewMode === ViewModes.Create ? "New person" : "Edit person" }}
            </p>

            <h3>
              {{ viewMode === ViewModes.Create ? "New Person" : selectedPerson?.name }}
            </h3>
          </header>

          <form
            class="resource-form"
            @submit.prevent="viewMode === ViewModes.Create ? createPerson() : updatePerson()"
          >
            <label>
              Name
              <input
                v-model="personForm.name"
                type="text"
                placeholder="Person name"
                required
              />
            </label>

            <label>
              Role
              <input
                v-model="personForm.role"
                type="text"
                placeholder="Professor, lookout, priest, enemy, contact..."
              />
            </label>

            <label>
              Faction
              <input
                v-model="personForm.faction"
                type="text"
                placeholder="Dragon Order, Beggars, Talmira's Church..."
              />
            </label>

            <label>
              Location
              <input
                v-model="personForm.location"
                type="text"
                placeholder="Gernanti magic academy, docks, mainland..."
              />
            </label>

            <label>
              Description
              <textarea
                v-model="personForm.description"
                rows="10"
                placeholder="Write notes about this person here..."
              />
            </label>

            <label>
              Tags
              <input
                v-model="personForm.tags"
                type="text"
                placeholder="ally, enemy, academy, recurring"
              />
            </label>

            <div class="resource-form-actions">
              <button type="submit">
                {{ viewMode === ViewModes.Create ? "Save person" : "Update person" }}
              </button>

              <button
                type="button"
                class="secondary"
                @click="cancelPersonForm"
              >
                Cancel
              </button>
            </div>
          </form>
        </template>

        <template v-else-if="selectedPerson">
          
          <header class="resource-detail-header with-actions">
            <div class="resource-detail-title">
              <p class="resource-detail-kicker">
                {{ selectedPerson.role || "Person of interest" }}
              </p>

              <h3>{{ selectedPerson.name }}</h3>
            </div>
            
            <div class="resource-detail-actions">
              <button
                type="button"
                class="secondary"
                @click="showEditPersonForm"
              >
                Edit
              </button>

              <button
                type="button"
                class="danger"
                @click="deletePerson()"
              >
                Delete
              </button>
            </div>
          </header>

          <dl class="resource-facts">
            <div>
              <dt>Faction</dt>
              <dd>{{ selectedPerson.faction || "None registered" }}</dd>
            </div>

            <div>
              <dt>Location</dt>
              <dd>{{ selectedPerson.location || "None registered" }}</dd>
            </div>
          </dl>

          <p class="resource-description">
            {{ selectedPerson.description || "No description has been added yet." }}
          </p>

          <div
            v-if="selectedPerson.tags.length > 0"
            class="tag-list"
          >
            <span
              v-for="tag in selectedPerson.tags"
              :key="tag"
              class="tag"
            >
              {{ tag }}
            </span>
          </div>
        </template>

        <template v-else>
          <p class="empty-text">
            Select a person from the list or add a new one.
          </p>
        </template>
      </article>
    </div>
  </section>
</template>