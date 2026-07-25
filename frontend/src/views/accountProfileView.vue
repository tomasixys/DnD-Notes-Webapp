<script setup lang="ts">
import { useRouter } from "vue-router"
import { useAuthStore } from "@/stores/authStore"

const router = useRouter()
const auth = useAuthStore()

async function logout(allSessions = false) {
  await auth.logout(allSessions)
  await router.replace({ name: "Login" })
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-card">
      <h1>Account</h1>
      <dl v-if="auth.user.value" class="profile-details">
        <div>
          <dt>Display name</dt>
          <dd>{{ auth.user.value.displayName || "Not set" }}</dd>
        </div>
        <div>
          <dt>Username</dt>
          <dd>{{ auth.user.value.username }}</dd>
        </div>
        <div>
          <dt>Server role</dt>
          <dd>{{ auth.user.value.systemRole }}</dd>
        </div>
        <div>
          <dt>Authentication</dt>
          <dd>
            {{ auth.authenticationRequired.value
              ? "Server account"
              : "Local mode"
            }}
          </dd>
        </div>
      </dl>

      <div v-if="auth.authenticationRequired.value" class="auth-actions">
        <button type="button" @click="logout(false)">Sign out</button>
        <button type="button" class="secondary" @click="logout(true)">
          Sign out everywhere
        </button>
      </div>
    </section>
  </main>
</template>
