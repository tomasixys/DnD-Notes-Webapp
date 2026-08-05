<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import {
  DeleteAPI,
  GetAPI,
  isApiFailure,
  PostAPI,
  PutAPI,
} from "@/apihelpers"
import { useAuthStore } from "@/stores/authStore"
import type {
  AccountMutationDto,
  AdminCampaignDto,
  AdminUserDto,
  IssuedAccountTokenDto,
  SessionMutationDto,
} from "@/types/DataTransferObjects"

const router = useRouter()
const auth = useAuthStore()
const users = ref<AdminUserDto[]>([])
const orphanedCampaigns = ref<AdminCampaignDto[]>([])
const reason = ref("")
const message = ref("")
const issuedLink = ref("")
const loading = ref(false)
const recoveryOwnerByCampaign = ref<Record<number, number | null>>({})

const activeRecoveryOwners = computed(() => users.value.filter(
  (user) => user.status === "active" && user.systemRole !== "custodian",
))

function requireReason(): string | null {
  const value = reason.value.trim()
  if (!value) {
    message.value = "Enter an administrative reason first."
    return null
  }
  return value
}

async function loadUsers() {
  loading.value = true
  const response = await GetAPI<AdminUserDto[]>("auth/admin/users")
  loading.value = false
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  users.value = response
}

async function loadOrphanedCampaigns() {
  const auditReason = requireReason()
  if (!auditReason) return
  const response = await GetAPI<AdminCampaignDto[]>(
    `admin/campaigns?reason=${encodeURIComponent(auditReason)}`,
  )
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  orphanedCampaigns.value = response
  message.value = response.length
    ? "Recovery queue refreshed."
    : "No orphaned campaigns require recovery."
}

async function setUserStatus(
  user: AdminUserDto,
  status: "active" | "suspended",
) {
  const auditReason = requireReason()
  if (!auditReason) return
  const response = await PutAPI<AccountMutationDto>(
    `auth/admin/users/${user.id}/status`,
    { status, reason: auditReason },
  )
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  message.value = response.message
  await loadUsers()
}

async function revokeUserSessions(user: AdminUserDto) {
  const auditReason = requireReason()
  if (!auditReason) return
  const response = await PostAPI<SessionMutationDto>(
    `auth/admin/users/${user.id}/revoke-sessions`,
    { reason: auditReason },
  )
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  message.value = `${response.message} (${response.revokedSessions})`
  await loadUsers()
}

async function issuePasswordReset(user: AdminUserDto) {
  const response = await PostAPI<IssuedAccountTokenDto>(
    `auth/admin/users/${user.id}/password-reset`,
    {},
  )
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  const url = new URL("/reset-password", window.location.origin)
  url.searchParams.set("token", response.token)
  issuedLink.value = url.toString()
  message.value = `One-time password reset link created for ${user.username}.`
}

async function deleteUser(user: AdminUserDto) {
  if (!window.confirm(
    `Delete ${user.username}? Their campaigns will be preserved for recovery.`,
  )) return
  const response = await DeleteAPI<AccountMutationDto>(
    `auth/admin/users/${user.id}`,
  )
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  message.value = response.message
  await loadUsers()
}

async function revokeAllSessions() {
  const auditReason = requireReason()
  if (!auditReason) return
  if (!window.confirm(
    "Revoke every active session? You will also be signed out.",
  )) return
  const response = await PostAPI<SessionMutationDto>(
    "auth/admin/sessions/revoke-all",
    { reason: auditReason },
    { notifyFailures: false },
  )
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  await auth.logout()
  await router.replace({ name: "Login" })
}

async function recoverCampaign(campaign: AdminCampaignDto) {
  const auditReason = requireReason()
  const ownerUserId = recoveryOwnerByCampaign.value[campaign.id]
  if (!auditReason || !ownerUserId) {
    message.value = "Choose an active recovery owner and enter a reason."
    return
  }
  const response = await PostAPI<AdminCampaignDto>(
    `admin/campaigns/${campaign.id}/recover`,
    { ownerUserId, reason: auditReason },
  )
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  message.value = `${response.name} has a new owner.`
  await loadOrphanedCampaigns()
}

async function copyIssuedLink() {
  if (!issuedLink.value) return
  try {
    await navigator.clipboard.writeText(issuedLink.value)
    message.value = "One-time link copied."
  } catch {
    message.value = "Copy the one-time link manually."
  }
}

onMounted(loadUsers)
</script>

