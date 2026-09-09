import { computed, ref } from "vue"
import {
  configureApiSecurity,
  GetAPI,
  isApiFailure,
  PostAPI,
  type ApiFailure,
} from "@/apihelpers"
import type {
  AccountMutationDto,
  AuthSessionDto,
  AuthUserDto,
  CampaignsDto,
  SessionMutationDto,
} from "@/types/DataTransferObjects"
import { useCampaignStore } from "@/stores/campaignStore"
import { useSearchStore } from "@/stores/searchStore"
import { useConcurrencyStore } from "@/stores/concurrencyStore"

export type AuthState =
  | "loading"
  | "anonymous"
  | "authenticated"
  | "expired"

type NavigationHandler = (
  destination: "login" | "expired" | "access-denied",
) => void

const state = ref<AuthState>("loading")
const user = ref<AuthUserDto | null>(null)
const csrfToken = ref<string | null>(null)
const authenticationRequired = ref(true)
const lastFailure = ref<ApiFailure | null>(null)
let bootstrapPromise: Promise<void> | null = null
let navigate: NavigationHandler = () => undefined

const isAuthenticated = computed(
  () => state.value === "authenticated" && user.value !== null,
)

function clearUserScopedState() {
  useCampaignStore().clearUserState()
  useSearchStore().clearSearchCache()
  useConcurrencyStore().resetConcurrencyState()
}

function applySession(session: AuthSessionDto) {
  const accountChanged = user.value?.id !== session.user.id
  if (accountChanged) clearUserScopedState()
  user.value = session.user
  csrfToken.value = session.csrfToken || null
  authenticationRequired.value = session.authenticationRequired
  state.value = "authenticated"
  lastFailure.value = null
  useCampaignStore().setUserScope(session.user.id)
}

async function hydrateCampaigns(userId: number) {
  const response = await GetAPI<CampaignsDto[]>(
    "campaigns",
    { notifyFailures: false },
  )
  if (
    isApiFailure(response)
    || !Array.isArray(response)
    || state.value !== "authenticated"
    || user.value?.id !== userId
  ) {
    return
  }
  useCampaignStore().setCampaigns(response)
}

function clearSession(nextState: AuthState) {
  user.value = null
  csrfToken.value = null
  authenticationRequired.value = true
  state.value = nextState
  clearUserScopedState()
}

function handleApiFailure(failure: ApiFailure) {
  lastFailure.value = failure
  if (failure.status === 409) {
    useConcurrencyStore().recordConflict(failure)
  }
  if (failure.status === 401 && state.value === "authenticated") {
    clearSession("expired")
    navigate("expired")
  } else if (failure.status === 403) {
    navigate("access-denied")
  }
}

configureApiSecurity({
  csrfToken: () => csrfToken.value,
  onFailure: handleApiFailure,
})

async function bootstrap() {
  if (bootstrapPromise) return bootstrapPromise
  bootstrapPromise = (async () => {
    state.value = "loading"
    const response = await GetAPI<AuthSessionDto>(
      "auth/session",
      { notifyFailures: false },
    )
    if (isApiFailure(response)) {
      lastFailure.value = response
      clearSession("anonymous")
      return
    }
    applySession(response)
    await hydrateCampaigns(response.user.id)
  })()
  return bootstrapPromise
}

async function login(username: string, password: string) {
  const response = await PostAPI<AuthSessionDto>(
    "auth/login",
    { username, password },
    { notifyFailures: false },
  )
  if (isApiFailure(response)) {
    lastFailure.value = response
    return response
  }
  applySession(response)
  await hydrateCampaigns(response.user.id)
  return response
}

async function logout(allSessions = false) {
  await PostAPI<SessionMutationDto>(
    allSessions ? "auth/logout-all" : "auth/logout",
    {},
    { notifyFailures: false },
  )
  clearSession("anonymous")
}

async function completeAccountToken(
  purpose: "activate" | "reset-password",
  token: string,
  password: string,
  profile?: { username: string; displayName: string },
) {
  const response = await PostAPI<AccountMutationDto>(
    `auth/${purpose}`,
    { token, password, ...profile },
    { notifyFailures: false },
  )
  if (isApiFailure(response)) {
    lastFailure.value = response
    return response
  }
  lastFailure.value = null
  return response
}

function setNavigationHandler(handler: NavigationHandler) {
  navigate = handler
}

export function useAuthStore() {
  return {
    state,
    user,
    csrfToken,
    authenticationRequired,
    lastFailure,
    isAuthenticated,
    bootstrap,
    login,
    logout,
    completeAccountToken,
    setNavigationHandler,
  }
}
