import { computed, ref } from "vue"

import {
  GetAPI,
  isApiFailure,
  type ApiFailure,
  type RevisionConflict,
} from "@/apihelpers"
import type {
  CampaignChangeDto,
  CampaignChangesDto,
} from "@/types/DataTransferObjects"

const campaignCursors = new Map<number, number>()
const conflict = ref<RevisionConflict | null>(null)
const remoteChanges = ref<CampaignChangeDto[]>([])
const accessChanged = ref(false)
const noticeCampaignId = ref<number | null>(null)
const viewRevision = ref(0)
let polling = false

const hasNotice = computed(
  () => (
    conflict.value !== null
    || accessChanged.value
    || remoteChanges.value.length > 0
  ),
)

function recordConflict(failure: ApiFailure) {
  if (failure.status !== 409) return
  conflict.value = failure.conflict ?? {
    code: "revision_conflict",
    resourceType: "resource",
    resourceId: null,
    expectedRevision: 0,
    currentRevision: null,
    message: failure.message,
  }
}

async function pollCampaignChanges(campaignId: number) {
  if (polling) return
  polling = true
  try {
    const previousCursor = campaignCursors.get(campaignId)
    const endpoint = previousCursor === undefined
      ? `campaigns/${campaignId}/changes`
      : `campaigns/${campaignId}/changes?after=${previousCursor}`
    const response = await GetAPI<CampaignChangesDto>(endpoint)
    if (isApiFailure(response)) {
      if (response.status === 404) {
        noticeCampaignId.value = campaignId
        accessChanged.value = true
      }
      return
    }

    campaignCursors.set(campaignId, response.cursor)
    if (response.changes.length === 0) return
    noticeCampaignId.value = campaignId
    remoteChanges.value = [
      ...remoteChanges.value,
      ...response.changes,
    ].slice(-250)
  } finally {
    polling = false
  }
}

function dismissNotice() {
  conflict.value = null
  remoteChanges.value = []
  accessChanged.value = false
  noticeCampaignId.value = null
}

function refreshCurrentView() {
  dismissNotice()
  viewRevision.value += 1
}

function resetConcurrencyState() {
  campaignCursors.clear()
  dismissNotice()
  viewRevision.value += 1
}

export function useConcurrencyStore() {
  return {
    conflict,
    remoteChanges,
    accessChanged,
    noticeCampaignId,
    viewRevision,
    hasNotice,
    recordConflict,
    pollCampaignChanges,
    dismissNotice,
    refreshCurrentView,
    resetConcurrencyState,
  }
}
