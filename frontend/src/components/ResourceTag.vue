<script setup lang="ts">
import { computed } from "vue"
import { useRouter } from "vue-router"

import type {
  ResourceTagDto,
  ResourceType,
} from "@/types/DataTransferObjects"

const props = defineProps<{
  tag: ResourceTagDto
}>()

const router = useRouter()

const routeNames: Partial<Record<ResourceType, string>> = {
  session: "Sessions",
  person: "People",
  location: "Locations",
  faction: "Factions",
}

const isLinked = computed(
  () =>
    props.tag.resolutionState === "resolved" &&
    props.tag.referenceType !== null &&
    props.tag.referenceId !== null &&
    routeNames[props.tag.referenceType] !== undefined,
)

const title = computed(() => {
  if (isLinked.value) {
    return `Open ${props.tag.referenceType}: ${props.tag.label}`
  }

  if (props.tag.resolutionState === "unresolved") {
    return `No matching ${props.tag.referenceType ?? "resource"} found`
  }

  if (props.tag.resolutionState === "ambiguous") {
    return `More than one matching ${props.tag.referenceType ?? "resource"} found`
  }

  return undefined
})

async function openReference() {
  if (
    !isLinked.value ||
    props.tag.referenceType === null ||
    props.tag.referenceId === null
  ) {
    return
  }

  const routeName = routeNames[props.tag.referenceType]
  if (!routeName) return

  await router.push({
    name: routeName,
    params: { id: props.tag.referenceId },
  })
}
</script>

<template>
  <button
    v-if="isLinked"
    type="button"
    class="tag tag-link"
    :title="title"
    :aria-label="title"
    @click="openReference"
  >
    {{ tag.label }}
  </button>

  <span
    v-else
    class="tag"
    :class="{
      'tag-unresolved': tag.resolutionState === 'unresolved',
      'tag-ambiguous': tag.resolutionState === 'ambiguous',
    }"
    :title="title"
  >
    {{ tag.label }}
  </span>
</template>


<style scoped>

.tag {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.55rem;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  color: var(--color-text-muted);
  background: rgba(0, 0, 0, 0.16);
  font-size: 0.8rem;
  font-weight: 500;
  line-height: 1.2;
}

.tag-link {
  border-color: var(--color-accent-dark);
  color: var(--color-accent-soft);
  text-decoration: none;
}

.tag-link:hover,
.tag-link:focus-visible {
  border-color: var(--color-accent);
  background: rgba(201, 137, 63, 0.14);
  color: var(--color-text);
}

.tag-link:focus-visible {
  outline: 2px solid var(--color-accent-soft);
  outline-offset: 2px;
}

.tag-unresolved,
.tag-ambiguous {
  border-style: dashed;
}

.tag-unresolved {
  opacity: 0.72;
}

</style>
