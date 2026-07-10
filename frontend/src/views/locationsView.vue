<script setup lang="ts">
import { computed, reactive, ref, onBeforeMount } from "vue"
import { GetAPI, PostAPI, PutAPI, DeleteAPI } from "@/apihelpers";
import { useCampaignStore } from "@/stores/campaignStore";
import { ViewModes } from "@/types/viewTypes"
import { LocationDto } from "@/types/DataTransferObjects"

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
  await fetchLocations()
})

const viewMode = ref<ViewModes>(ViewModes.Details)
const selectedLocationId = ref<number | null>(null)
const locations = ref<LocationDto[]>([])

const locationForm = reactive({
  name: "",
  type: "",
  parentLocation: "",
  description: "",
  tags: "",
})

const selectedLocation = computed(() => {
  if (locations.value.length === 0) return null

  return (
    locations.value.find(
      (location) => location.id === selectedLocationId.value,
    ) ?? locations.value[0]
  )
})

function selectLocation(locationId: number | null = null) {
  if (locationId === null && locations.value.length > 0) {
    selectedLocationId.value = locations.value[0].id
  } else {
    selectedLocationId.value = locationId
  }
  viewMode.value = ViewModes.Details
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
  viewMode.value = ViewModes.Create
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

  viewMode.value = ViewModes.Edit
}

function cancelLocationForm() {
  viewMode.value = ViewModes.Details
}

function parseTags(tags: string) {
  return tags
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean)
}

async function fetchLocations() {
  if (!selectedCampaignId.value) {
    console.error("No campaign selected. Cannot fetch locations.")
    return
  }
  const response = await GetAPI(`campaigns/${selectedCampaignId.value}/locations`)
  if (response.success === false || !Array.isArray(response)) {
    console.error("Failed to fetch locations:", response.error ?? "Response is not an array")
    return
  }
  locations.value = response as LocationDto[]
}

async function createLocation() {
  const name = locationForm.name.trim()
  if (!name || !selectedCampaignId.value) return

  const location: LocationDto = {
    id: 0,
    campaignId: selectedCampaignId.value,
    name: name,
    type: locationForm.type.trim(),
    parentLocation: locationForm.parentLocation.trim(),
    description: locationForm.description.trim(),
    tags: parseTags(locationForm.tags),
  }

  const response = await PostAPI(`campaigns/${selectedCampaignId.value}/locations`, location)
  if (response.success === false) {
    console.error("Failed to create location:", response.Message)
    return
  }
  const createdLocation = response as LocationDto

  locations.value = [...locations.value, createdLocation].sort((a, b) =>
    a.name.localeCompare(b.name),
  )

  resetLocationForm()
  selectLocation(createdLocation.id)
}

async function updateLocation() {
  const name = locationForm.name.trim()
  if (!name || !selectedLocation.value || !selectedCampaignId.value) return

  const location: LocationDto = {
    id: selectedLocation.value.id,
    campaignId: selectedCampaignId.value,
    name: name,
    type: locationForm.type.trim(),
    parentLocation: locationForm.parentLocation.trim(),
    description: locationForm.description.trim(),
    tags: parseTags(locationForm.tags),
  }
  const response = await PutAPI(`campaigns/${selectedCampaignId.value}/locations/${location.id}`, location)
  if (response.success === false) {
    console.error("Failed to update location:", response.Message)
    return
  }
  await fetchLocations()
  resetLocationForm()
  selectLocation(location.id)
}

async function deleteLocation() {
  if (!selectedCampaignId.value || !selectedLocationId.value) return

  const response = await DeleteAPI(`campaigns/${selectedCampaignId.value}/locations/${selectedLocationId.value}`)
  if (response.success === false) {
    console.error("Failed to delete location:", response.Message)
    return
  }
  await fetchLocations()
  selectLocation()
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

        <ul v-if="locations.length > 0" class="resource-list">
          <li
            v-for="location in locations"
            :key="location.id"
          >
            <button
              type="button"
              class="resource-list-item"
              :class="{
                selected:
                  viewMode === ViewModes.Details &&
                  selectedLocation?.id === location.id,
              }"
              @click="selectLocation(location.id)"
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
        <template v-if="viewMode === ViewModes.Create || viewMode === ViewModes.Edit">
          <header class="resource-detail-header">
            <p class="resource-detail-kicker">
              {{ viewMode === ViewModes.Create ? "New location" : "Edit location" }}
            </p>

            <h3>
              {{ viewMode === ViewModes.Create ? "New Location " : selectedLocation?.name }}
            </h3>
          </header>

          <form
            class="resource-form"
            @submit.prevent="viewMode === ViewModes.Create ? createLocation() : updateLocation()"
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
                {{ viewMode === ViewModes.Create ? "Save location" : "Update location" }}
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
            <div class="resource-detail-title">
              <p class="resource-detail-kicker">
                {{ selectedLocation.type || "Location" }}
              </p>

              <h3>{{ selectedLocation.name }}</h3>
            </div>

            <div class="resource-detail-actions">
              <button
                type="button"
                class="secondary"
                @click="showEditLocationForm"
              >
                Edit
              </button>

              <button
                type="button"
                class="danger"
                @click="deleteLocation"
              >
                Delete
              </button>
            </div>
            
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