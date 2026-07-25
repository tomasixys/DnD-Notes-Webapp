import { computed, type MaybeRefOrGetter, toValue } from "vue"
import { useCampaignStore } from "@/stores/campaignStore"

export function useCampaignAuthorization(
  characterPersonId?: MaybeRefOrGetter<number | null | undefined>,
) {
  const { selectedCampaign, hasCapability } = useCampaignStore()

  const canWriteSharedResources = computed(
    () => hasCapability("shared_resource.write"),
  )
  const canCreateCharacter = computed(
    () => {
      const campaign = selectedCampaign.value
      if (!campaign || !hasCapability("character.self_create")) return false
      return (
        campaign.membershipRole === "owner"
        || campaign.assignedCharacterPersonId === null
      )
    },
  )
  const canManageMemberships = computed(
    () => hasCapability("membership.manage"),
  )
  function canWriteCharacterFor(personId: number | null | undefined): boolean {
    const campaign = selectedCampaign.value
    if (!campaign || personId === null || personId === undefined) return false
    return (
      campaign.membershipRole === "owner"
      || (
        campaign.capabilities.includes("assigned_character.write")
        && campaign.assignedCharacterPersonId === personId
      )
    )
  }
  const canWriteCharacter = computed(() =>
    canWriteCharacterFor(
      characterPersonId === undefined ? null : toValue(characterPersonId),
    ),
  )

  return {
    canWriteSharedResources,
    canCreateCharacter,
    canManageMemberships,
    canWriteCharacter,
    canWriteCharacterFor,
  }
}
