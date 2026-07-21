<script setup lang="ts">
import { computed, ref, watch, onMounted } from "vue"
import { RouterLink, useRoute, useRouter } from "vue-router"
import { PostAPI } from "@/apihelpers"
import { useCampaignStore } from "@/stores/campaignStore"
import { useSearchStore } from "@/stores/searchStore"
import type { SearchResourceType, SearchResponseDto, SearchResultDto, SearchQueryDto} from "@/types/DataTransferObjects"

const route = useRoute()
const router = useRouter()

const { selectedCampaignId } = useCampaignStore()
const { cacheSearch, getCachedSearch } = useSearchStore()

const resourceOptions: Array<{
  type: SearchResourceType
  label: string
  routeName: string
}> = [
  { type: "session",  label: "Sessions",  routeName: "SessionNotes" },
  { type: "person",   label: "People",    routeName: "People" },
  { type: "location", label: "Locations", routeName: "Locations" },
  { type: "faction",  label: "Factions",  routeName: "Factions" },
]

const allResourceTypes = resourceOptions.map( (option) => option.type )
const selectedResourceTypes = ref<SearchResourceType[]>([])
const searchResults = ref<SearchResultDto[]>([])
const searchInput = ref("")

const queryFromUrl = computed(() => {
  const query = route.query.q
  return (typeof query === "string") ? query.trim() : ""
})

const resourceTypesFromUrl = computed<SearchResourceType[]>(() => {
  const parameter = route.query.types

  if (typeof parameter !== "string" || !parameter.trim()) {
    return [...allResourceTypes]
  }

  const requestedTypes = parameter.split(",")

  return allResourceTypes.filter((type) =>
    requestedTypes.includes(type),
  )
})

async function getSearchResults(query: string, resourceTypes: SearchResourceType[])
{
  if (!query || !selectedCampaignId.value) return

  const searchQuery: SearchQueryDto = {
    query: query,
    resourceTypes: resourceTypes,
  }

  console.log("Performing search with query:", searchQuery)

  const cachedResponse = getCachedSearch(selectedCampaignId.value, searchQuery.query, searchQuery.resourceTypes)
  if (cachedResponse) {
    console.log("Using cached search results.")
    searchResults.value = cachedResponse.results
    return
  }

  const response = await PostAPI(`campaigns/${selectedCampaignId.value}/search`, searchQuery)
  if (response.success === false) {
    console.error("Search API request failed:", response.error)
    return
  }
  const responseDto = response as SearchResponseDto

  console.log("Search API response:", responseDto)

  if (responseDto.query !== searchQuery.query) {
    console.warn("Search response query does not match request query.")
  }
  if (responseDto.totalCount === 0) {
    console.warn("Search response returned no results.")
  }

  const matchedResults = responseDto.results
    .sort(
      (first, second) =>
        second.relevance - first.relevance,
    )

    console.log("Matched results after filtering and sorting:", matchedResults)

    cacheSearch(
      selectedCampaignId.value,
      searchQuery.query,
      searchQuery.resourceTypes,
      {
        query: searchQuery.query,
        searchedResourceTypes: searchQuery.resourceTypes,
        totalCount: matchedResults.length,
        results: matchedResults,
      }
    )
    searchResults.value = matchedResults

    console.log("Search results updated:", searchResults.value)
}

const groupedResults = computed(() => {
  return resourceOptions
    .map((resourceOption) => ({
      ...resourceOption,
      results: searchResults.value.filter(
        (result) => result.resourceType === resourceOption.type
      ),
    }))
    .filter((group) => group.results.length > 0)
})

const totalResultCount = computed(() => { return searchResults.value?.length ?? 0 })

function getResultRoute(result: SearchResultDto) {
  const resourceOption = resourceOptions.find((option) => option.type === result.resourceType)

  return {
    name: resourceOption?.routeName,
    params: { id: result.resourceId },
  }
}

function normalizeResourceTypes(types: SearchResourceType[]) {
  return allResourceTypes.filter((type) => types.includes(type))
}

async function submitSearch() {
  const query = searchInput.value.trim()
  const types = normalizeResourceTypes(selectedResourceTypes.value)

  if (!query || types.length === 0) {
    return
  }

  const allTypesSelected = types.length === allResourceTypes.length

  await router.push({
    name: "Search",
    query: {
      q: query,
      ...(allTypesSelected
        ? {}
        : { types: types.join(",") }),
    },
  })
}

