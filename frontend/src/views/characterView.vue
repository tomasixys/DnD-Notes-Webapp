<script setup lang="ts">
import { provide, ref, watch } from "vue"
import { RouterView, useRoute } from "vue-router"

import { GetAPI } from "@/apihelpers"
import { characterContextKey } from "@/composables/useCharacterContext"
import { useCampaignStore } from "@/stores/campaignStore"
import type { CharacterDto } from "@/types/DataTransferObjects"

const route = useRoute()
const { selectedCampaignId } = useCampaignStore()

const character = ref<CharacterDto | null>(null)
const loading = ref(false)
const errorMessage = ref("")

function personIdFromRoute(): number | null {
  const rawValue = Array.isArray(route.params.personId)
    ? route.params.personId[0]
    : route.params.personId
  const personId = Number(rawValue)
  return Number.isInteger(personId) && personId > 0 ? personId : null
}

async function loadCharacter() {
  character.value = null
  errorMessage.value = ""
  if (!selectedCampaignId.value) {
    return
  }

  loading.value = true
  const personId = personIdFromRoute()
  const endpoint = personId === null
    ? `campaigns/${selectedCampaignId.value}/characters/active`
    : `campaigns/${selectedCampaignId.value}/characters/${personId}`
  const response = await GetAPI(endpoint)
  loading.value = false

  if (response?.success === false) {
    errorMessage.value = personId === null
      ? "The active character could not be loaded."
      : "That character profile could not be loaded."
    return
  }

  character.value = response as CharacterDto | null
}

function setCharacter(updatedCharacter: CharacterDto | null) {
  character.value = updatedCharacter
  errorMessage.value = ""
}

provide(characterContextKey, {
  character,
  loading,
  errorMessage,
  loadCharacter,
  setCharacter,
})

watch(
  () => [selectedCampaignId.value, route.params.personId],
  () => void loadCharacter(),
  { immediate: true },
)
</script>

<template>
  <RouterView />
</template>