<template>
  <section class="admin-page">
    <header class="admin-header">
      <div>
        <p class="eyebrow">Hosted server</p>
        <h1>System administration</h1>
        <p>
          Account, session, and campaign-recovery actions are recorded in the
          security audit log.
        </p>
      </div>
    </header>

    <label class="reason-field">
      Administrative reason
      <input
        v-model="reason"
        placeholder="Incident, support request, or recovery reference"
      />
    </label>

    <p v-if="message" class="form-success" role="status">{{ message }}</p>

    <section class="admin-section">
      <div class="section-heading">
        <div>
          <h2>Accounts and sessions</h2>
          <p>Suspension immediately revokes that account’s active sessions.</p>
        </div>
        <button type="button" class="secondary" @click="loadUsers">
          {{ loading ? "Refreshing…" : "Refresh" }}
        </button>
      </div>

      <div class="admin-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Account</th>
              <th>Status</th>
              <th>Campaigns</th>
              <th>Sessions</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td>
                <strong>{{ user.displayName || user.username }}</strong>
                <small>{{ user.username }} · {{ user.systemRole }}</small>
              </td>
              <td>{{ user.status }}</td>
              <td>{{ user.campaignMemberships }}</td>
              <td>{{ user.activeSessions }}</td>
              <td>
                <div class="row-actions">
                  <button
                    v-if="
                      user.status === 'active'
                      && user.systemRole !== 'custodian'
                      && user.id !== auth.user.value?.id
                    "
                    type="button"
                    class="secondary"
                    @click="setUserStatus(user, 'suspended')"
                  >
                    Suspend
                  </button>
                  <button
                    v-if="user.status === 'suspended'"
                    type="button"
                    class="secondary"
                    @click="setUserStatus(user, 'active')"
                  >
                    Reactivate
                  </button>
                  <button
                    v-if="user.systemRole !== 'custodian'"
                    type="button"
                    class="secondary"
                    @click="revokeUserSessions(user)"
                  >
                    Revoke sessions
                  </button>
                  <button
                    v-if="
                      user.status !== 'deleted'
                      && user.systemRole !== 'custodian'
                    "
                    type="button"
                    class="secondary"
                    @click="issuePasswordReset(user)"
                  >
                    Reset link
                  </button>
                  <button
                    v-if="
                      user.id !== auth.user.value?.id
                      && user.status !== 'deleted'
                      && user.systemRole !== 'custodian'
                    "
                    type="button"
                    class="danger"
                    @click="deleteUser(user)"
                  >
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="issuedLink" class="issued-link">
        <label>
          One-time password reset link
          <input :value="issuedLink" readonly />
        </label>
        <button type="button" class="secondary" @click="copyIssuedLink">
          Copy link
        </button>
      </div>

      <button type="button" class="danger incident-action" @click="revokeAllSessions">
        Revoke every active session
      </button>
    </section>

    <section class="admin-section">
      <div class="section-heading">
        <div>
          <h2>Campaign recovery</h2>
          <p>Deleted owners never delete campaign data automatically.</p>
        </div>
        <button type="button" class="secondary" @click="loadOrphanedCampaigns">
          Load recovery queue
        </button>
      </div>

      <article
        v-for="campaign in orphanedCampaigns"
        :key="campaign.id"
        class="recovery-row"
      >
        <strong>{{ campaign.name }}</strong>
        <select v-model="recoveryOwnerByCampaign[campaign.id]">
          <option :value="null">Choose new owner</option>
          <option
            v-for="user in activeRecoveryOwners"
            :key="user.id"
            :value="user.id"
          >
            {{ user.displayName || user.username }} ({{ user.username }})
          </option>
        </select>
        <button type="button" @click="recoverCampaign(campaign)">
          Assign owner
        </button>
      </article>
    </section>
  </section>
</template>

<style scoped>
.admin-page {
  display: grid;
  gap: 1.5rem;
  margin: 0 auto;
  max-width: 78rem;
}

.admin-header,
.section-heading,
.issued-link,
.recovery-row {
  align-items: end;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
}

.admin-header h1,
.admin-header p,
.section-heading h2,
.section-heading p {
  margin: 0;
}

.eyebrow {
  color: var(--color-accent-soft);
  font-size: 0.8rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.reason-field {
  max-width: 42rem;
}

.admin-section {
  background: rgba(255, 255, 255, 0.035);
  border: 1px solid var(--color-border);
  border-radius: 0.8rem;
  display: grid;
  gap: 1rem;
  padding: 1.25rem;
}

.admin-table-wrap {
  overflow-x: auto;
}

table {
  border-collapse: collapse;
  width: 100%;
}

th,
td {
  border-bottom: 1px solid var(--color-border);
  padding: 0.75rem;
  text-align: left;
  vertical-align: top;
}

td small {
  color: var(--color-text-muted);
  display: block;
}

.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.row-actions button {
  padding: 0.4rem 0.65rem;
}

.issued-link {
  align-items: end;
}

.issued-link label,
.recovery-row select {
  flex: 1;
}

.incident-action {
  justify-self: start;
}

@media (max-width: 700px) {
  .admin-header,
  .section-heading,
  .issued-link,
  .recovery-row {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
