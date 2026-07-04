<script setup lang="ts">
import { computed, reactive, ref } from "vue"
import { PersonDto } from "@/assets/DataTransferObjects"
import { peopleExample } from "@/assets/exampleData"

type PeopleViewMode = "detail" | "new" | "edit"

const activeCampaignId = ref<number>(1)
const selectedPersonId = ref<number | null>(null)
const viewMode = ref<PeopleViewMode>("detail")

const people = ref<PersonDto[]>(peopleExample)

const personForm = reactive({
  name: "",
  role: "",
  faction: "",
  location: "",
  description: "",
  tags: "",
})

const campaignPeople = computed(() => {
  return people.value
    .filter((person) => person.campaignId === activeCampaignId.value)
    .sort((a, b) => a.name.localeCompare(b.name))
})

const nextPersonId = computed(() => {
  const currentHighestPersonId = Math.max(
    0,
    ...people.value
      .filter((person) => person.campaignId === activeCampaignId.value)
      .map((person) => person.personId),
  )

  return currentHighestPersonId + 1
})

const selectedPerson = computed(() => {
  if (campaignPeople.value.length === 0) {
    return null
  }

  return (
    campaignPeople.value.find(
      (person) => person.personId === selectedPersonId.value,
    ) ?? campaignPeople.value[0]
  )
})

function selectPerson(personId: number) {
  selectedPersonId.value = personId
  viewMode.value = "detail"
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
  viewMode.value = "new"
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

  viewMode.value = "edit"
}

function cancelPersonForm() {
  viewMode.value = "detail"
}

function parseTags(tags: string) {
  return tags
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean)
}

function createPerson() {
  const name = personForm.name.trim()

  if (!name) {
    return
  }

  const person: PersonDto = {
    campaignId: activeCampaignId.value,
    personId: nextPersonId.value,
    name,
    role: personForm.role.trim(),
    faction: personForm.faction.trim(),
    location: personForm.location.trim(),
    description: personForm.description.trim(),
    tags: parseTags(personForm.tags),
  }

  people.value.push(person)
  selectedPersonId.value = person.personId
  resetPersonForm()
  viewMode.value = "detail"
}

function updatePerson() {
  if (!selectedPerson.value) {
    return
  }

  const name = personForm.name.trim()

  if (!name) {
    return
  }

  const personIndex = people.value.findIndex(
    (person) =>
      person.campaignId === selectedPerson.value?.campaignId &&
      person.personId === selectedPerson.value?.personId,
  )

  if (personIndex === -1) {
    return
  }

  people.value[personIndex] = {
    ...people.value[personIndex],
    name,
    role: personForm.role.trim(),
    faction: personForm.faction.trim(),
    location: personForm.location.trim(),
    description: personForm.description.trim(),
    tags: parseTags(personForm.tags),
  }

  resetPersonForm()
  viewMode.value = "detail"
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

        <ul v-if="campaignPeople.length > 0" class="resource-list">
          <li
            v-for="person in campaignPeople"
            :key="person.personId"
          >
            <button
              type="button"
              class="resource-list-item"
              :class="{
                selected:
                  viewMode === 'detail' &&
                  selectedPerson?.personId === person.personId,
              }"
              @click="selectPerson(person.personId)"
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
        <template v-if="viewMode === 'new' || viewMode === 'edit'">
          <header class="resource-detail-header">
            <p class="resource-detail-kicker">
              {{ viewMode === "new" ? "New person" : "Edit person" }}
            </p>

            <h3>
              {{ viewMode === "new" ? "Person " + nextPersonId : selectedPerson?.name }}
            </h3>
          </header>

          <form
            class="resource-form"
            @submit.prevent="viewMode === 'new' ? createPerson() : updatePerson()"
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
                {{ viewMode === "new" ? "Save person" : "Update person" }}
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
            <div>
              <p class="resource-detail-kicker">
                {{ selectedPerson.role || "Person of interest" }}
              </p>

              <h3>{{ selectedPerson.name }}</h3>
            </div>

            <button
              type="button"
              class="secondary"
              @click="showEditPersonForm"
            >
              Edit
            </button>
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