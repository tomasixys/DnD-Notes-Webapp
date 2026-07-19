<script setup lang="ts">
import { ref, computed, onBeforeMount } from "vue"
import { GetAPI, PutAPI } from "@/apihelpers"
import { useCampaignStore } from "@/stores/campaignStore"

interface CoinEntry {
  value: number
  type: "cp" | "sp" | "ep" | "gp" | "pp"
}

interface LootItem {
  id?: number
  name: string
  desc: string
  value: CoinEntry
}

const COIN_MULTIPLIER_TO_GP = {
  cp: 0.01,
  sp: 0.1,
  ep: 0.5,
  gp: 1.0,
  pp: 10.0,
}

const { selectedCampaignId, selectedCampaign } = useCampaignStore()

// Local counts for vault cards
const coins = ref({
  cp: 0,
  sp: 0,
  ep: 0,
  gp: 0,
  pp: 0,
})

const loot = ref<LootItem[]>([])

// Loading & Saving state
const isLoading = ref(true)
const isSaving = ref(false)
const saveStatus = ref<"idle" | "saving" | "success" | "error">("idle")

// Inline form for adding new loot item
const newLootName = ref("")
const newLootDesc = ref("")
const newLootValue = ref<number | null>(null)
const newLootType = ref<"cp" | "sp" | "ep" | "gp" | "pp">("gp")

// Computed values
const totalCoinsGold = computed(() => {
  return (
    coins.value.cp * COIN_MULTIPLIER_TO_GP.cp +
    coins.value.sp * COIN_MULTIPLIER_TO_GP.sp +
    coins.value.ep * COIN_MULTIPLIER_TO_GP.ep +
    coins.value.gp * COIN_MULTIPLIER_TO_GP.gp +
    coins.value.pp * COIN_MULTIPLIER_TO_GP.pp
  )
})

const totalLootGold = computed(() => {
  return loot.value.reduce((sum, item) => {
    const coinValue = Number(item.value.value) || 0
    const coinType = item.value.type
    const multiplier = COIN_MULTIPLIER_TO_GP[coinType] || 0
    return sum + coinValue * multiplier
  }, 0)
})

const grandTotalGold = computed(() => {
  return totalCoinsGold.value + totalLootGold.value
})

async function fetchStash() {
  if (!selectedCampaignId.value) return

  isLoading.value = true
  const response = await GetAPI(`campaigns/${selectedCampaignId.value}/party/stash`)

  if (response && response.success !== false) {
    const rawStash = response as any
    const rawCoins = rawStash.wealth?.coins || []

    // Reset counts
    coins.value = { cp: 0, sp: 0, ep: 0, gp: 0, pp: 0 }

    // Map counts from list
    for (const coin of rawCoins) {
      const type = coin.type as keyof typeof coins.value
      if (type in coins.value) {
        coins.value[type] = coin.value
      }
    }

    loot.value = rawStash.loot || []
  } else {
    console.error("Failed to load stash data.")
  }
  isLoading.value = false
}

async function saveStash() {
  if (!selectedCampaignId.value) return

  isSaving.value = true
  saveStatus.value = "saving"

  // Construct wealth coins payload
  const coinsPayload = Object.entries(coins.value).map(([type, value]) => ({
    value,
    type,
  }))

  const payload = {
    wealth: {
      coins: coinsPayload,
      total_value: {
        value: totalCoinsGold.value,
        type: "gp",
      },
    },
    loot: loot.value.map((item) => ({
      name: item.name,
      desc: item.desc,
      value: {
        value: item.value.value,
        type: item.value.type,
      },
    })),
  }

  const response = await PutAPI(`campaigns/${selectedCampaignId.value}/party/stash`, payload)

  if (response && response.success !== false) {
    saveStatus.value = "success"
    setTimeout(() => {
      saveStatus.value = "idle"
    }, 3000)
  } else {
    saveStatus.value = "error"
    console.error("Failed to save stash:", response)
  }
  isSaving.value = false
}

function adjustCoin(coinKey: keyof typeof coins.value, amount: number) {
  coins.value[coinKey] = Math.max(0, coins.value[coinKey] + amount)
}

function addLootItem() {
  if (!newLootName.value.trim()) return

  loot.value.push({
    name: newLootName.value.trim(),
    desc: newLootDesc.value.trim(),
    value: {
      value: newLootValue.value || 0,
      type: newLootType.value,
    },
  })

  // Clear inputs
  newLootName.value = ""
  newLootDesc.value = ""
  newLootValue.value = null
  newLootType.value = "gp"

  // Directly save to database
  saveStash()
}

