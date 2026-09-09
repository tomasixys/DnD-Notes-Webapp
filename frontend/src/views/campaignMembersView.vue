<script setup lang="ts">
import { useResourceEditor } from "@/composables/useResourceEditor"
import { computed, onBeforeMount, ref, watch } from "vue"
import { useRouter } from "vue-router"
import {
  DeleteAPI,
  GetAPI,
  isApiFailure,
  PostAPI,
  PutAPI,
} from "@/apihelpers"
import { useAuthStore } from "@/stores/authStore"
import { useCampaignStore } from "@/stores/campaignStore"
import type {
  CampaignInvitationDto,
  CampaignMembershipDto,
  CampaignOwnershipTransferDto,
  CampaignRole,
  CampaignsDto,
  DeleteResponseDto,
  IssuedCampaignInvitationDto,
} from "@/types/DataTransferObjects"

const router = useRouter()
const auth = useAuthStore()
const {
  selectedCampaign,
  selectedCampaignId,
  setCampaigns,
} = useCampaignStore()

const members = ref<CampaignMembershipDto[]>([])
const invitations = ref<CampaignInvitationDto[]>([])
const inviteUsername = ref("")
const inviteRole = ref<CampaignRole>("member")
const issuedLink = ref("")
const message = ref("")
const loading = ref(false)

const canManage = computed(
  () => selectedCampaign.value?.capabilities.includes(
    "membership.manage",
  ) ?? false,
)

