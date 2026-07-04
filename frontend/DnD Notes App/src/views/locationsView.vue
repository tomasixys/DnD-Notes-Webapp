<script setup lang="ts">
import { computed, reactive, ref } from "vue"
import { LocationDto } from "@/assets/DataTransferObjects"
import { locationsExample } from "@/assets/exampleData"

type LocationViewMode = "detail" | "new" | "edit"

const activeCampaignId = ref<number>(1)
const selectedLocationId = ref<number | null>(null)
const viewMode = ref<LocationViewMode>("detail")

const locations = ref<LocationDto[]>(locationsExample)

const locationForm = reactive({
  name: "",
  type: "",
  parentLocation: "",
  description: "",
  tags: "",
})

const campaignLocations = computed(() => {
  return locations.value
    .filter((location) => location.campaignId === activeCampaignId.value)
    .sort((a, b) => a.name.localeCompare(b.name))
})

const nextLocationId = computed(() => {
  const currentHighestLocationId = Math.max(
    0,
    ...locations.value
      .filter((location) => location.campaignId === activeCampaignId.value)
      .map((location) => location.locationId),
  )

  return currentHighestLocationId + 1
})

const selectedLocation = computed(() => {
  if (campaignLocations.value.length === 0) {
    return null
  }

  return (
    campaignLocations.value.find(
      (location) => location.locationId === selectedLocationId.value,
    ) ?? campaignLocations.value[0]
  )
})

function selectLocation(locationId: number) {
  selectedLocationId.value = locationId
  viewMode.value = "detail"
}

function resetLocationForm() {
  locationForm.name = ""
  locationForm.type = ""
  locationForm.parentLocation = ""
  locationForm.description = ""
  locationForm.tags = ""
}

function showAddLocationForm() {
  resetLocationForm()
  viewMode.value = "new"
}

function showEditLocationForm() {
  if (!selectedLocation.value) {
    return
  }

  locationForm.name = selectedLocation.value.name
  locationForm.type = selectedLocation.value.type
  locationForm.parentLocation = selectedLocation.value.parentLocation
  locationForm.description = selectedLocation.value.description
  locationForm.tags = selectedLocation.value.tags.join(", ")

  viewMode.value = "edit"
}

function cancelLocationForm() {
  viewMode.value = "detail"
}

function parseTags(tags: string) {
  return tags
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean)
}

function createLocation() {
  const name = locationForm.name.trim()

  if (!name) {
    return
  }

  const location: LocationDto = {
    campaignId: activeCampaignId.value,
    locationId: nextLocationId.value,
    name,
    type: locationForm.type.trim(),
    parentLocation: locationForm.parentLocation.trim(),
    description: locationForm.description.trim(),
    tags: parseTags(locationForm.tags),
  }

  locations.value.push(location)
  selectedLocationId.value = location.locationId
  resetLocationForm()
  viewMode.value = "detail"
}

function updateLocation() {
  if (!selectedLocation.value) {
    return
  }

  const name = locationForm.name.trim()

  if (!name) {
    return
  }

  const locationIndex = locations.value.findIndex(
    (location) =>
      location.campaignId === selectedLocation.value?.campaignId &&
      location.locationId === selectedLocation.value?.locationId,
  )

  if (locationIndex === -1) {
    return
  }

  locations.value[locationIndex] = {
    ...locations.value[locationIndex],
    name,
    type: locationForm.type.trim(),
    parentLocation: locationForm.parentLocation.trim(),
    description: locationForm.description.trim(),
    tags: parseTags(locationForm.tags),
  }

  resetLocationForm()
  viewMode.value = "detail"
}
</script>

<template>
  <section class="resource-view">
    <header class="view-header">
      <h2>Locations</h2>
      <p>Track cities, districts, buildings, rooms, wilderness sites, and other campaign places.</p>
    </header>

    <div class="resource-layout">
      <aside class="resource-list-panel">
        <div class="resource-list-header">
          <h3>Location list</h3>

          <button type="button" @click="showAddLocationForm">
            Add location
          </button>
        </div>

        <ul v-if="campaignLocations.length > 0" class="resource-list">
          <li
            v-for="location in campaignLocations"
            :key="location.locationId"
          >
            <button
              type="button"
              class="resource-list-item"
              :class="{
                selected:
                  viewMode === 'detail' &&
                  selectedLocation?.locationId === location.locationId,
              }"
              @click="selectLocation(location.locationId)"
            >
              <span class="resource-list-kicker">
                {{ location.type || "Location" }}
              </span>

              <span class="resource-list-title">
                {{ location.name }}
              </span>

              <span class="resource-list-meta">
                {{ location.parentLocation || "No parent location" }}
              </span>
            </button>
          </li>
        </ul>

        <p v-else class="empty-text">
          No locations have been registered for this campaign yet.
        </p>
      </aside>

      <article class="resource-detail-panel">
        <template v-if="viewMode === 'new' || viewMode === 'edit'">
          <header class="resource-detail-header">
            <p class="resource-detail-kicker">
              {{ viewMode === "new" ? "New location" : "Edit location" }}
            </p>

            <h3>
              {{ viewMode === "new" ? "Location " + nextLocationId : selectedLocation?.name }}
            </h3>
          </header>

          <form
            class="resource-form"
            @submit.prevent="viewMode === 'new' ? createLocation() : updateLocation()"
          >
            <label>
              Name
              <input
                v-model="locationForm.name"
                type="text"
                placeholder="Location name"
                required
              />
            </label>

            <label>
              Type
              <input
                v-model="locationForm.type"
                type="text"
                placeholder="City, district, building, room, forest, dungeon..."
              />
            </label>

            <label>
              Parent location
              <input
                v-model="locationForm.parentLocation"
                type="text"
                placeholder="Gernanti, Gernanti Mainland, Academy District..."
              />
            </label>

            <label>
              Description
              <textarea
                v-model="locationForm.description"
                rows="10"
                placeholder="Write notes about this location here..."
              />
            </label>

            <label>
              Tags
              <input
                v-model="locationForm.tags"
                type="text"
                placeholder="city, academy, safehouse, dangerous, noble"
              />
            </label>

            <div class="resource-form-actions">
              <button type="submit">
                {{ viewMode === "new" ? "Save location" : "Update location" }}
              </button>

              <button
                type="button"
                class="secondary"
                @click="cancelLocationForm"
              >
                Cancel
              </button>
            </div>
          </form>
        </template>

        <template v-else-if="selectedLocation">
          <header class="resource-detail-header with-actions">
            <div>
              <p class="resource-detail-kicker">
                {{ selectedLocation.type || "Location" }}
              </p>

              <h3>{{ selectedLocation.name }}</h3>
            </div>

            <button
              type="button"
              class="secondary"
              @click="showEditLocationForm"
            >
              Edit
            </button>
          </header>

          <dl class="resource-facts">
            <div>
              <dt>Type</dt>
              <dd>{{ selectedLocation.type || "None registered" }}</dd>
            </div>

            <div>
              <dt>Located in</dt>
              <dd>{{ selectedLocation.parentLocation || "None registered" }}</dd>
            </div>
          </dl>

          <p class="resource-description">
            {{ selectedLocation.description || "No description has been added yet." }}
          </p>

          <div
            v-if="selectedLocation.tags.length > 0"
            class="tag-list"
          >
            <span
              v-for="tag in selectedLocation.tags"
              :key="tag"
              class="tag"
            >
              {{ tag }}
            </span>
          </div>
        </template>

        <template v-else>
          <p class="empty-text">
            Select a location from the list or add a new one.
          </p>
        </template>
      </article>
    </div>
  </section>
</template>