function removeLootItem(index: number) {
  loot.value.splice(index, 1)

  // Directly save to database
  saveStash()
}

onBeforeMount(async () => {
  await fetchStash()
})
</script>

<template>
  <section class="resource-view stash-view-container">
    <header class="view-header with-actions">
      <div class="view-header-copy">
        <h2>Party Stash</h2>
        <p>Track the shared treasury, currency balances, and custom loot items for <strong>{{ selectedCampaign?.name }}</strong>.</p>
      </div>

      <div class="header-actions">
        <button
          type="button"
          class="save-button"
          :class="{
            'saving': saveStatus === 'saving',
            'success': saveStatus === 'success',
            'error': saveStatus === 'error'
          }"
          :disabled="isSaving"
          @click="saveStash"
        >
          <span v-if="saveStatus === 'idle'">Save Stash</span>
          <span v-else-if="saveStatus === 'saving'">Saving...</span>
          <span v-else-if="saveStatus === 'success'">✓ Stash Saved!</span>
          <span v-else-if="saveStatus === 'error'">⚠ Save Failed</span>
        </button>
      </div>
    </header>

    <div v-if="isLoading" class="loading-state">
      <div class="spinner"></div>
      <p>Unlocking the party vault...</p>
    </div>

    <div v-else class="stash-layout">
      <!-- Top Row: Summary Cards -->
      <div class="summary-cards">
        <div class="summary-card gold-glowing">
          <div class="summary-icon">🪙</div>
          <div class="summary-info">
            <span class="summary-label">Grand Total Value</span>
            <span class="summary-value">{{ grandTotalGold.toFixed(2) }} gp</span>
          </div>
        </div>

        <div class="summary-card">
          <div class="summary-icon">👛</div>
          <div class="summary-info">
            <span class="summary-label">Total in Coins</span>
            <span class="summary-value">{{ totalCoinsGold.toFixed(2) }} gp</span>
          </div>
        </div>

        <div class="summary-card">
          <div class="summary-icon">💎</div>
          <div class="summary-info">
            <span class="summary-label">Total in Loot</span>
            <span class="summary-value">{{ totalLootGold.toFixed(2) }} gp</span>
          </div>
        </div>
      </div>

      <div class="stash-grid">
        <!-- Left Panel: Coins Chest -->
        <div class="vault-panel card-panel">
          <div class="panel-header">
            <h3>Coin Vault</h3>
            <p class="panel-subtitle">Edit quantities and verify real-time gold value conversions</p>
          </div>

          <div class="coins-grid">
            <!-- Copper Card -->
            <div class="coin-card copper-theme">
              <div class="coin-header">
                <div class="coin-badge">CP</div>
                <span class="coin-name-label">Copper Pieces</span>
              </div>
              <div class="coin-controls">
                <button type="button" class="adjust-btn" @click="adjustCoin('cp', -10)">-10</button>
                <button type="button" class="adjust-btn" @click="adjustCoin('cp', -1)">-1</button>
                <input
                  v-model.number="coins.cp"
                  type="number"
                  min="0"
                  class="coin-value-input"
                />
                <button type="button" class="adjust-btn" @click="adjustCoin('cp', 1)">+1</button>
                <button type="button" class="adjust-btn" @click="adjustCoin('cp', 10)">+10</button>
              </div>
              <div class="coin-meta">
                <div class="meta-row gold-val">
                  <span>Gold Value (1/100 GP):</span>
                  <span>{{ (coins.cp * COIN_MULTIPLIER_TO_GP.cp).toFixed(2) }} gp</span>
                </div>
              </div>
            </div>

            <!-- Silver Card -->
            <div class="coin-card silver-theme">
              <div class="coin-header">
                <div class="coin-badge">SP</div>
                <span class="coin-name-label">Silver Pieces</span>
              </div>
              <div class="coin-controls">
                <button type="button" class="adjust-btn" @click="adjustCoin('sp', -10)">-10</button>
                <button type="button" class="adjust-btn" @click="adjustCoin('sp', -1)">-1</button>
                <input
                  v-model.number="coins.sp"
                  type="number"
                  min="0"
                  class="coin-value-input"
                />
                <button type="button" class="adjust-btn" @click="adjustCoin('sp', 1)">+1</button>
                <button type="button" class="adjust-btn" @click="adjustCoin('sp', 10)">+10</button>
              </div>
              <div class="coin-meta">
                <div class="meta-row gold-val">
                  <span>Gold Value (1/10 GP):</span>
                  <span>{{ (coins.sp * COIN_MULTIPLIER_TO_GP.sp).toFixed(2) }} gp</span>
                </div>
              </div>
            </div>

            <!-- Electrum Card -->
            <div class="coin-card electrum-theme">
              <div class="coin-header">
                <div class="coin-badge">EP</div>
                <span class="coin-name-label">Electrum Pieces</span>
              </div>
              <div class="coin-controls">
                <button type="button" class="adjust-btn" @click="adjustCoin('ep', -10)">-10</button>
                <button type="button" class="adjust-btn" @click="adjustCoin('ep', -1)">-1</button>
                <input
                  v-model.number="coins.ep"
                  type="number"
                  min="0"
                  class="coin-value-input"
                />
                <button type="button" class="adjust-btn" @click="adjustCoin('ep', 1)">+1</button>
                <button type="button" class="adjust-btn" @click="adjustCoin('ep', 10)">+10</button>
              </div>
              <div class="coin-meta">
                <div class="meta-row gold-val">
                  <span>Gold Value (1/2 GP):</span>
                  <span>{{ (coins.ep * COIN_MULTIPLIER_TO_GP.ep).toFixed(2) }} gp</span>
                </div>
              </div>
            </div>

            <!-- Gold Card -->
            <div class="coin-card gold-theme">
              <div class="coin-header">
                <div class="coin-badge">GP</div>
                <span class="coin-name-label">Gold Pieces</span>
              </div>
              <div class="coin-controls">
                <button type="button" class="adjust-btn" @click="adjustCoin('gp', -10)">-10</button>
                <button type="button" class="adjust-btn" @click="adjustCoin('gp', -1)">-1</button>
                <input
                  v-model.number="coins.gp"
                  type="number"
                  min="0"
                  class="coin-value-input"
                />
                <button type="button" class="adjust-btn" @click="adjustCoin('gp', 1)">+1</button>
                <button type="button" class="adjust-btn" @click="adjustCoin('gp', 10)">+10</button>
              </div>
              <div class="coin-meta">
                <div class="meta-row gold-val">
                  <span>Gold Value (1 GP):</span>
                  <span>{{ (coins.gp * COIN_MULTIPLIER_TO_GP.gp).toFixed(2) }} gp</span>
                </div>
              </div>
            </div>

            <!-- Platinum Card -->
            <div class="coin-card platinum-theme">
              <div class="coin-header">
                <div class="coin-badge">PP</div>
                <span class="coin-name-label">Platinum Pieces</span>
              </div>
              <div class="coin-controls">
                <button type="button" class="adjust-btn" @click="adjustCoin('pp', -10)">-10</button>
                <button type="button" class="adjust-btn" @click="adjustCoin('pp', -1)">-1</button>
                <input
                  v-model.number="coins.pp"
                  type="number"
                  min="0"
                  class="coin-value-input"
                />
                <button type="button" class="adjust-btn" @click="adjustCoin('pp', 1)">+1</button>
                <button type="button" class="adjust-btn" @click="adjustCoin('pp', 10)">+10</button>
              </div>
              <div class="coin-meta">
                <div class="meta-row gold-val">
                  <span>Gold Value (10 GP):</span>
                  <span>{{ (coins.pp * COIN_MULTIPLIER_TO_GP.pp).toFixed(2) }} gp</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Right Panel: Loot Bag -->
        <div class="loot-panel card-panel">
          <div class="panel-header">
            <h3>Loot Inventory</h3>
            <p class="panel-subtitle">Catalog art objects, gems, and specialized items</p>
          </div>

          <!-- Add Loot Form -->
          <form class="add-loot-form" @submit.prevent="addLootItem">
            <div class="form-row">
              <div class="input-group name-group">
                <label for="loot-name">Item Name</label>
                <input
                  id="loot-name"
                  v-model="newLootName"
                  type="text"
                  placeholder="e.g. Sapphire Necklace"
                  required
                />
              </div>
              <div class="input-group val-input-group">
                <label for="loot-value">Value</label>
                <input
                  id="loot-value"
                  v-model.number="newLootValue"
                  type="number"
                  min="0"
                  placeholder="0"
                  required
                />
              </div>
              <div class="input-group type-input-group">
                <label for="loot-type">Denomination</label>
                <select id="loot-type" v-model="newLootType">
                  <option value="cp">cp</option>
                  <option value="sp">sp</option>
                  <option value="ep">ep</option>
                  <option value="gp">gp</option>
                  <option value="pp">pp</option>
                </select>
              </div>
            </div>
            <div class="input-group desc-group">
              <label for="loot-desc">Description</label>
              <textarea
                id="loot-desc"
                v-model="newLootDesc"
                rows="2"
                placeholder="Describe the item's details..."
              ></textarea>
            </div>
            <button type="submit" class="add-item-btn">Add to Loot</button>
          </form>

          <!-- Loot List -->
          <div class="loot-list-container">
            <ul v-if="loot.length > 0" class="loot-list">
              <transition-group name="loot-fade">
                <li v-for="(item, index) in loot" :key="index" class="loot-item">
                  <div class="loot-item-details">
                    <div class="loot-item-header">
                      <span class="loot-item-name">{{ item.name }}</span>
                      <span class="loot-item-value">
                        {{ item.value.value }} {{ item.value.type }}
                        <span class="loot-converted-value">
                          ({{ (item.value.value * COIN_MULTIPLIER_TO_GP[item.value.type]).toFixed(2) }} gp)
                        </span>
                      </span>
                    </div>
                    <p v-if="item.desc" class="loot-item-desc">{{ item.desc }}</p>
                  </div>
                  <button
                    type="button"
                    class="remove-loot-btn"
                    title="Remove item"
                    @click="removeLootItem(index)"
                  >
                    🗑
                  </button>
                </li>
              </transition-group>
            </ul>
            <p v-else class="empty-loot-text">No items in the loot bag yet.</p>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.stash-view-container {
  padding: 1.5rem clamp(1rem, 2vw, 2rem);
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 5rem 0;
  gap: 1.5rem;
  color: var(--color-text-muted);
}

