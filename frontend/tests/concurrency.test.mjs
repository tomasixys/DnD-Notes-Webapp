import assert from 'node:assert/strict'
import { after, before, beforeEach, test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

let server, store
const originalFetch = globalThis.fetch
const key = Symbol('test-editor')
const change = { sequence: 1, resourceType: 'person', resourceId: 10, action: 'updated', revision: 2, createdAt: '' }
const editor = { campaignId: 1, resourceType: 'person', resourceId: 10, revision: 1 }
const respond = (changes = [], status = 200) => {
  globalThis.fetch = async () => new Response(JSON.stringify({ cursor: 1, changes }), {
    status, headers: { 'Content-Type': 'application/json' },
  })
}

before(async () => {
  server = await createServer({
    configFile: false,
    root: fileURLToPath(new URL('..', import.meta.url)),
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true, hmr: false, ws: false, watch: null },
  })
  store = (await server.ssrLoadModule('/src/stores/concurrencyStore.ts')).useConcurrencyStore()
})
after(async () => { globalThis.fetch = originalFetch; await server?.close() })
beforeEach(() => { store.resetConcurrencyState(); respond() })

test('browsing changes request a quiet refresh without a notice', async () => {
  respond([change])
  assert.equal(await store.pollCampaignChanges(1), true)
  assert.equal(store.hasNotice.value, false)
  store.refreshCurrentView(1)
  respond()
  assert.equal(await store.pollCampaignChanges(1), false)
})
test('only a newer change to the resource being edited shows a notice', async () => {
  store.setEditors(key, [editor])
  respond([{ ...change, resourceId: 11 }, { ...change, revision: 1 }])
  assert.equal(await store.pollCampaignChanges(1), false)
  assert.equal(store.hasNotice.value, false)
  respond([change])
  assert.equal(await store.pollCampaignChanges(1), false)
  assert.equal(store.hasNotice.value, true)
  assert.equal(store.remoteChanges.value.length, 1)
  store.setEditors(key, [])
  assert.equal(store.hasNotice.value, false)
  respond()
  assert.equal(await store.pollCampaignChanges(1), true)
})
test('create drafts are preserved without remote-change notices', async () => {
  store.setEditors(key, [{ ...editor, resourceId: null }])
  respond([change])
  assert.equal(await store.pollCampaignChanges(1), false)
  assert.equal(store.hasNotice.value, false)
})
test('another campaign or resource type does not trigger an editor notice', async () => {
  store.setEditors(key, [editor])
  respond([{ ...change, resourceType: 'location' }])
  await store.pollCampaignChanges(1)
  respond([change])
  await store.pollCampaignChanges(2)
  assert.equal(store.hasNotice.value, false)
})
test('deletion of the edited resource warns even with no revision', async () => {
  store.setEditors(key, [editor])
  respond([{ ...change, action: 'deleted', revision: null }])
  await store.pollCampaignChanges(1)
  assert.equal(store.hasNotice.value, true)
})
test('ordinary validation conflicts do not become synchronization notices', () => {
  store.recordConflict({ status: 409, message: 'Invitation already exists' })
  assert.equal(store.hasNotice.value, false)
})
test('session reset discards an in-flight change response', async () => {
  let finish
  globalThis.fetch = () => new Promise(resolve => { finish = resolve })
  const request = store.pollCampaignChanges(1)
  store.resetConcurrencyState()
  finish(new Response(JSON.stringify({ cursor: 1, changes: [change] })))
  assert.equal(await request, false)
  assert.equal(store.hasNotice.value, false)
})
