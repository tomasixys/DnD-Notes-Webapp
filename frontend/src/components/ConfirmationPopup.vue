<script setup lang="ts">
import Popup from "../components/Popup.vue"

defineProps<{
  title: string
  message: string
  confirmText?: string
  cancelText?: string
}>()

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()
</script>

<template>
  <Popup :title="title" @close="emit('cancel')">
    <p>{{ message }}</p>

    <template #footer>
      <button
        type="button"
        class="secondary"
        @click="emit('cancel')"
      >
        {{ cancelText ?? "Cancel" }}
      </button>

      <button
        type="button"
        class="danger"
        @click="emit('confirm')"
      >
        {{ confirmText ?? "Delete" }}
      </button>
    </template>
  </Popup>
</template>