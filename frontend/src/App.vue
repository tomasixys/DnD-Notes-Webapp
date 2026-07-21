<script setup>

import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router"
import { useCampaignStore } from "@/stores/campaignStore"
import bannerImageDefault from "./assets/banner.png"

const route = useRoute()
const router = useRouter()

const {
  selectedCampaignId,
  selectedCampaign,
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
  { label: "Character", to: "/character/overview" },
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
      to: {
        name: child.name,
        params: {
          ...(route.params.personId
            ? { personId: route.params.personId }
            : {}),
          ...(route.params.id
            ? { id: route.params.id }
            : {}),
        },
      },
    }))
})

const hasSubmenu = computed(() => submenuLinks.value.length > 0)

const activeMainLinkIndex = computed(() => {
  const routeRoot = `/${route.path.split("/").filter(Boolean)[0] ?? ""}`
  return mainLinks.value.findIndex((link) =>
    link.to === routeRoot || link.to.startsWith(`${routeRoot}/`),
  )
})

const mainNavLinksElement = ref(null)
const submenuElement = ref(null)
const submenuNavElement = ref(null)
const submenuOffset = ref(0)

function updateSubmenuPosition() {
  const mainLink = mainNavLinksElement.value?.querySelector(
    `[data-main-nav-index="${activeMainLinkIndex.value}"]`,
  )
  const submenu = submenuElement.value
  const submenuNav = submenuNavElement.value

  if (!mainLink || !submenu || !submenuNav) {
    submenuOffset.value = 0
    return
  }

  const linkBounds = mainLink.getBoundingClientRect()
  const submenuBounds = submenu.getBoundingClientRect()
  const navWidth = submenuNav.getBoundingClientRect().width
  const submenuStyles = window.getComputedStyle(submenu)
  const paddingLeft = Number.parseFloat(submenuStyles.paddingLeft) || 0
  const paddingRight = Number.parseFloat(submenuStyles.paddingRight) || 0
  const desiredOffset =
    linkBounds.left + linkBounds.width / 2
    - submenuBounds.left
    - paddingLeft
    - navWidth / 2
  const maximumOffset = Math.max(
    0,
    submenuBounds.width - paddingLeft - paddingRight - navWidth,
  )

  submenuOffset.value = Math.round(
    Math.min(Math.max(0, desiredOffset), maximumOffset),
  )
}

function scheduleSubmenuPositionUpdate() {
  void nextTick(updateSubmenuPosition)
}

watch(
  () => [route.path, submenuLinks.value.length],
  scheduleSubmenuPositionUpdate,
  { flush: "post" },
)

onMounted(() => {
  window.addEventListener("resize", scheduleSubmenuPositionUpdate)
  scheduleSubmenuPositionUpdate()
})

onBeforeUnmount(() => {
  window.removeEventListener("resize", scheduleSubmenuPositionUpdate)
})

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

    if (selectedCampaignId.value === null && routeName !== "Dashboard") {
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
          <div
            ref="mainNavLinksElement"
            class="main-nav-links"
            @scroll.passive="updateSubmenuPosition"
          >
            <RouterLink
              v-for="(link, index) in mainLinks"
              :key="link.to"
              :to="link.to"
              class="main-nav-link"
              :class="{
                'main-nav-link-home': index === 0,
                'main-nav-link-group-active': activeMainLinkIndex === index,
              }"
              :data-main-nav-index="index"
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

      <div v-if="hasSubmenu" id="submenu" ref="submenuElement">
        <nav
          ref="submenuNavElement"
          aria-label="Sub navigation"
          :style="{ marginLeft: `${submenuOffset}px` }"
        >
          <ul>
            <li v-for="child in submenuLinks" :key="child.name">
              <RouterLink :to="child.to">
                {{ child.label }}
              </RouterLink>
            </li>
          </ul>
        </nav>
      </div>
    </header>

    <div id="main">
      <main id="app-content">
        <RouterView />
      </main>
    </div>
  </div>
</template>
