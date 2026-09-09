<script setup lang="ts">
import { computed, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { isApiFailure } from "@/apihelpers"
import { useAuthStore } from "@/stores/authStore"

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const username = ref("")
const password = ref("")
const submitting = ref(false)
const message = ref("")
const statusMessage = computed(() => (
  typeof route.query.message === "string"
    ? route.query.message
    : ""
))

const redirectTarget = computed(() => (
  typeof route.query.redirect === "string"
    && route.query.redirect.startsWith("/")
    && !route.query.redirect.startsWith("//")
    ? route.query.redirect
    : "/dashboard"
))

async function submit() {
  if (!username.value.trim() || !password.value) return
  submitting.value = true
  message.value = ""
  const response = await auth.login(username.value, password.value)
  submitting.value = false
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  await router.replace(redirectTarget.value)
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-card">
      <h1>Campaign Notes</h1>
      <p>Sign in with the account issued by this server.</p>
      <p v-if="statusMessage" class="form-success" role="status">
        {{ statusMessage }}
      </p>

      <form @submit.prevent="submit">
        <label>
          Username
          <input
            v-model="username"
            autocomplete="username"
            required
            autofocus
          />
        </label>

        <label>
          Password
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            required
          />
        </label>

        <p v-if="message" class="form-error" role="alert">
          {{ message }}
        </p>

        <button type="submit" :disabled="submitting">
          {{ submitting ? "Signing in…" : "Sign in" }}
        </button>
      </form>
    </section>
  </main>
</template>
