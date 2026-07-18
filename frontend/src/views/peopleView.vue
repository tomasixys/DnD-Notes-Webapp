<script setup lang="ts">
import { reactive, ref, onBeforeMount } from "vue"
import { GetAPI, PostAPI, PutAPI, DeleteAPI } from "@/apihelpers";
import { useCampaignStore } from "@/stores/campaignStore";
import { ViewModes } from "@/types/viewTypes"
import { PersonDto } from "@/types/DataTransferObjects"
import { useRouteEntrySelection } from "@/composables/useRouteEntrySelection"

const viewMode = ref<ViewModes>(ViewModes.Details)
const people = ref<PersonDto[]>([])

const {
  entryIdFromUrl,
  selectedEntry,
  openEntry,
  ensureDefaultEntry,
  replaceWithFirstEntry,
} = useRouteEntrySelection({
  entries: people,
  routeName: "People",
  onRouteEntryChange: () => {
    viewMode.value = ViewModes.Details
  },
})

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
  await ensureDefaultEntry()
})


const personForm = reactive({
  name: "",
  role: "",
  faction: "",
  location: "",
  description: "",
  tags: "",
})

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
  if (!selectedEntry.value) {
    return
  }

  personForm.name = selectedEntry.value.name
  personForm.role = selectedEntry.value.role
  personForm.faction = selectedEntry.value.faction
  personForm.location = selectedEntry.value.location
  personForm.description = selectedEntry.value.description
  personForm.tags = selectedEntry.value.tags.join(", ")

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
  await fetchPeople()
  resetPersonForm()
  await openEntry(createdPerson.id)
}

async function updatePerson() {
  if (!selectedEntry.value || !selectedCampaignId.value) return

  const name = personForm.name.trim()
  if (!name) return

  const person: PersonDto = {
    id: selectedEntry.value.id,
    campaignId: selectedCampaignId.value,
    name: name,
    role: personForm.role.trim(),
    faction: personForm.faction.trim(),
    location: personForm.location.trim(),
    description: personForm.description.trim(),
    tags: parseTags(personForm.tags),
  }

  const response = await PutAPI(`campaigns/${selectedCampaignId.value}/people/${selectedEntry.value.id}`, person)
  if (response.success === false) {
    console.error("Failed to update person:", response.error)
    return
  }
  resetPersonForm()
  await openEntry(person.id)
}

async function deletePerson() {
  if (!selectedEntry.value || !selectedCampaignId.value) return

  const response = await DeleteAPI(`campaigns/${selectedCampaignId.value}/people/${selectedEntry.value.id}`)
  if (response.success === false) {
    console.error("Failed to delete person:", response.error)
    return
  }
  await fetchPeople()
  await replaceWithFirstEntry()
}

</script>

<template>
  <section class="resource-view">
    <header class="view-header with-actions">
      <div class="view-header-copy">
        <h2>People</h2>
        <p>Track player characters, NPCs, contacts, enemies, and other people of interest.</p>
      </div>

      <button type="button" @click="showAddPersonForm">
        Add person
      </button>
    </header>

    <div class="resource-layout">
      <aside class="resource-list-panel">
        <div class="resource-list-header">
          <h3>People list</h3>
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
                  selectedEntry?.id === person.id,
              }"
              @click="openEntry(person.id)"
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
              {{ viewMode === ViewModes.Create ? "New Person" : selectedEntry?.name }}
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

        <template v-else-if="selectedEntry">
          
          <header class="resource-detail-header with-actions">
            <div class="resource-detail-title">
              <p class="resource-detail-kicker">
                {{ selectedEntry.role || "Person of interest" }}
              </p>

              <h3>{{ selectedEntry.name }}</h3>
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
              <dd>{{ selectedEntry.faction || "None registered" }}</dd>
            </div>

            <div>
              <dt>Location</dt>
              <dd>{{ selectedEntry.location || "None registered" }}</dd>
            </div>
          </dl>

          <p class="resource-description">
            {{ selectedEntry.description || "No description has been added yet." }}
          </p>

          <div
            v-if="selectedEntry.tags.length > 0"
            class="tag-list"
          >
            <span
              v-for="tag in selectedEntry.tags"
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
