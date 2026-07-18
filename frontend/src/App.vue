<script setup>

import { computed, ref, watch } from "vue"
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router"
import { useCampaignStore } from "@/stores/campaignStore"
import bannerImageDefault from "./assets/banner.png"

const route = useRoute()
const router = useRouter()

const {
  selectedCampaignId,
  selectedCampaign,
  hasSelectedCampaign,
  selectedCampaignImageUrl,
  selectedCampaignBannerUrl,
} = useCampaignStore()

const mainLinks = computed(() => [
  {
    label: selectedCampaign.value?.name ?? "Campaign Notes",
    to: "/dashboard",
  },
  { label: "Sessions", to: "/sessions" },
  { label: "People", to: "/people" },
  { label: "Locations", to: "/locations" },
  { label: "Factions", to: "/factions" },
  { label: "Rolls", to: "/rolls" },
])

const currentRouteGroup = computed(() => {
  return route.matched[0]
})

const submenuLinks = computed(() => {
  const children = currentRouteGroup.value?.children ?? []

  return children
    .filter((child) => child.name && child.meta?.showInSubmenu !== false)
    .map((child) => ({
      name: child.name,
      label: child.meta?.label ?? child.name,
    }))
})

const hasSubmenu = computed(() => submenuLinks.value.length > 0)

const searchPhrase = ref("")

const canSearch = computed(() => {
  return (
    selectedCampaignId.value !== null &&
    searchPhrase.value.trim().length > 0
  )
})

watch(
  () => [route.name, route.query.q],
  ([routeName, queryValue]) => {

    if (!hasSelectedCampaign.value && routeName !== "Dashboard") {
      searchPhrase.value = ""
      router.push({name: "Dashboard" })
      return
    }

    if (routeName !== "Search") {
      return
    }

    const value = Array.isArray(queryValue)
      ? queryValue[0]
      : queryValue

    searchPhrase.value =
      typeof value === "string"
        ? value
        : ""
  },
  { immediate: true },
)

async function submitSearch() {
  const query = searchPhrase.value.trim()

  if (!query || !selectedCampaignId.value) {
    return
  }

  /*
   * Preserve type filters when performing another search
   * from the search page. Searches from other views start
   * with all resource types.
   */
  const existingTypes = route.name === "Search" ? route.query.types : undefined

  await router.push({
    name: "Search",
    query: {
      q: query,
      ...(existingTypes ? { types: existingTypes } : {}),
    },
  })
}

</script>

<template>
  <div id="app-shell">
    <header id="app-header">

      <div>
        <nav id="main-nav" aria-label="Main navigation">
          <div class="main-nav-links">
            <RouterLink
              v-for="(link, index) in mainLinks"
              :key="link.to"
              :to="link.to"
              class="main-nav-link"
              :class="{ 'main-nav-link-home': index === 0 }"
            >
              {{ link.label }}
            </RouterLink>
          </div>

          <form
            class="main-search"
            role="search"
            aria-label="Search campaign"
            @submit.prevent="submitSearch"
          >
            <input
              v-model="searchPhrase"
              type="search"
              aria-label="Search phrase"
              :placeholder="
                selectedCampaignId
                  ? 'Search campaign...'
                  : 'Select a campaign first'
              "
              :disabled="!selectedCampaignId"
            />

            <button
              type="submit"
              :disabled="!canSearch"
            >
              Search
            </button>
          </form>

          <img
            id="nav-banner-graphics"
            :src="selectedCampaignBannerUrl ?? bannerImageDefault"
            alt=""
            aria-hidden="true"
          />
        </nav>
      </div>

    </header>

    <div id="main" :class="{ 'without-submenu': !hasSubmenu }">
      <aside v-if="hasSubmenu" id="submenu">
        <nav aria-label="Sub navigation">
          <ul>
            <li v-for="child in submenuLinks" :key="child.name">
              <RouterLink :to="{ name: child.name }">
                {{ child.label }}
              </RouterLink>
            </li>
          </ul>
        </nav>
      </aside>

      <main id="app-content">
        <RouterView />
      </main>
    </div>
  </div>
</template>
