<script setup lang="ts">
import { RouterLink, useRoute } from "vue-router"

const route = useRoute()
</script>

<template>
  <main class="auth-page">
    <section class="auth-card">
      <h1>Session expired</h1>
      <p>Your local campaign state has been cleared. Sign in again to continue.</p>
      <RouterLink
        class="button-link"
        :to="{ name: 'Login', query: { redirect: route.query.redirect ?? '/dashboard' } }"
      >
        Return to sign in
      </RouterLink>
    </section>
  </main>
</template>
