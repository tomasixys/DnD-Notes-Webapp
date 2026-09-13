<script setup lang="ts">
import type {
  AdminIssueDto,
  IssueStatus,
} from "@/types/DataTransferObjects"

defineProps<{
  report: AdminIssueDto
  status: IssueStatus
  note: string
  disabled: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  save: []
  "update:status": [status: IssueStatus]
  "update:note": [note: string]
}>()

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

function updateStatus(event: Event): void {
  emit(
    "update:status",
    (event.target as HTMLSelectElement).value as IssueStatus,
  )
}

function updateNote(event: Event): void {
  emit("update:note", (event.target as HTMLTextAreaElement).value)
}
</script>

<template>
  <article class="moderation-card">
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
        <select :value="status" @change="updateStatus">
          <option value="pending">Pending (private)</option>
          <option value="acknowledged">Acknowledged (public)</option>
          <option value="resolved">Resolved</option>
          <option value="rejected">Not accepted</option>
        </select>
      </label>
      <label class="moderation-note">
        Note to reporter
        <textarea
          :value="note"
          maxlength="1000"
          rows="2"
          placeholder="Optional review or resolution note"
          @input="updateNote"
        />
      </label>
      <button
        type="button"
        :disabled="disabled"
        @click="emit('save')"
      >
        {{ saving ? "Saving…" : "Save review" }}
      </button>
    </div>
  </article>
</template>

<style scoped>
.moderation-card {
  padding: 1rem;
  border: 1px solid var(--color-border);
  border-radius: 0.75rem;
  background: rgba(0, 0, 0, 0.14);
}

.issue-card-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.issue-card-heading h3 {
  margin: 0;
}

.issue-card-heading span {
  color: var(--color-text-muted);
}

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

.moderation-card > p {
  margin: 0.65rem 0 0;
  line-height: 1.55;
  white-space: pre-wrap;
}

.moderation-controls {
  display: grid;
  grid-template-columns: minmax(11rem, 0.35fr) minmax(16rem, 1fr) auto;
  gap: 0.75rem;
  align-items: end;
  margin-top: 1rem;
}

.moderation-controls label {
  display: grid;
  gap: 0.35rem;
}

.moderation-controls button {
  white-space: nowrap;
}

@media (max-width: 850px) {
  .moderation-controls {
    grid-template-columns: 1fr;
  }

  .moderation-controls button {
    justify-self: start;
  }
}

@media (max-width: 550px) {
  .issue-card-heading {
    flex-direction: column;
  }
}
</style>
