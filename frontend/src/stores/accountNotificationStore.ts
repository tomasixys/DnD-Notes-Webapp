import { computed, ref } from "vue"

import changelogSource from "../../../CHANGELOG.md?raw"
import { GetAPI, isApiFailure } from "@/apihelpers"
import { useAuthStore } from "@/stores/authStore"
import type {
  AccountNotificationSummaryDto,
  AuthUserDto,
} from "@/types/DataTransferObjects"

type SystemRole = AuthUserDto["systemRole"]

type SeenNotifications = {
  changelogFingerprint?: string
  systemRole?: SystemRole
}

const STORAGE_PREFIX = "dnd-notes-account-notifications"
const memoryState = new Map<number, SeenNotifications>()

function fingerprint(value: string): string {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash = Math.imul(hash ^ value.charCodeAt(index), 16777619)
  }
  return (hash >>> 0).toString(36)
}

const changelogFingerprint = fingerprint(changelogSource)
const pendingInvitationCount = ref(0)
const pendingIssueCount = ref(0)
const changelogUpdated = ref(false)
const systemRoleChanged = ref(false)
let refreshPromise: Promise<void> | null = null

function storageKey(userId: number): string {
  return `${STORAGE_PREFIX}:${userId}`
}

function isSystemRole(value: unknown): value is SystemRole {
  return value === "user" || value === "admin" || value === "custodian"
}

function readSeenNotifications(userId: number): SeenNotifications {
  try {
    const stored = localStorage.getItem(storageKey(userId))
    if (stored) {
      const parsed = JSON.parse(stored) as Record<string, unknown>
      const state: SeenNotifications = {
        ...(typeof parsed.changelogFingerprint === "string"
          ? { changelogFingerprint: parsed.changelogFingerprint }
          : {}),
        ...(isSystemRole(parsed.systemRole)
          ? { systemRole: parsed.systemRole }
          : {}),
      }
      memoryState.set(userId, state)
      return state
    }
  } catch {
    // Keep notifications functional when browser storage is unavailable.
  }
  return { ...(memoryState.get(userId) ?? {}) }
}

function writeSeenNotifications(
  userId: number,
  state: SeenNotifications,
): void {
  memoryState.set(userId, { ...state })
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(state))
  } catch {
    // The in-memory state still prevents repeated notices for this page load.
  }
}

function syncSeenNotifications(): void {
  const user = useAuthStore().user.value
  if (!user) {
    changelogUpdated.value = false
    systemRoleChanged.value = false
    return
  }

  const seen = readSeenNotifications(user.id)
  if (seen.systemRole === undefined) {
    seen.systemRole = user.systemRole
    writeSeenNotifications(user.id, seen)
  }
  changelogUpdated.value = (
    seen.changelogFingerprint !== changelogFingerprint
  )
  systemRoleChanged.value = seen.systemRole !== user.systemRole
}

function clearLiveCounts(): void {
  pendingInvitationCount.value = 0
  pendingIssueCount.value = 0
}

async function refreshNotifications(): Promise<void> {
  syncSeenNotifications()
  const auth = useAuthStore()
  const userId = auth.user.value?.id
  if (!auth.isAuthenticated.value || userId === undefined) {
    clearLiveCounts()
    return
  }
  if (!auth.authenticationRequired.value) {
    clearLiveCounts()
    return
  }
  if (refreshPromise) return refreshPromise

  refreshPromise = (async () => {
    const response = await GetAPI<AccountNotificationSummaryDto>(
      "notifications",
    )
    if (
      isApiFailure(response)
      || useAuthStore().user.value?.id !== userId
    ) {
      return
    }
    pendingInvitationCount.value = response.pendingCampaignInvitations
    pendingIssueCount.value = response.pendingIssueReports
  })().finally(() => {
    refreshPromise = null
  })
  return refreshPromise
}

function markChangelogSeen(): void {
  const user = useAuthStore().user.value
  if (!user) return
  const seen = readSeenNotifications(user.id)
  seen.changelogFingerprint = changelogFingerprint
  writeSeenNotifications(user.id, seen)
  syncSeenNotifications()
}

function markSystemRoleSeen(): void {
  const user = useAuthStore().user.value
  if (!user) return
  const seen = readSeenNotifications(user.id)
  seen.systemRole = user.systemRole
  writeSeenNotifications(user.id, seen)
  syncSeenNotifications()
}

const notificationCount = computed(() => (
  pendingInvitationCount.value
  + pendingIssueCount.value
  + (changelogUpdated.value ? 1 : 0)
  + (systemRoleChanged.value ? 1 : 0)
))

export function useAccountNotificationStore() {
  return {
    pendingInvitationCount,
    pendingIssueCount,
    changelogUpdated,
    systemRoleChanged,
    notificationCount,
    refreshNotifications,
    markChangelogSeen,
    markSystemRoleSeen,
  }
}