.spinner {
  width: 3rem;
  height: 3rem;
  border: 4px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.save-button {
  background: var(--color-accent-dark);
  color: #fff;
  border: 1px solid var(--color-accent);
  padding: 0.6rem 1.5rem;
  font-weight: 600;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
}

.save-button:hover:not(:disabled) {
  background: var(--color-accent);
  transform: translateY(-1px);
  box-shadow: 0 6px 12px rgba(201, 137, 63, 0.3);
}

.save-button.saving {
  background: var(--color-bg-soft);
  border-color: var(--color-border);
  color: var(--color-text-muted);
  cursor: not-allowed;
}

.save-button.success {
  background: #2e7d32;
  border-color: #4caf50;
  color: #fff;
}

.save-button.error {
  background: #c62828;
  border-color: #ef5350;
  color: #fff;
}

.stash-layout {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  width: 100%;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1rem;
}

.summary-card {
  background: var(--color-bg-panel);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 1.25rem;
  display: flex;
  align-items: center;
  gap: 1.25rem;
  box-shadow: var(--shadow-soft);
  transition: border-color 0.2s ease;
}

.summary-card:hover {
  border-color: var(--color-accent-soft);
}

.summary-card.gold-glowing {
  background: radial-gradient(circle at center, rgba(201, 137, 63, 0.15), transparent), var(--color-bg-panel);
  border-color: var(--color-accent);
  box-shadow: 0 0 15px rgba(201, 137, 63, 0.25);
}

.summary-icon {
  font-size: 2.25rem;
  filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5));
}

