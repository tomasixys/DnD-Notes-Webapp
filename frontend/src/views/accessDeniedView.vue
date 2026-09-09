<script setup lang="ts">
import { RouterLink } from "vue-router"
import { useAuthStore } from "@/stores/authStore"

const auth = useAuthStore()
</script>

<template>
  <main class="auth-page">
    <section class="auth-card">
      <h1>Access denied</h1>
      <p>
        {{ auth.lastFailure.value?.message
          ?? "Your account does not have permission for that operation."
        }}
      </p>
      <RouterLink class="button-link" to="/dashboard">
        Return to dashboard
      </RouterLink>
    </section>
  </main>
</template>
