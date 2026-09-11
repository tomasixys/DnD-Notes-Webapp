<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import { GetAPI, isApiFailure, PostAPI, PutAPI } from "@/apihelpers"
import { useAuthStore } from "@/stores/authStore"
import type {
  AdminIssueDto,
  IssueStatus,
  KnownIssueDto,
  UserIssueDto,
} from "@/types/DataTransferObjects"

const auth = useAuthStore()
const knownIssues = ref<KnownIssueDto[]>([])
const myReports = ref<UserIssueDto[]>([])
const adminReports = ref<AdminIssueDto[]>([])
const moderationStatuses = ref<Record<number, IssueStatus>>({})
const moderationNotes = ref<Record<number, string>>({})
const title = ref("")
const description = ref("")
const message = ref("")
const loading = ref(true)
const submitting = ref(false)
const savingReportId = ref<number | null>(null)

const isAdmin = computed(() => auth.user.value?.systemRole === "admin")

const statusLabels: Record<IssueStatus, string> = {
  pending: "Pending review",
  acknowledged: "Acknowledged",
  resolved: "Resolved",
  rejected: "Not accepted",
}

function formatDate(value: string): string {
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/.test(value)
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(hasTimezone ? value : `${value}Z`))
}

function setAdminReports(reports: AdminIssueDto[]) {
  adminReports.value = reports
  for (const report of reports) {
    moderationStatuses.value[report.id] = report.status
    moderationNotes.value[report.id] = report.reviewNote
  }
}

async function loadKnownIssues() {
  const response = await GetAPI<KnownIssueDto[]>("issues/known")
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  knownIssues.value = response
}

async function loadMyReports() {
  const response = await GetAPI<UserIssueDto[]>("issues/mine")
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  myReports.value = response
}

async function loadAdminReports() {
  if (!isAdmin.value) return
  const response = await GetAPI<AdminIssueDto[]>("issues/admin")
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  setAdminReports(response)
}

async function loadIssues() {
  loading.value = true
  await Promise.all([
    loadKnownIssues(),
    loadMyReports(),
    loadAdminReports(),
  ])
  loading.value = false
}

async function submitIssue() {
  if (submitting.value) return
  submitting.value = true
  message.value = ""
  const response = await PostAPI<UserIssueDto>("issues", {
    title: title.value,
    description: description.value,
  })
  submitting.value = false
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  title.value = ""
  description.value = ""
  message.value = "Issue submitted for administrator review."
  await Promise.all([loadMyReports(), loadAdminReports()])
}

async function saveModeration(report: AdminIssueDto) {
  if (savingReportId.value !== null) return
  savingReportId.value = report.id
  message.value = ""
  const response = await PutAPI<AdminIssueDto>(
    `issues/admin/${report.id}`,
    {
      status: moderationStatuses.value[report.id],
      reviewNote: moderationNotes.value[report.id] ?? "",
    },
  )
  savingReportId.value = null
  if (isApiFailure(response)) {
    message.value = response.message
    return
  }
  message.value = "Issue review saved."
  await Promise.all([
    loadKnownIssues(),
    loadMyReports(),
    loadAdminReports(),
  ])
}

onMounted(loadIssues)
</script>