.summary-info {
  display: flex;
  flex-direction: column;
}

.summary-label {
  font-size: 0.85rem;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.summary-value {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--color-text);
  margin-top: 0.15rem;
}

.gold-glowing .summary-value {
  color: var(--color-accent-soft);
}

.stash-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

@media (max-width: 1024px) {
  .stash-grid {
    grid-template-columns: 1fr;
  }
}

.card-panel {
  background: var(--color-bg-panel);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  box-shadow: var(--shadow-soft);
}

.panel-header {
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding-bottom: 0.75rem;
}

.panel-header h3 {
  margin: 0;
  font-size: 1.3rem;
  color: var(--color-text);
}

.panel-subtitle {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
  color: var(--color-text-muted);
}

.coins-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}

.coin-card {
  border-radius: 6px;
  padding: 1rem 1.25rem;
  border-left: 5px solid transparent;
  background: var(--color-bg-soft);
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  transition: all 0.2s ease;
}

.coin-card:hover {
  transform: translateX(2px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.25);
}

.copper-theme {
  border-left-color: #c87533;
}
.copper-theme .coin-badge {
  background: #c87533;
  color: #fff;
}

.silver-theme {
  border-left-color: #b0c4de;
}
.silver-theme .coin-badge {
  background: #809bb0;
  color: #fff;
}

.electrum-theme {
  border-left-color: #7f9e07;
}
.electrum-theme .coin-badge {
  background: #7f9e07;
  color: #fff;
}

.gold-theme {
  border-left-color: var(--color-accent);
}
.gold-theme .coin-badge {
  background: var(--color-accent);
  color: #fff;
}

