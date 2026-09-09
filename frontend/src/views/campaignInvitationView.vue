<script setup lang="ts">
import { onBeforeMount, onMounted, onBeforeUnmount, ref } from "vue"
import { RouterLink, useRoute, useRouter } from "vue-router"
import { GetAPI, isApiFailure, PostAPI } from "@/apihelpers"
import { useCampaignStore } from "@/stores/campaignStore"
import type {
  CampaignInvitationAcceptanceDto,
  CampaignInvitationDto,
  CampaignsDto,
} from "@/types/DataTransferObjects"

const route = useRoute()
const router = useRouter()
const { setCampaigns, selectCampaign } = useCampaignStore()
const pendingInvitationKey = "pendingCampaignInvitationToken"

const token = ref("")
const pending = ref<CampaignInvitationDto[]>([])
const acceptedCampaignId = ref<number | null>(null)
const message = ref("")
const submitting = ref(false)

function takeInvitationToken() {
  const fragment = new URLSearchParams(route.hash.replace(/^#/, ""))
  const routeToken = fragment.get("token") ?? (
    typeof route.query.token === "string" ? route.query.token : null
  )
  token.value = (
    routeToken
    ?? sessionStorage.getItem(pendingInvitationKey)
    ?? ""
  )
  sessionStorage.removeItem(pendingInvitationKey)
  if (routeToken) {
    void router.replace({ name: "AcceptCampaignInvitation" })
  }
}

async function loadPending() {
  const response = await GetAPI<CampaignInvitationDto[]>(
    "campaign-invitations/pending",
  )
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  pending.value = response
}

async function acceptInvitation(invitationId?: number) {
  if (submitting.value || (!invitationId && !token.value.trim())) return
  submitting.value = true
  message.value = ""
  const response = await PostAPI<CampaignInvitationAcceptanceDto>(
    invitationId ? `campaign-invitations/${invitationId}/accept` : "campaign-invitations/accept",
    invitationId ? {} : { token: token.value.trim() },
  )
  submitting.value = false
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }

  const campaigns = await GetAPI<CampaignsDto[]>("campaigns")
  if (!isApiFailure(campaigns)) {
    setCampaigns(campaigns)
    selectCampaign(response.invitation.campaignId)
  }
  acceptedCampaignId.value = response.invitation.campaignId
  token.value = ""
  message.value = `You joined ${response.invitation.campaignName} as ${response.membership.role}.`
  await loadPending()
}

async function declineInvitation(invitationId: number) {
  if (submitting.value) return
  submitting.value = true
  const response = await PostAPI<CampaignInvitationDto>(
    `campaign-invitations/${invitationId}/decline`, {},
  )
  submitting.value = false
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  message.value = `Invitation to ${response.campaignName} declined.`
  await loadPending()
}

onBeforeMount(() => {
  takeInvitationToken()
  void loadPending()
})
let refreshTimer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  refreshTimer = setInterval(() => {
    if (!submitting.value && document.visibilityState === "visible") void loadPending()
  }, 15_000)
})
onBeforeUnmount(() => clearInterval(refreshTimer))
</script>

<template>
  <div class="account-page">
    <section class="auth-card invitation-card">
      <h1>Campaign invitations</h1>
      <p>Accept or decline the campaigns you have been invited to join.</p>
      <button v-if="token" type="button" :disabled="submitting" @click="acceptInvitation()">
        Accept linked invitation
      </button>

      <p v-if="message" class="invitation-message" role="status">
        {{ message }}
      </p>

      <RouterLink
        v-if="acceptedCampaignId"
        class="button-link"
        to="/dashboard"
      >
        Open campaign
      </RouterLink>

      <div class="pending-invitations">
        <h2>Pending for your account</h2>
        <ul v-if="pending.length">
          <li v-for="invitation in pending" :key="invitation.id">
            <strong>{{ invitation.campaignName }}</strong>
            <span>{{ invitation.role }} access</span>
            <div class="invitation-actions">
              <button type="button" :disabled="submitting" @click="acceptInvitation(invitation.id)">Accept</button>
              <button type="button" class="secondary" :disabled="submitting" @click="declineInvitation(invitation.id)">Decline</button>
            </div>
          </li>
        </ul>
        <p v-else class="empty-text">No pending campaign invitations.</p>
      </div>

    </section>
  </div>
</template>

<style scoped>
.account-page {
  display: grid;
  justify-items: center;
}

.invitation-card {
  width: min(100%, 42rem);
  background: rgba(255, 255, 255, 0.035);
}

.invitation-message {
  color: var(--color-accent-soft);
}

.pending-invitations {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--color-border);
}

.pending-invitations h2 {
  font-size: 1.1rem;
}

.pending-invitations ul {
  display: grid;
  gap: 0.5rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.pending-invitations li {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.75rem;
  border-radius: 0.5rem;
  background: rgba(0, 0, 0, 0.16);
}

.pending-invitations span {
  color: var(--color-text-muted);
  text-transform: capitalize;
}

.invitation-actions {
  display: flex;
  gap: 0.5rem;
  margin-left: auto;
}
</style>
