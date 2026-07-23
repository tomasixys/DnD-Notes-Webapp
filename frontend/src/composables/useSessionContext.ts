import { inject, type ComputedRef, type InjectionKey, type Ref } from "vue"

import type { SessionListItemDto } from "@/types/DataTransferObjects"

export type SessionContext = {
  sessions: Ref<SessionListItemDto[]>
  selectedSession: ComputedRef<SessionListItemDto | null>
  selectedSessionId: ComputedRef<number | null>
  selectionRevision: Ref<number>
  loadSessions: () => Promise<void>
  upsertSession: (session: SessionListItemDto) => void
  removeSession: (sessionId: number) => void
  openSession: (sessionId: number, replace?: boolean) => Promise<void>
  replaceWithFirstSession: () => Promise<void>
}

export const sessionContextKey: InjectionKey<SessionContext> = Symbol(
  "session-context",
)

export function useSessionContext(): SessionContext {
  const context = inject(sessionContextKey)
  if (!context) {
    throw new Error("Session context is unavailable")
  }
  return context
}
