<script setup lang="ts">
import { computed, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { isApiFailure } from "@/apihelpers"
import { useAuthStore } from "@/stores/authStore"

const props = defineProps<{
  purpose: "activate" | "reset-password"
}>()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const token = ref(
  typeof route.query.token === "string" ? route.query.token : "",
)
const hasLinkToken = Boolean(token.value)
const password = ref("")
const username = ref("")
const displayName = ref("")
const confirmation = ref("")
const submitting = ref(false)
const message = ref("")
const title = computed(() => (
  props.purpose === "activate" ? "Activate account" : "Reset password"
))

async function submit() {
  if (password.value !== confirmation.value) {
    message.value = "Passwords do not match."
    return
  }
  submitting.value = true
  message.value = ""
  const response = await auth.completeAccountToken(
    props.purpose,
    token.value,
    password.value,
    props.purpose === "activate"
      ? { username: username.value.trim(), displayName: displayName.value.trim() }
      : undefined,
  )
  submitting.value = false
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  await router.replace({
    name: "Login",
    query: { message: response.message },
  })
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-card">
      <h1>{{ title }}</h1>
      <p>{{ purpose === 'activate' ? 'Choose your account details to join the server.' : 'Choose a new password for your account.' }}</p>

      <form @submit.prevent="submit">
        <label v-if="!hasLinkToken">
          Account token
          <input v-model="token" autocomplete="one-time-code" required />
        </label>

        <template v-if="purpose === 'activate'">
          <label>
            Username
            <input v-model="username" autocomplete="username" minlength="3" maxlength="64" required />
          </label>
          <label>
            Display name
            <input v-model="displayName" autocomplete="nickname" maxlength="200" required />
          </label>
        </template>

        <label>
          New password
          <input
            v-model="password"
            type="password"
            autocomplete="new-password"
            minlength="15"
            required
          />
        </label>

        <label>
          Confirm password
          <input
            v-model="confirmation"
            type="password"
            autocomplete="new-password"
            minlength="15"
            required
          />
        </label>

        <p v-if="message" class="form-error" role="alert">
          {{ message }}
        </p>

        <button type="submit" :disabled="submitting">
          {{ submitting ? "Saving…" : title }}
        </button>
      </form>
    </section>
  </main>
</template>
