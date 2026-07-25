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
const password = ref("")
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
      <p>Tokens are single-use and issued by a server administrator.</p>

      <form @submit.prevent="submit">
        <label>
          Account token
          <input v-model="token" autocomplete="one-time-code" required />
        </label>

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