.platinum-theme {
  border-left-color: #e5e4e2;
}
.platinum-theme .coin-badge {
  background: #a3a6ad;
  color: #fff;
}

.coin-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.coin-badge {
  font-weight: 800;
  font-size: 0.75rem;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  letter-spacing: 0.05em;
  text-shadow: 0 1px 1px rgba(0,0,0,0.3);
}

.coin-name-label {
  font-weight: 600;
  color: var(--color-text);
  font-size: 1rem;
}

.coin-controls {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.adjust-btn {
  background: var(--color-bg-panel);
  border: 1px solid var(--color-border);
  color: var(--color-text);
  padding: 0.35rem 0.6rem;
  font-size: 0.85rem;
  border-radius: 4px;
  min-width: 2.25rem;
  transition: all 0.15s ease;
}

.adjust-btn:hover {
  background: var(--color-accent-dark);
  border-color: var(--color-accent);
}

.coin-value-input {
  flex: 1;
  background: var(--color-bg-panel);
  border: 1px solid var(--color-border);
  color: #fff;
  padding: 0.35rem 0.5rem;
  text-align: center;
  font-weight: 700;
  font-size: 1.15rem;
  border-radius: 4px;
}

.coin-value-input::-webkit-outer-spin-button,
.coin-value-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.coin-value-input[type=number] {
  -moz-appearance: textfield;
}

.coin-meta {
  border-top: 1px solid rgba(255,255,255,0.04);
  padding-top: 0.6rem;
  font-size: 0.85rem;
  color: var(--color-text-muted);
}

.meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.gold-val {
  font-weight: 600;
}
.gold-val span:last-child {
  color: var(--color-accent-soft);
}

.add-loot-form {
  background: var(--color-bg-soft);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.form-row {
  display: flex;
  gap: 0.75rem;
  align-items: flex-end;
}

@media (max-width: 480px) {
  .form-row {
    flex-direction: column;
    align-items: stretch;
  }
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.name-group {
  flex: 3;
}

.val-input-group {
  flex: 1.5;
}

.type-input-group {
  flex: 1.5;
}

.desc-group {
  width: 100%;
}

.input-group label {
  font-size: 0.75rem;
  text-transform: uppercase;
  color: var(--color-text-muted);
  letter-spacing: 0.05em;
  font-weight: 600;
}

.input-group input, .input-group textarea, .input-group select {
  background: var(--color-bg-panel);
  border: 1px solid var(--color-border);
  color: var(--color-text);
  padding: 0.5rem 0.65rem;
  border-radius: 4px;
  font-size: 0.9rem;
}

.input-group input:focus, .input-group textarea:focus, .input-group select:focus {
  border-color: var(--color-accent);
  outline: none;
}

.add-item-btn {
  background: var(--color-accent-dark);
  color: #fff;
  border: 1px solid var(--color-accent);
  padding: 0.5rem 1rem;
  font-weight: 600;
  border-radius: 4px;
  cursor: pointer;
  align-self: flex-end;
  transition: all 0.2s ease;
}

.add-item-btn:hover {
  background: var(--color-accent);
}

.loot-list-container {
  display: flex;
  flex-direction: column;
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 6px;
}

.loot-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.loot-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 0.85rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  background: var(--color-bg-soft);
  transition: all 0.15s ease;
  gap: 1rem;
}

.loot-item:last-child {
  border-bottom: none;
}

.loot-item:hover {
  background: rgba(255, 255, 255, 0.02);
}

.loot-item-details {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.loot-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.loot-item-name {
  font-weight: 600;
  color: var(--color-text);
  font-size: 0.95rem;
}

.loot-item-value {
  font-weight: 700;
  color: var(--color-accent-soft);
  font-size: 0.9rem;
}

.loot-converted-value {
  font-weight: 400;
  font-size: 0.8rem;
  color: var(--color-text-muted);
  margin-left: 0.25rem;
}

.loot-item-desc {
  margin: 0.25rem 0 0;
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

.remove-loot-btn {
  background: transparent;
  border: none;
  color: var(--color-text-muted);
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 4px;
  transition: all 0.15s ease;
  line-height: 1;
}

.remove-loot-btn:hover {
  color: #ef5350;
  background: rgba(239, 83, 80, 0.1);
}

.empty-loot-text {
  text-align: center;
  padding: 2rem;
  color: var(--color-text-muted);
  font-style: italic;
  font-size: 0.9rem;
  margin: 0;
}

/* Animations */
.loot-fade-enter-active, .loot-fade-leave-active {
  transition: all 0.25s ease;
}

.loot-fade-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}

.loot-fade-leave-to {
  opacity: 0;
  transform: translateY(10px);
}
</style>
