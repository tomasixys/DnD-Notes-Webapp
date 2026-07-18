import { computed, watch, type Ref } from "vue"
import { useRoute, useRouter } from "vue-router"

type EntryWithId = {
  id: number
}

type RouteEntrySelectionOptions<T extends EntryWithId> = {
  entries: Ref<T[]>
  routeName: string
  paramName?: string
  onRouteEntryChange?: () => void
}

export function useRouteEntrySelection<T extends EntryWithId>({
  entries,
  routeName,
  paramName = "id",
  onRouteEntryChange,
}: RouteEntrySelectionOptions<T>) {
  const route = useRoute()
  const router = useRouter()

  const rawEntryId = computed(() => {
    const routeValue = route.params[paramName]

    return Array.isArray(routeValue)
      ? routeValue[0]
      : routeValue
  })

  const hasEntryIdParameter = computed(() => {
    return (
      typeof rawEntryId.value === "string" &&
      rawEntryId.value.length > 0
    )
  })

  const entryIdFromUrl = computed<number | null>(() => {
    if (typeof rawEntryId.value !== "string") {
      return null
    }

    const id = Number(rawEntryId.value)

    return Number.isInteger(id) && id > 0
      ? id
      : null
  })

  const selectedEntry = computed<T | null>(() => {
    if (entryIdFromUrl.value === null) {
      return null
    }

    return (
      entries.value.find(
        (entry) => entry.id === entryIdFromUrl.value,
      ) ?? null
    )
  })

  watch(rawEntryId, () => {
    onRouteEntryChange?.()
  })

  function buildRouteParams(entryId: number | "") {
    return {
      ...route.params,
      [paramName]: entryId,
    }
  }

  async function openEntry(
    entryId: number,
    replace = false,
  ) {
    if (entryIdFromUrl.value === entryId) {
      onRouteEntryChange?.()
      return
    }

    const destination = {
      name: routeName,
      params: buildRouteParams(entryId),
    }

    if (replace) {
      await router.replace(destination)
    } else {
      await router.push(destination)
    }
  }

  async function ensureDefaultEntry() {
    if (
      hasEntryIdParameter.value ||
      entries.value.length === 0
    ) {
      return
    }

    await openEntry(entries.value[0].id, true)
  }

  async function replaceWithFirstEntry() {
    const firstEntry = entries.value[0]

    if (firstEntry) {
      await openEntry(firstEntry.id, true)
      return
    }

    await router.replace({
      name: routeName,
      params: buildRouteParams(""),
    })
  }

  return {
    entryIdFromUrl,
    hasEntryIdParameter,
    selectedEntry,
    openEntry,
    ensureDefaultEntry,
    replaceWithFirstEntry,
  }
}