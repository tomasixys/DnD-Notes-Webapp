<script setup lang="ts">
import { onMounted } from "vue"

import changelogSource from "../../../CHANGELOG.md?raw"
import { useAccountNotificationStore } from "@/stores/accountNotificationStore"

type ChangeGroup = {
  heading: string
  items: string[]
}

type Release = {
  heading: string
  groups: ChangeGroup[]
}

function plainMarkdown(value: string): string {
  return value
    .replace(/\[([^\]]+)]\([^)]+\)/g, "$1")
    .replace(/\[([^\]]+)]/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
}

function parseChangelog(source: string): Release[] {
  const releases: Release[] = []
  let release: Release | null = null
  let group: ChangeGroup | null = null

  for (const sourceLine of source.split(/\r?\n/)) {
    const line = sourceLine.trim()
    if (line.startsWith("## ")) {
      release = {
        heading: plainMarkdown(line.slice(3)),
        groups: [],
      }
      releases.push(release)
      group = null
      continue
    }
    if (release && line.startsWith("### ")) {
      group = {
        heading: plainMarkdown(line.slice(4)),
        items: [],
      }
      release.groups.push(group)
      continue
    }
    if (group && line.startsWith("- ")) {
      group.items.push(plainMarkdown(line.slice(2)))
      continue
    }
    if (group && line && group.items.length > 0) {
      const itemIndex = group.items.length - 1
      group.items[itemIndex] += ` ${plainMarkdown(line)}`
    }
  }

  return releases
}

const releases = parseChangelog(changelogSource)
const accountNotifications = useAccountNotificationStore()

onMounted(accountNotifications.markChangelogSeen)
</script>

<template>
  <section class="information-page changelog-page">
    <header class="information-header">
      <p class="eyebrow">Application updates</p>
      <h1>Changelog</h1>
      <p>New features, changes, and fixes included in DnD Notes.</p>
    </header>

    <div class="release-list">
      <article
        v-for="release in releases"
        :key="release.heading"
        class="information-card release-card"
      >
        <h2>{{ release.heading }}</h2>
        <section
          v-for="group in release.groups"
          :key="group.heading"
          class="change-group"
        >
          <h3>{{ group.heading }}</h3>
          <ul>
            <li v-for="item in group.items" :key="item">{{ item }}</li>
          </ul>
        </section>
      </article>
    </div>
  </section>
</template>

<style scoped>
.information-page {
  width: min(100%, 72rem);
  margin: 0 auto;
}

.information-header {
  margin-bottom: 1rem;
}

.information-header h1,
.information-header p {
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

.release-list {
  display: grid;
  gap: 1rem;
}

.information-card {
  padding: clamp(1rem, 2vw, 1.5rem);
  border: 1px solid var(--color-border);
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.035);
}

.release-card h2 {
  margin: 0 0 1rem;
  color: var(--color-accent-soft);
}

.change-group + .change-group {
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid var(--color-border);
}

.change-group h3 {
  margin: 0 0 0.65rem;
  font-size: 1.05rem;
}

.change-group ul {
  display: grid;
  gap: 0.5rem;
  margin: 0;
  padding-left: 1.25rem;
  color: var(--color-text-muted);
  line-height: 1.5;
}
</style>
