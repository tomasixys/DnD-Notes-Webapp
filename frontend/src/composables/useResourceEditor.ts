import { onBeforeUnmount, watch } from "vue"
import { useConcurrencyStore } from "@/stores/concurrencyStore"
import type { ResourceEditor } from "@/utils/editorChanges"

// Create forms register a null ID: preserve the draft without a remote-edit notice.
export function useResourceEditor(readEditors: () => ResourceEditor[]) {
  const store = useConcurrencyStore()
  const key = Symbol("resource-editor")
  watch(readEditors, (editors) => store.setEditors(key, editors), { immediate: true, deep: true, flush: "sync" })
  onBeforeUnmount(() => store.setEditors(key, []))
}
