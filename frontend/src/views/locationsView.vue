<script setup lang="ts">
import { reactive, ref, onBeforeMount } from "vue"
import { GetAPI, PostAPI, PutAPI, DeleteAPI } from "@/apihelpers";
import { useCampaignStore } from "@/stores/campaignStore";
import { ViewModes } from "@/types/viewTypes"
import type {
  DeleteResponseDto,
  LocationDataDto,
  LocationDto,
} from "@/types/DataTransferObjects"
import { useRouteEntrySelection } from "@/composables/useRouteEntrySelection"
import {
  compareByName,
  removeById,
  upsertById,
} from "@/utils/resourceCollections"
import ResourceTag from "@/components/ResourceTag.vue"


const viewMode = ref<ViewModes>(ViewModes.Details)
const locations = ref<LocationDto[]>([])

const {
  entryIdFromUrl,
  selectedEntry,
  openEntry,
  ensureDefaultEntry,
  replaceWithFirstEntry,
} = useRouteEntrySelection({
  entries: locations,
  routeName: "Locations",
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
  await fetchLocations()
  await ensureDefaultEntry()
})

const locationForm = reactive({
  name: "",
  type: "",
  parentLocation: "",
  description: "",
  tags: "",
})

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
  if (!selectedEntry.value) {
    return
  }

  locationForm.name = selectedEntry.value.name
  locationForm.type = selectedEntry.value.type
  locationForm.parentLocation = selectedEntry.value.parentLocation?.label ?? ""
  locationForm.description = selectedEntry.value.description
  locationForm.tags = selectedEntry.value.tags
    .map((tag) => tag.value)
    .join(", ")

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

  const location: LocationDataDto = {
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

  locations.value = upsertById(
    locations.value,
    createdLocation,
    compareByName,
  )

  resetLocationForm()
  await openEntry(createdLocation.id)
}

async function updateLocation() {
  const name = locationForm.name.trim()
  if (!name || !selectedEntry.value || !selectedCampaignId.value) return

  const location: LocationDataDto = {
    name: name,
    type: locationForm.type.trim(),
    parentLocation: locationForm.parentLocation.trim(),
    description: locationForm.description.trim(),
    tags: parseTags(locationForm.tags),
  }
  const locationId = selectedEntry.value.id
  const response = await PutAPI(`campaigns/${selectedCampaignId.value}/locations/${locationId}`, location)
  if (response.success === false) {
    console.error("Failed to update location:", response.Message)
    return
  }
  const updatedLocation = response as LocationDto
  locations.value = upsertById(
    locations.value,
    updatedLocation,
    compareByName,
  )
  resetLocationForm()
  await openEntry(locationId)
}

async function deleteLocation() {
  if (!selectedCampaignId.value || !selectedEntry.value) return

  const response = await DeleteAPI(`campaigns/${selectedCampaignId.value}/locations/${selectedEntry.value.id}`)
  if (response.success === false) {
    console.error("Failed to delete location:", response.Message)
    return
  }
  const deleted = response as DeleteResponseDto
  locations.value = removeById(
    locations.value,
    deleted.deletedId,
  )
  await replaceWithFirstEntry()
}

</script>

<template>
  <section class="resource-view">
    <header class="view-header with-actions">
      <div class="view-header-copy">
        <h2>Locations</h2>
        <p>Track cities, districts, buildings, rooms, wilderness sites, and other campaign places.</p>
      </div>

      <button type="button" @click="showAddLocationForm">
        Add location
      </button>
    </header>

    <div class="resource-layout">
      <aside class="resource-list-panel">
        <div class="resource-list-header">
          <h3>Location list</h3>
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
                  selectedEntry?.id === location.id,
              }"
              @click="openEntry(location.id)"
            >
              <span class="resource-list-kicker">
                {{ location.type || "Location" }}
              </span>

              <span class="resource-list-title">
                {{ location.name }}
              </span>

              <span class="resource-list-meta">
                {{ location.parentLocation?.label || "No parent location" }}
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
              {{ viewMode === ViewModes.Create ? "New Location " : selectedEntry?.name }}
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

        <template v-else-if="selectedEntry">
          <header class="resource-detail-header with-actions">
            <div class="resource-detail-title">
              <p class="resource-detail-kicker">
                {{ selectedEntry.type || "Location" }}
              </p>

              <h3>{{ selectedEntry.name }}</h3>
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
              <dt>Located in</dt>
              <dd>
                <ResourceTag
                  v-if="selectedEntry.parentLocation"
                  :tag="selectedEntry.parentLocation"
                />
                <template v-else>None registered</template>
              </dd>
            </div>

            <div>
              <dt>People</dt>
              <dd>
                <span v-if="selectedEntry.people.length > 0" class="tag-list">
                  <ResourceTag
                    v-for="person in selectedEntry.people"
                    :key="person.value"
                    :tag="person"
                  />
                </span>
                <template v-else>None registered</template>
              </dd>
            </div>
          </dl>

          <p class="resource-description">
            {{ selectedEntry.description || "No description has been added yet." }}
          </p>

          <div
            v-if="selectedEntry.tags.length > 0"
            class="tag-list"
          >
            <ResourceTag
              v-for="tag in selectedEntry.tags"
              :key="tag.value"
              :tag="tag"
            />
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
