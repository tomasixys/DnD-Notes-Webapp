<script setup>

import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router"
import { useCampaignStore } from "@/stores/campaignStore"
import { useAuthStore } from "@/stores/authStore"
import { useConcurrencyStore } from "@/stores/concurrencyStore"
import { GetAPI, isApiFailure } from "@/apihelpers"
import { useSearchStore } from "@/stores/searchStore"
import bannerImageDefault from "./assets/banner.png"

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const concurrency = useConcurrencyStore()
const draftCopyStatus = ref("")
const accountMenuOpen = ref(false)
const accountMenuElement = ref(null)
const accountMenuButtonElement = ref(null)

const accountName = computed(() => (
  auth.user.value?.displayName?.trim()
  || auth.user.value?.username?.trim()
  || "User"
))
const accountInitial = computed(() => (
  Array.from(accountName.value)[0]?.toLocaleUpperCase() ?? "?"
))
const canViewInvitations = computed(() => (
  auth.authenticationRequired.value
))
const canAdministerServer = computed(() => (
  auth.authenticationRequired.value
  && auth.user.value?.systemRole === "admin"
))

const {
  selectedCampaignId,
  selectedCampaign,
  selectedCampaignImageUrl,
  selectedCampaignBannerUrl,
  setCampaigns,
} = useCampaignStore()

