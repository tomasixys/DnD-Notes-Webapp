<script setup lang="ts">
import { computed, ref } from "vue"
import { useRouter } from "vue-router"
import { isApiFailure, PostAPI } from "@/apihelpers"
import { useAuthStore } from "@/stores/authStore"
import type { IssuedAccountTokenDto } from "@/types/DataTransferObjects"

const router = useRouter()
const auth = useAuthStore()
const inviting = ref(false)
const activationLink = ref("")
const accountMessage = ref("")
const canInviteAccounts = computed(
  () => (
    auth.authenticationRequired.value
    && auth.user.value?.systemRole === "admin"
  ),
)

function buildActivationLink(token: string): string {
  const url = new URL("/activate", window.location.origin)
  url.searchParams.set("token", token)
  return url.toString()
}

async function inviteAccount() {
  if (inviting.value) return
  inviting.value = true
  const response = await PostAPI<IssuedAccountTokenDto>(
    "auth/admin/invitations",
    {},
  )
  inviting.value = false
  if (isApiFailure(response)) {
    accountMessage.value = response.message
    return
  }
  activationLink.value = buildActivationLink(response.token)
  accountMessage.value = (
    "Account invitation created. Copy the activation link now."
  )
}

async function copyActivationLink() {
  if (!activationLink.value) return
  try {
    await navigator.clipboard.writeText(activationLink.value)
    accountMessage.value = "Activation link copied."
  } catch {
    accountMessage.value = "Copy the activation link manually."
  }
}

async function logout(allSessions = false) {
  await auth.logout(allSessions)
  await router.replace({ name: "Login" })
}
</script>

<template>
  <div class="account-page">
    <section class="auth-card account-card">
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

      <section v-if="canInviteAccounts" class="account-admin">
        <h2>Create server account invitation</h2>
        <p>
          Send a one-time invitation link to your friend. They choose their
          username, display name, and password when they accept.
        </p>
        <form @submit.prevent="inviteAccount">
          <button type="submit" :disabled="inviting">{{ inviting ? 'Creating…' : 'Create account invitation' }}</button>
        </form>
        <div v-if="activationLink" class="activation-link copy-link-row">
          <label>
            One-time activation link
            <input :value="activationLink" readonly />
          </label>
          <button
            type="button"
            class="secondary"
            @click="copyActivationLink"
          >
            Copy link
          </button>
        </div>
        <p v-if="accountMessage" class="form-success" role="status">
          {{ accountMessage }}
        </p>
      </section>
    </section>
  </div>
</template>

<style scoped>
.account-page {
  display: grid;
  justify-items: center;
}

.account-card {
  width: min(100%, 50rem);
  background: rgba(255, 255, 255, 0.035);
}

.account-admin {
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--color-border);
}

.account-admin h2 {
  font-size: 1.15rem;
}

.activation-link {
  display: grid;
  gap: 0.75rem;
  margin-top: 1rem;
}
</style>