watch(
  () => [
    route.query.q,
    route.query.types,
    selectedCampaignId.value,
  ],
  () => {
    searchInput.value = queryFromUrl.value
    selectedResourceTypes.value = [...resourceTypesFromUrl.value]

    void getSearchResults(
      queryFromUrl.value,
      resourceTypesFromUrl.value,
    )
  },
  { immediate: true },
)

</script>

<template>
  <section class="resource-view">
    <header class="view-header with-actions">
      <div class="view-header-copy">
        <h2>Search</h2>

        <p v-if="queryFromUrl">
          Results for “{{ queryFromUrl }}”
        </p>

        <p v-else>
          Search the active campaign.
        </p>
      </div>
    </header>

    <article class="resource-detail-panel search-panel">
      <template v-if="!selectedCampaignId">
        <p class="empty-text">
          Select a campaign before searching.
        </p>
      </template>

      <template v-else>
        <form
          class="search-form"
          @submit.prevent="submitSearch"
        >
          <div class="search-filter-form">
            <input
              v-model="searchInput"
              type="search"
              placeholder="Search campaign…"
              aria-label="Search campaign"
            />

            <button type="submit"
              :disabled="!searchInput.trim() || selectedResourceTypes.length === 0"
            >
              Search
            </button>
          </div>

          <div class="search-filter-form">


            <fieldset>

              <div class="search-filter-options">
                <label>Filters:  </label>
                <label
                v-for="option in resourceOptions"
                :key="option.type"
                class="search-filter-option"
                >
                <input
                v-model="selectedResourceTypes"
                type="checkbox"
                :value="option.type"
                />

                {{ option.label }}
                </label>
              </div>
            </fieldset>
          </div>
        </form>

        <p class="search-result-count">
          {{ totalResultCount }}
          {{
            totalResultCount === 1
              ? "result"
              : "results"
          }}
        </p>

        <div
          v-if="groupedResults.length > 0"
          class="search-groups"
        >
          <section
            v-for="group in groupedResults"
            :key="group.type"
            class="search-group"
          >
            <header class="search-group-header">
              <h3>{{ group.label }}</h3>
              <span>{{ group.results.length }}</span>
            </header>

            <ul class="resource-list">
              <li
                v-for="result in group.results"
                :key="`${result.resourceType}-${result.resourceId}`"
              >
                <RouterLink
                  :to="getResultRoute(result)"
                  class="resource-list-item search-result-link"
                >
                  <span class="resource-list-kicker">
                    {{ result.context }}
                  </span>

                  <span class="resource-list-title">
                    {{ result.title }}
                  </span>

                  <span class="search-result-snippet">
                    {{ result.snippet }}
                  </span>
                </RouterLink>
              </li>
            </ul>
          </section>
        </div>

        <p v-else class="empty-text">
          No matching entries were found.
        </p>
      </template>
    </article>
  </section>
</template>

<style scoped>
.search-panel {
  width: 100%;
}

.search-filter-form {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 1rem;
}

.search-filter-form fieldset {
  margin: 0;
  padding: 0;
  border: 0;
}

.search-filter-options {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  padding-top: 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--color-border);
}

.search-filter-option {
  display: flex;
  grid-template-columns: none;
  align-items: center;
  gap: 0.4rem;
}

.search-filter-option input {
  width: auto;
}

.search-result-count {
  color: var(--color-text-muted);
}

.search-groups {
  display: grid;
  gap: 1rem;
}

.search-group + .search-group {
  padding-top: 0.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.search-group-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  /* justify-content: space-between; */
  margin-bottom: 0.4rem;
}

.search-group-header h3 {
  margin: 0;
}

.search-group-header h3::after {
  content: "\00b7";
  margin-left: 0.6rem;
  color: var(--color-accent);
  font-weight: 400;
}

.search-group-header span {
  color: var(--color-text-muted);
}

.search-result-link {
  text-decoration: none;
}

.search-result-snippet {
  color: var(--color-text-muted);
  line-height: 1.2;
}

@media (max-width: 700px) {
  .search-filter-form {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
