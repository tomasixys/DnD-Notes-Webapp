<script setup>

import { computed } from "vue"
import { RouterLink, RouterView, useRoute } from "vue-router"
import { useCampaignStore } from "@/stores/campaignStore"
import bannerImageDefault from "./assets/banner.png"

const route = useRoute()
const campaignNameDefault = "No Campaign Selected"
const { 
  selectedCampaign,
  hasSelectedCampaign,
  selectedCampaignImageUrl,
  selectedCampaignBannerUrl,
} = useCampaignStore()

const mainLinks = [
  { label: "Dashboard", to: "/" },
  { label: "Sessions", to: "/sessions" },
  { label: "People", to: "/people" },
  { label: "Locations", to: "/locations" },
  { label: "Factions", to: "/factions" },
  { label: "Rolls", to: "/rolls" },
]

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
</script>

<template>
  <div id="app-shell">
    <header id="app-header">

      <section id="banner">
        <h1>Campaign Notes</h1>
        <p class="campaign-name">{{ hasSelectedCampaign ? selectedCampaign.name : campaignNameDefault }}</p>
        <img 
        id="banner-graphics"
        :src="selectedCampaignBannerUrl ?? bannerImageDefault"
        alt="Banner graphics"
        />
      </section>

      <div>
        <nav id="main-nav" aria-label="Main navigation">
          <RouterLink
          v-for="link in mainLinks"
          :key="link.to"
          :to="link.to"
          class="main-nav-link"
          >
          {{ link.label }}
          </RouterLink>
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