import { inject, type InjectionKey, type Ref } from "vue"

import type { CharacterDto } from "@/types/DataTransferObjects"

export type CharacterContext = {
  character: Ref<CharacterDto | null>
  loading: Ref<boolean>
  errorMessage: Ref<string>
  loadCharacter: () => Promise<void>
  setCharacter: (character: CharacterDto | null) => void
}

export const characterContextKey: InjectionKey<CharacterContext> = Symbol(
  "character-context",
)

export function useCharacterContext(): CharacterContext {
  const context = inject(characterContextKey)
  if (!context) {
    throw new Error("Character context is unavailable")
  }
  return context
}