const mainLinks = computed(() => [
  {
    label: selectedCampaign.value?.name ?? "Campaign Notes",
    to: "/dashboard",
  },
  { label: "Sessions", to: "/sessions/notes" },
  { label: "People", to: "/people" },
  { label: "Locations", to: "/locations" },
  { label: "Factions", to: "/factions" },
  { label: "Character", to: "/character/overview" },
  { label: "Inventory", to: "/inventory" },
  ...(
    auth.authenticationRequired.value
    && selectedCampaign.value?.capabilities.includes("membership.read")
      ? [{ label: "Members", to: "/members" }]
      : []
  ),
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
const isAuthPage = computed(() => route.meta.authPage === true)
const isAccountPage = computed(() => route.meta.accountPage === true)

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

async function pollCampaignChanges() {
  if (
    !auth.isAuthenticated.value
    || selectedCampaignId.value === null
    || isAuthPage.value
    || isAccountPage.value
  ) {
    return
  }
  await concurrency.pollCampaignChanges(selectedCampaignId.value)
}

async function refreshCurrentView() {
  const response = await GetAPI("campaigns")
  if (!isApiFailure(response) && Array.isArray(response)) {
    setCampaigns(response)
  }
  useSearchStore().clearSearchCache()
  concurrency.refreshCurrentView()
  await pollCampaignChanges()
}

async function copyVisibleDraft() {
  const controls = document.querySelectorAll(
    "#app-content input:not([type='password']):not([type='file']), "
    + "#app-content textarea, #app-content select",
  )
  const draft = Array.from(controls)
    .map((control) => {
      const label = (
        control.getAttribute("aria-label")
        || control.getAttribute("name")
        || control.id
        || control.closest("label")?.textContent?.trim()
        || "Field"
      )
      const value = control.type === "checkbox"
        ? (control.checked ? "yes" : "no")
        : control.value
      return `${label}: ${value}`
    })
    .filter((line) => line.split(": ", 2)[1]?.trim())
    .join("\n\n")
  if (!draft) {
    draftCopyStatus.value = "No open form values found."
    return
  }
  try {
    await navigator.clipboard.writeText(draft)
    draftCopyStatus.value = "Draft copied."
  } catch {
    draftCopyStatus.value = "Copy was blocked by the browser."
  }
}

function pollOnFocus() {
  if (document.visibilityState === "visible") {
    void pollCampaignChanges()
  }
}

function closeAccountMenu({ restoreFocus = false } = {}) {
  if (!accountMenuOpen.value) {
    return
  }

  accountMenuOpen.value = false
  if (restoreFocus) {
    void nextTick(() => accountMenuButtonElement.value?.focus())
  }
}

function toggleAccountMenu() {
  accountMenuOpen.value = !accountMenuOpen.value
}

function closeAccountMenuOnOutsideClick(event) {
  if (
    accountMenuOpen.value
    && event.target instanceof Node
    && !accountMenuElement.value?.contains(event.target)
  ) {
    closeAccountMenu()
  }
}

function closeAccountMenuOnEscape(event) {
  if (event.key === "Escape" && accountMenuOpen.value) {
    closeAccountMenu({ restoreFocus: true })
  }
}

let changePollTimer = null

onMounted(() => {
  window.addEventListener("resize", scheduleSubmenuPositionUpdate)
  window.addEventListener("focus", pollOnFocus)
  window.addEventListener("online", pollOnFocus)
  document.addEventListener("visibilitychange", pollOnFocus)
  document.addEventListener("pointerdown", closeAccountMenuOnOutsideClick)
  document.addEventListener("keydown", closeAccountMenuOnEscape)
  changePollTimer = window.setInterval(
    () => void pollCampaignChanges(),
    15_000,
  )
  scheduleSubmenuPositionUpdate()
  void pollCampaignChanges()
})

onBeforeUnmount(() => {
  window.removeEventListener("resize", scheduleSubmenuPositionUpdate)
  window.removeEventListener("focus", pollOnFocus)
  window.removeEventListener("online", pollOnFocus)
  document.removeEventListener("visibilitychange", pollOnFocus)
  document.removeEventListener("pointerdown", closeAccountMenuOnOutsideClick)
  document.removeEventListener("keydown", closeAccountMenuOnEscape)
  if (changePollTimer !== null) {
    window.clearInterval(changePollTimer)
  }
})

watch(
  () => [selectedCampaignId.value, auth.isAuthenticated.value],
  () => {
    concurrency.dismissNotice()
    void pollCampaignChanges()
  },
)

watch(
  () => route.fullPath,
  () => closeAccountMenu(),
)

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
    if (
      route.meta.authPage === true
      || route.meta.accountPage === true
      || !auth.isAuthenticated.value
    ) {
      return
    }

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

async function logout() {
  closeAccountMenu()
  await auth.logout()
  await router.replace({ name: "Login" })
}

</script>

<template>
  <RouterView v-if="isAuthPage" />

  <div v-else id="app-shell">
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

          <div ref="accountMenuElement" class="account-menu">
            <button
              ref="accountMenuButtonElement"
              type="button"
              class="account-avatar"
              :class="{ 'account-avatar-active': isAccountPage }"
              aria-haspopup="menu"
              :aria-expanded="accountMenuOpen"
              aria-controls="account-menu-popover"
              :aria-label="`Open account menu for ${accountName}`"
              :title="accountName"
              @click="toggleAccountMenu"
            >
              <span aria-hidden="true">{{ accountInitial }}</span>
            </button>

            <div
              v-if="accountMenuOpen"
              id="account-menu-popover"
              class="account-menu-popover"
              role="menu"
              aria-label="Account menu"
            >
              <div class="account-menu-identity">
                <strong>{{ accountName }}</strong>
                <span>
                  {{ auth.user.value?.username }}
                  <template v-if="auth.user.value?.systemRole === 'admin'">
                    &middot; administrator
                  </template>
                </span>
              </div>

              <RouterLink role="menuitem" to="/profile">
                Account
              </RouterLink>
              <RouterLink
                v-if="canViewInvitations"
                role="menuitem"
                to="/invitations"
              >
                Invitations
              </RouterLink>
              <RouterLink
                v-if="canAdministerServer"
                role="menuitem"
                to="/admin"
              >
                Administration
              </RouterLink>
              <button
                v-if="auth.authenticationRequired.value"
                type="button"
                class="account-menu-signout"
                role="menuitem"
                @click="logout"
              >
                Sign out
              </button>
            </div>
          </div>
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

    <aside
      v-if="concurrency.hasNotice.value && !isAccountPage"
      class="concurrency-notice"
      aria-live="polite"
    >
      <div>
        <strong>
          {{ concurrency.conflict.value
            ? "Your changes were not saved."
            : concurrency.accessChanged.value
              ? "Your campaign access changed."
              : "This campaign changed in another client." }}
        </strong>
        <p v-if="concurrency.conflict.value">
          Copy any draft text you want to keep, then refresh this view and
          reapply it to the current version.
        </p>
        <p v-else-if="concurrency.accessChanged.value">
          Refresh to update your campaign list and current permissions. Any
          open form values remain untouched until you choose to refresh.
        </p>
        <p v-else>
          {{ concurrency.remoteChanges.value.length }} server
          {{ concurrency.remoteChanges.value.length === 1 ? "change is" : "changes are" }}
          ready. Refresh this view when you are ready; open form values are
          left untouched until then.
        </p>
      </div>
      <div class="concurrency-notice-actions">
        <button
          v-if="concurrency.conflict.value"
          type="button"
          class="secondary"
          @click="copyVisibleDraft"
        >
          Copy draft
        </button>
        <button type="button" @click="refreshCurrentView">
          Refresh view
        </button>
        <button
          type="button"
          class="secondary"
          @click="concurrency.dismissNotice"
        >
          Keep working
        </button>
      </div>
      <span v-if="draftCopyStatus" class="sr-only" aria-live="polite">
        {{ draftCopyStatus }}
      </span>
    </aside>

    <div id="main">
      <main id="app-content">
        <RouterView :key="concurrency.viewRevision.value" />
      </main>
    </div>
  </div>
</template>
