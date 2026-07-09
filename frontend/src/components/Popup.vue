<script setup lang="ts">
defineProps<{
  title?: string
}>()

const emit = defineEmits<{
  close: []
}>()
</script>

<template>
  <Teleport to="body">
    <div class="popup-backdrop" @click.self="emit('close')">
      <article class="popup-panel">
        <header v-if="title || $slots.header" class="popup-header">
          <slot name="header">
            <h3>{{ title }}</h3>
          </slot>
        </header>

        <section class="popup-body">
          <slot />
        </section>

        <footer v-if="$slots.footer" class="popup-footer">
          <slot name="footer" />
        </footer>
      </article>
    </div>
  </Teleport>
</template>

<style scoped>
.popup-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.65);
}

.popup-panel {
  width: min(100%, 32rem);
  padding: 1.5rem;
  border: 1px solid var(--color-border);
  border-radius: 1rem;
  background: var(--color-bg-panel);
  box-shadow: var(--shadow-soft);
}

.popup-header h3 {
  margin: 0;
  font-size: 1.4rem;
}

.popup-body {
  margin-top: 1rem;
}

.popup-body p {
  margin: 0;
  color: var(--color-text-muted);
  line-height: 1.5;
}

.popup-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 1.5rem;
}
</style> 