import assert from 'node:assert/strict'
import { after, before, beforeEach, test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

let server, store, campaignStore, authStore, useCampaignAuthorization
let compareByDateDescending
const originalFetch = globalThis.fetch
const key = Symbol('test-editor')
const change = { sequence: 1, resourceType: 'person', resourceId: 10, action: 'updated', revision: 2, createdAt: '' }
const editor = { campaignId: 1, resourceType: 'person', resourceId: 10, revision: 1 }
const storage = new Map()
globalThis.localStorage = {
  getItem: key => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, String(value)),
  removeItem: key => storage.delete(key),
  clear: () => storage.clear(),
}
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
  campaignStore = (await server.ssrLoadModule('/src/stores/campaignStore.ts')).useCampaignStore()
  authStore = (await server.ssrLoadModule('/src/stores/authStore.ts')).useAuthStore()
  useCampaignAuthorization = (
    await server.ssrLoadModule('/src/composables/useCampaignAuthorization.ts')
  ).useCampaignAuthorization
  compareByDateDescending = (
    await server.ssrLoadModule('/src/utils/resourceCollections.ts')
  ).compareByDateDescending
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

test('sessions sort by date with newest same-day IDs first', () => {
  const sessions = [
    { id: 3, date: '2026-01-10' },
    { id: 1, date: '2026-01-20' },
    { id: 2, date: '2026-01-20' },
  ]

  sessions.sort(compareByDateDescending)

  assert.deepEqual(sessions.map(session => session.id), [2, 1, 3])
  assert.deepEqual(
    sessions.map((session, index) => sessions.length - index),
    [3, 2, 1],
  )
})

test('deleting the assigned character restores member character creation', () => {
  campaignStore.clearUserState()
  campaignStore.setUserScope(99)
  campaignStore.setCampaigns([{
    id: 1,
    name: 'Test campaign',
    playerCharacter: 'Existing character',
    description: '',
    sessionCount: 0,
    imageUrl: '',
    bannerImageUrl: '',
    activeCharacterPersonId: 10,
    assignedCharacterPersonId: 10,
    membershipRole: 'member',
    capabilities: ['character.self_create', 'assigned_character.write'],
    revision: 1,
    updatedAt: '',
  }])
  campaignStore.selectCampaign(1)
  const { canCreateCharacter } = useCampaignAuthorization()

  assert.equal(canCreateCharacter.value, false)
  campaignStore.setCampaignActiveCharacter(1, null)

  assert.equal(campaignStore.selectedCampaign.value.activeCharacterPersonId, null)
  assert.equal(campaignStore.selectedCampaign.value.assignedCharacterPersonId, null)
  assert.equal(campaignStore.selectedCampaign.value.playerCharacter, '')
  assert.equal(canCreateCharacter.value, true)
})

test('login hydrates campaign permissions before opening a protected view', async () => {
  const requestedEndpoints = []
  globalThis.fetch = async (url) => {
    requestedEndpoints.push(String(url))
    if (String(url).endsWith('/api/auth/login')) {
      return new Response(JSON.stringify({
        user: {
          id: 101,
          username: 'member',
          display_name: 'Member',
          status: 'active',
          system_role: 'user',
        },
        csrf_token: 'test-csrf',
        authentication_required: true,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    if (String(url).endsWith('/api/campaigns')) {
      return new Response(JSON.stringify([{
        id: 3,
        name: 'Test campaign',
        player_character: '',
        description: '',
        session_count: 0,
        image_url: '',
        banner_image_url: '',
        active_character_person_id: null,
        assigned_character_person_id: null,
        membership_role: 'member',
        capabilities: ['character.self_create'],
        revision: 1,
        updated_at: '',
      }]), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    throw new Error(`Unexpected request: ${url}`)
  }

  const response = await authStore.login('member', 'test-password')
  assert.equal(response.user.username, 'member')
  assert.deepEqual(
    requestedEndpoints.map(endpoint => new URL(endpoint).pathname),
    ['/api/auth/login', '/api/campaigns'],
  )
  assert.equal(campaignStore.selectedCampaign.value.id, 3)
  const { canCreateCharacter } = useCampaignAuthorization()
  assert.equal(canCreateCharacter.value, true)
})