function invitationLink(token: string): string {
  const url = new URL("/invitations/accept", window.location.origin)
  url.hash = new URLSearchParams({ token }).toString()
  return url.toString()
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

async function refreshCampaigns() {
  const response = await GetAPI<CampaignsDto[]>("campaigns")
  if (!isApiFailure(response)) setCampaigns(response)
}

async function loadMembers() {
  const campaignId = selectedCampaignId.value
  if (!campaignId) {
    members.value = []
    invitations.value = []
    return
  }
  loading.value = true
  message.value = ""
  const memberResponse = await GetAPI<CampaignMembershipDto[]>(
    `campaigns/${campaignId}/members`,
  )
  if (isApiFailure(memberResponse)) {
    message.value = memberResponse.message
    loading.value = false
    return
  }
  members.value = memberResponse

  if (canManage.value) {
    const invitationResponse = await GetAPI<CampaignInvitationDto[]>(
      `campaigns/${campaignId}/invitations`,
    )
    if (isApiFailure(invitationResponse)) {
      message.value = invitationResponse.message
    } else {
      invitations.value = invitationResponse
    }
  } else {
    invitations.value = []
  }
  loading.value = false
}

async function createInvitation() {
  const campaignId = selectedCampaignId.value
  if (!campaignId || !inviteUsername.value.trim()) return
  const response = await PostAPI<IssuedCampaignInvitationDto>(
    `campaigns/${campaignId}/invitations`,
    {
      username: inviteUsername.value.trim(),
      role: inviteRole.value,
    },
  )
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  issuedLink.value = invitationLink(response.token)
  inviteUsername.value = ""
  message.value = "Invitation sent. They can accept it from their Invitations page."
  await loadMembers()
}

async function replaceInvitation(invitationId: number) {
  const campaignId = selectedCampaignId.value
  if (!campaignId) return
  const response = await PostAPI<IssuedCampaignInvitationDto>(
    `campaigns/${campaignId}/invitations/${invitationId}/replace`,
    {},
  )
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  issuedLink.value = invitationLink(response.token)
  message.value = "Invitation renewed. They can accept it from their Invitations page."
  await loadMembers()
}

async function revokeInvitation(invitationId: number) {
  const campaignId = selectedCampaignId.value
  if (!campaignId) return
  const response = await DeleteAPI<CampaignInvitationDto>(
    `campaigns/${campaignId}/invitations/${invitationId}`,
  )
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  message.value = "Invitation revoked."
  await loadMembers()
}

async function copyIssuedLink() {
  if (!issuedLink.value) return
  try {
    await navigator.clipboard.writeText(issuedLink.value)
    message.value = "Invitation link copied."
  } catch {
    message.value = "Copy the invitation link manually."
  }
}

function selectInput(event: Event) {
  (event.target as HTMLInputElement).select()
}

async function changeRole(
  member: CampaignMembershipDto,
  event: Event,
) {
  const campaignId = selectedCampaignId.value
  const role = (event.target as HTMLSelectElement).value as CampaignRole
  if (!campaignId || role === member.role) return
  const response = await PutAPI<CampaignMembershipDto>(
    `campaigns/${campaignId}/members/${member.userId}/role`,
    { role },
  )
  if (isApiFailure(response)) {
    message.value = response.message
    await loadMembers()
    return
  }
  message.value = `${response.username}'s role is now ${response.role}.`
  await refreshCampaigns()
  await loadMembers()
}

async function removeMember(member: CampaignMembershipDto) {
  const campaignId = selectedCampaignId.value
  if (!campaignId) return
  const response = await DeleteAPI<DeleteResponseDto>(
    `campaigns/${campaignId}/members/${member.userId}`,
  )
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  message.value = `${member.username} was removed from the campaign.`
  await loadMembers()
}

async function leaveCampaign() {
  const campaignId = selectedCampaignId.value
  if (!campaignId) return
  const response = await DeleteAPI<DeleteResponseDto>(
    `campaigns/${campaignId}/members/self/leave`,
  )
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  await refreshCampaigns()
  await router.replace({ name: "Dashboard" })
}

async function transferOwnership(member: CampaignMembershipDto) {
  const campaignId = selectedCampaignId.value
  if (!campaignId) return
  const response = await PostAPI<CampaignOwnershipTransferDto>(
    `campaigns/${campaignId}/members/${member.userId}/transfer-ownership`,
    {},
  )
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  message.value = `Ownership transferred to ${response.newOwner.username}.`
  await refreshCampaigns()
  await loadMembers()
}

watch(selectedCampaignId, loadMembers)
onBeforeMount(async () => {
  if (!selectedCampaign.value) await refreshCampaigns()
  await loadMembers()
})
// Keep owner management forms and one-time links intact during background polling.
useResourceEditor(() => selectedCampaignId.value && canManage.value ? [{
  campaignId: selectedCampaignId.value,
  resourceType: "membership",
  resourceId: null,
}] : [])
</script>

<template>
  <section class="members-view">
    <header class="view-header">
      <h2>Campaign members</h2>
      <p v-if="selectedCampaign">
        Manage access to {{ selectedCampaign.name }}.
      </p>
    </header>

    <p v-if="message" class="member-message" role="status">
      {{ message }}
    </p>

    <template v-if="selectedCampaign">
      <article v-if="canManage" class="member-panel">
        <h3>Invite an existing server account</h3>
        <p class="empty-text">
          New players first accept a server invitation and choose their username.
        </p>
        <form class="invite-form" @submit.prevent="createInvitation">
          <label>
            Username
            <input v-model="inviteUsername" required autocomplete="off" />
          </label>
          <label>
            Initial role
            <select v-model="inviteRole">
              <option value="member">Member</option>
              <option value="viewer">Viewer</option>
            </select>
          </label>
          <button type="submit">Create invitation</button>
        </form>

        <div v-if="issuedLink" class="issued-link copy-link-row">
          <label>
            One-time invitation link
            <input :value="issuedLink" readonly @focus="selectInput" />
          </label>
          <button type="button" class="secondary" @click="copyIssuedLink">
            Copy link
          </button>
        </div>
      </article>

      <article class="member-panel">
        <div class="member-panel-heading">
          <h3>Members</h3>
          <button type="button" class="secondary" @click="leaveCampaign">
            Leave campaign
          </button>
        </div>
        <p v-if="loading">Loading members…</p>
        <ul v-else class="member-list">
          <li v-for="member in members" :key="member.id">
            <div>
              <strong>{{ member.displayName || member.username }}</strong>
              <small>
                @{{ member.username }}
                <template v-if="member.userId === auth.user.value?.id">
                  · you
                </template>
              </small>
            </div>
            <div class="member-actions">
              <select
                v-if="canManage"
                :value="member.role"
                :aria-label="`Role for ${member.username}`"
                @change="changeRole(member, $event)"
              >
                <option value="owner">Owner</option>
                <option value="member">Member</option>
                <option value="viewer">Viewer</option>
              </select>
              <span v-else class="role-label">{{ member.role }}</span>
              <button
                v-if="
                  canManage
                  && selectedCampaign.membershipRole === 'owner'
                  && member.userId !== auth.user.value?.id
                "
                type="button"
                class="secondary"
                @click="transferOwnership(member)"
              >
                Transfer ownership
              </button>
              <button
                v-if="canManage && member.userId !== auth.user.value?.id"
                type="button"
                class="danger"
                @click="removeMember(member)"
              >
                Remove
              </button>
            </div>
          </li>
        </ul>
      </article>

      <article v-if="canManage" class="member-panel">
        <h3>Invitation history</h3>
        <ul v-if="invitations.length" class="member-list">
          <li v-for="invitation in invitations" :key="invitation.id">
            <div>
              <strong>{{ invitation.displayName || invitation.username }}</strong>
              <small>
                @{{ invitation.username }} · {{ invitation.role }} ·
                {{ invitation.status }} · expires
                {{ formatDate(invitation.expiresAt) }}
              </small>
            </div>
            <div
              v-if="invitation.status === 'pending'"
              class="member-actions"
            >
              <button
                type="button"
                class="secondary"
                @click="replaceInvitation(invitation.id)"
              >
                Replace link
              </button>
              <button
                type="button"
                class="danger"
                @click="revokeInvitation(invitation.id)"
              >
                Revoke
              </button>
            </div>
          </li>
        </ul>
        <p v-else class="empty-text">No campaign invitations yet.</p>
      </article>
    </template>

    <p v-else>Select a campaign before managing its members.</p>
  </section>
</template>

<style scoped>
.members-view {
  display: grid;
  gap: 1rem;
}

.member-panel {
  padding: 1.25rem;
  border: 1px solid var(--color-border);
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.035);
}

.member-panel h3 {
  margin-top: 0;
}

.member-panel-heading,
.member-actions,
.issued-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.invite-form {
  display: grid;
  grid-template-columns: minmax(12rem, 1fr) minmax(9rem, 0.4fr) auto;
  gap: 0.75rem;
  align-items: end;
}

.issued-link {
  margin-top: 1rem;
}

.issued-link label {
  flex: 1;
}

.member-list {
  display: grid;
  gap: 0.75rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.member-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.9rem;
  border-radius: 0.65rem;
  background: rgba(0, 0, 0, 0.16);
}

.member-list small {
  display: block;
  margin-top: 0.2rem;
  color: var(--color-text-muted);
}

.member-actions {
  justify-content: flex-end;
}

.member-actions select {
  width: auto;
}

.member-message {
  color: var(--color-accent-soft);
}

.role-label {
  color: var(--color-text-muted);
  text-transform: capitalize;
}

@media (max-width: 760px) {
  .invite-form {
    grid-template-columns: 1fr;
  }

  .member-list li {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
