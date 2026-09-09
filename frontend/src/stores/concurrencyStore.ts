import { computed, ref } from "vue"
import { changeAffectsEditor, type ResourceEditor } from "@/utils/editorChanges"

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
let generation = 0
const editorGroups = new Map<symbol, ResourceEditor[]>()
const editors = ref<ResourceEditor[]>([])
const refreshPending = new Set<number>()

function setEditors(key: symbol, value: ResourceEditor[]) {
  if (value.length) editorGroups.set(key, value)
  else editorGroups.delete(key)
  editors.value = [...editorGroups.values()].flat()
  remoteChanges.value = remoteChanges.value.filter((change) =>
    editors.value.some((editor) => changeAffectsEditor(change, editor, noticeCampaignId.value ?? -1)),
  )
  if (!editors.value.length) dismissNotice()
}

const hasNotice = computed(
  () => (
    conflict.value !== null
    || accessChanged.value
    || remoteChanges.value.length > 0
  ),
)

function recordConflict(failure: ApiFailure) {
  if (failure.status !== 409 || !failure.conflict) return
  conflict.value = failure.conflict
}

async function pollCampaignChanges(campaignId: number) {
  if (polling) return false
  polling = true
  const requestGeneration = generation
  try {
    const previousCursor = campaignCursors.get(campaignId)
    const endpoint = previousCursor === undefined
      ? `campaigns/${campaignId}/changes`
      : `campaigns/${campaignId}/changes?after=${previousCursor}`
    const response = await GetAPI<CampaignChangesDto>(endpoint)
    if (requestGeneration !== generation) return false
    if (isApiFailure(response)) {
      if (response.status === 404) {
        noticeCampaignId.value = campaignId
        accessChanged.value = editors.value.some((editor) => editor.campaignId === campaignId)
        return !accessChanged.value
      }
      return false
    }

    campaignCursors.set(campaignId, response.cursor)
    if (response.changes.length) refreshPending.add(campaignId)
    const relevant = response.changes.filter((change) =>
      editors.value.some((editor) => changeAffectsEditor(change, editor, campaignId)),
    )
    if (relevant.length) {
      noticeCampaignId.value = campaignId
      remoteChanges.value = [...remoteChanges.value, ...relevant].slice(-250)
    }
    // Quietly refresh browsing views; never remount any open create/edit form.
    if (refreshPending.has(campaignId) && editors.value.length === 0) {
      return true
    }
    return false
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

function refreshCurrentView(campaignId?: number | null) {
  if (campaignId != null) refreshPending.delete(campaignId)
  dismissNotice()
  viewRevision.value += 1
}

function resetConcurrencyState() {
  generation += 1
  campaignCursors.clear()
  editorGroups.clear()
  editors.value = []
  refreshPending.clear()
  dismissNotice()
  viewRevision.value += 1
}

export function useConcurrencyStore() {
  return {
    hasActiveEditors: computed(() => editors.value.length > 0),
    setEditors,
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