<template>
  <section class="issues-page">
    <header class="issues-header">
      <p class="eyebrow">Support and transparency</p>
      <h1>Known issues</h1>
      <p>
        Review acknowledged problems or report something that is not working
        as expected.
      </p>
    </header>

    <p v-if="message" class="form-success" role="status">{{ message }}</p>
    <p v-if="loading" class="empty-text">Loading issue reports…</p>

    <div v-else class="issues-overview">
      <section class="issue-section information-card">
        <div class="section-heading">
          <div>
            <h2>Acknowledged issues</h2>
            <p>Verified reports currently visible to all users.</p>
          </div>
          <span class="count-badge">{{ knownIssues.length }}</span>
        </div>

        <div v-if="knownIssues.length" class="issue-list">
          <article
            v-for="issue in knownIssues"
            :key="issue.id"
            class="issue-card"
          >
            <div class="issue-card-heading">
              <h3>{{ issue.title }}</h3>
              <span>Acknowledged {{ formatDate(issue.acknowledgedAt) }}</span>
            </div>
            <p>{{ issue.description }}</p>
          </article>
        </div>
        <p v-else class="empty-text">There are no acknowledged issues.</p>
      </section>

      <section class="issue-section information-card">
        <h2>Report an issue</h2>
        <p>
          Your report remains private until an administrator acknowledges it.
        </p>
        <form class="issue-form" @submit.prevent="submitIssue">
          <label>
            Short title
            <input
              v-model="title"
              required
              minlength="3"
              maxlength="160"
              placeholder="What is not working?"
            />
          </label>
          <label>
            What happened?
            <textarea
              v-model="description"
              required
              minlength="10"
              maxlength="5000"
              rows="7"
              placeholder="Describe what you expected, what happened, and how to reproduce it."
            />
          </label>
          <button type="submit" :disabled="submitting">
            {{ submitting ? "Submitting…" : "Submit for review" }}
          </button>
        </form>
      </section>
    </div>

    <section v-if="!loading" class="issue-section information-card">
      <div class="section-heading">
        <div>
          <h2>Your reports</h2>
          <p>Only you and administrators can see reports awaiting review.</p>
        </div>
        <span class="count-badge">{{ myReports.length }}</span>
      </div>
      <div v-if="myReports.length" class="issue-list compact-list">
        <article
          v-for="report in myReports"
          :key="report.id"
          class="issue-card"
        >
          <div class="issue-card-heading">
            <h3>{{ report.title }}</h3>
            <span class="status-badge" :data-status="report.status">
              {{ statusLabels[report.status] }}
            </span>
          </div>
          <p>{{ report.description }}</p>
          <p v-if="report.reviewNote" class="review-note">
            <strong>Administrator note:</strong> {{ report.reviewNote }}
          </p>
          <small>Submitted {{ formatDate(report.createdAt) }}</small>
        </article>
      </div>
      <p v-else class="empty-text">You have not submitted any issues.</p>
    </section>

    <section
      v-if="!loading && isAdmin"
      class="issue-section information-card moderation-section"
    >
      <div class="section-heading">
        <div>
          <p class="eyebrow">Administrator</p>
          <h2>Issue moderation</h2>
          <p>Acknowledged reports become visible to every signed-in user.</p>
        </div>
        <span class="count-badge">{{ adminReports.length }}</span>
      </div>

      <div v-if="adminReports.length" class="moderation-list">
        <article
          v-for="report in adminReports"
          :key="report.id"
          class="moderation-card"
        >
          <div class="issue-card-heading">
            <div>
              <h3>{{ report.title }}</h3>
              <span>
                {{ report.reporterDisplayName }}
                · @{{ report.reporterUsername }}
                · {{ formatDate(report.createdAt) }}
              </span>
            </div>
            <span class="status-badge" :data-status="report.status">
              {{ statusLabels[report.status] }}
            </span>
          </div>
          <p>{{ report.description }}</p>
          <div class="moderation-controls">
            <label>
              Status
              <select v-model="moderationStatuses[report.id]">
                <option value="pending">Pending (private)</option>
                <option value="acknowledged">Acknowledged (public)</option>
                <option value="resolved">Resolved</option>
                <option value="rejected">Not accepted</option>
              </select>
            </label>
            <label class="moderation-note">
              Note to reporter
              <textarea
                v-model="moderationNotes[report.id]"
                maxlength="1000"
                rows="2"
                placeholder="Optional review or resolution note"
              />
            </label>
            <button
              type="button"
              :disabled="savingReportId !== null"
              @click="saveModeration(report)"
            >
              {{ savingReportId === report.id ? "Saving…" : "Save review" }}
            </button>
          </div>
        </article>
      </div>
      <p v-else class="empty-text">No issue reports require moderation.</p>
    </section>
  </section>
</template>

<style scoped>
.issues-page {
  width: min(100%, 78rem);
  margin: 0 auto;
}

.issues-header {
  margin-bottom: 1rem;
}

.issues-header h1,
.issues-header p,
.issue-section h2,
.issue-section p {
  margin-top: 0;
}

.eyebrow {
  margin-bottom: 0.25rem;
  color: var(--color-accent-soft);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
}

.issues-overview {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(18rem, 0.65fr);
  gap: 1rem;
}

.information-card {
  padding: clamp(1rem, 2vw, 1.5rem);
  border: 1px solid var(--color-border);
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.035);
}

.issue-section + .issue-section,
.issues-overview + .issue-section {
  margin-top: 1rem;
}

.issues-overview .issue-section + .issue-section {
  margin-top: 0;
}

.section-heading,
.issue-card-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.section-heading h2,
.issue-card-heading h3 {
  margin: 0;
}

.section-heading p,
.issue-card-heading span,
.issue-card small {
  color: var(--color-text-muted);
}

.count-badge,
.status-badge {
  flex: 0 0 auto;
  padding: 0.2rem 0.55rem;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  color: var(--color-text-muted);
  font-size: 0.78rem;
}

.status-badge[data-status="acknowledged"] {
  border-color: var(--color-accent-dark);
  color: var(--color-accent-soft);
}

.status-badge[data-status="resolved"] {
  color: #9dcc9d;
}

.status-badge[data-status="rejected"] {
  color: #d3a29b;
}

.issue-list,
.moderation-list,
.issue-form {
  display: grid;
  gap: 0.75rem;
  margin-top: 1rem;
}

.issue-card,
.moderation-card {
  padding: 1rem;
  border: 1px solid var(--color-border);
  border-radius: 0.75rem;
  background: rgba(0, 0, 0, 0.14);
}

.issue-card p,
.moderation-card > p {
  margin: 0.65rem 0 0;
  line-height: 1.55;
  white-space: pre-wrap;
}

.compact-list {
  grid-template-columns: repeat(auto-fit, minmax(min(22rem, 100%), 1fr));
}

.review-note {
  padding: 0.75rem;
  border-left: 3px solid var(--color-accent-dark);
  background: rgba(201, 137, 63, 0.08);
}

.issue-form label,
.moderation-controls label {
  display: grid;
  gap: 0.35rem;
}

.issue-form button {
  justify-self: start;
}

.moderation-controls {
  display: grid;
  grid-template-columns: minmax(11rem, 0.35fr) minmax(16rem, 1fr) auto;
  gap: 0.75rem;
  align-items: end;
  margin-top: 1rem;
}

.moderation-controls button {
  white-space: nowrap;
}

@media (max-width: 850px) {
  .issues-overview,
  .moderation-controls {
    grid-template-columns: 1fr;
  }

  .moderation-controls button {
    justify-self: start;
  }
}

@media (max-width: 550px) {
  .section-heading,
  .issue-card-heading {
    flex-direction: column;
  }
}
</style>
