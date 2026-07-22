<script setup lang="ts">
import { computed, onBeforeMount, reactive, ref } from "vue"

import { DeleteAPI, GetAPI, PatchAPI, PostAPI } from "@/apihelpers"
import ConfirmationPopup from "@/components/ConfirmationPopup.vue"
import Popup from "@/components/Popup.vue"
import { useRouteEntrySelection } from "@/composables/useRouteEntrySelection"
import { useCampaignStore } from "@/stores/campaignStore"
import type {
  InventoryDto,
  InventoryItemCreateDto,
  InventoryItemDto,
  InventoryItemUpdateDto,
  PurseBalancesUpdateDto,
  PurseUpdateDto,
} from "@/types/DataTransferObjects"
import {
  currencyDenominations,
  itemCategories,
  itemRarities,
  type CurrencyDenomination,
  type ItemCategory,
  type ItemRarity,
} from "@/types/inventoryTypes"
import { ViewModes } from "@/types/viewTypes"

type PurseAction = "deposit" | "withdraw"
type InventorySort =
  | "rarity_desc"
  | "name_asc"
  | "name_desc"
  | "value_desc"
  | "value_asc"

const rarityRank: Record<ItemRarity, number> = {
  common: 1,
  uncommon: 2,
  rare: 3,
  very_rare: 4,
  legendary: 5,
  artifact: 6,
}
const displayedCurrencyDenominations: CurrencyDenomination[] = [
  ...currencyDenominations,
].reverse()

const { selectedCampaignId } = useCampaignStore()

const inventory = ref<InventoryDto | null>(null)
const loading = ref(true)
const pageError = ref("")
const formError = ref("")
const viewMode = ref<ViewModes>(ViewModes.Details)
const showPurseManager = ref(false)
const showDeleteConfirmation = ref(false)
const itemSearch = ref("")
const categoryFilter = ref<ItemCategory | "all">("all")
const itemSort = ref<InventorySort>("rarity_desc")

const items = computed(() => inventory.value?.items ?? [])

const {
  selectedEntry,
  openEntry,
  ensureDefaultEntry,
  replaceWithFirstEntry,
} = useRouteEntrySelection<InventoryItemDto>({
  entries: items,
  routeName: "Inventory",
  onRouteEntryChange: () => {
    viewMode.value = ViewModes.Details
  },
})

const filteredItems = computed(() => {
  const query = itemSearch.value.trim().toLocaleLowerCase()

  return items.value
    .filter((item) => {
      const matchesCategory =
        categoryFilter.value === "all" || item.category === categoryFilter.value
      const matchesQuery =
        !query ||
        item.name.toLocaleLowerCase().includes(query) ||
        item.description.toLocaleLowerCase().includes(query)

      return matchesCategory && matchesQuery
    })
    .sort(compareItems)
})

const totalFunds = computed(() => moneyValue(inventory.value?.purse.totalValue))
const inventoryValue = computed(() =>
  items.value.reduce(
    (total, item) => total + moneyValue(item.totalValue),
    0,
  ),
)
const totalWealth = computed(() => totalFunds.value + inventoryValue.value)
const unvaluedItemCount = computed(() =>
  items.value.filter((item) => item.totalValue === null).length,
)

const ownerNames = computed(() =>
  inventory.value?.members
    .filter((member) => member.role === "owner")
    .map((member) => member.characterName)
    .join(", ") || "No owner assigned",
)

const itemForm = reactive({
  name: "",
  description: "",
  category: "equipment" as ItemCategory,
  rarity: "" as ItemRarity | "",
  quantity: 1,
  hasValue: false,
  valueAmount: "",
  valueDenomination: "gp" as CurrencyDenomination,
})

const purseChanges = reactive<Record<CurrencyDenomination, number>>({
  cp: 0,
  sp: 0,
  ep: 0,
  gp: 0,
  pp: 0,
})

function isApiError(response: unknown): response is { success: false; message?: string } {
  return (
    typeof response === "object" &&
    response !== null &&
    "success" in response &&
    response.success === false
  )
}

function moneyValue(money: { amount: string } | null | undefined): number {
  if (!money) return 0
  const amount = Number(money.amount)
  return Number.isFinite(amount) ? amount : 0
}

function formatGold(amount: number): string {
  return `${amount.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} gp`
}

function displayName(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function compareNames(a: InventoryItemDto, b: InventoryItemDto): number {
  return a.name.localeCompare(b.name, undefined, { sensitivity: "base" })
}

function compareItemValues(
  a: InventoryItemDto,
  b: InventoryItemDto,
  direction: "asc" | "desc",
): number {
  if (a.totalValue === null) return b.totalValue === null ? compareNames(a, b) : 1
  if (b.totalValue === null) return -1

  const difference = moneyValue(a.totalValue) - moneyValue(b.totalValue)
  return (direction === "asc" ? difference : -difference) || compareNames(a, b)
}

function compareItems(a: InventoryItemDto, b: InventoryItemDto): number {
  switch (itemSort.value) {
    case "name_asc":
      return compareNames(a, b)
    case "name_desc":
      return -compareNames(a, b)
    case "value_desc":
      return compareItemValues(a, b, "desc")
    case "value_asc":
      return compareItemValues(a, b, "asc")
    default: {
      const rarityDifference =
        (b.rarity ? rarityRank[b.rarity] : 0) -
        (a.rarity ? rarityRank[a.rarity] : 0)
      return rarityDifference || compareNames(a, b)
    }
  }
}

function rarityClass(rarity: ItemRarity | null): string | null {
  return rarity ? `rarity-${rarity.replace(/_/g, "-")}` : null
}

function inventoryEndpoint(suffix = ""): string {
  return `campaigns/${selectedCampaignId.value}/inventory${suffix}`
}

async function fetchInventory() {
  if (!selectedCampaignId.value) return

  loading.value = true
  pageError.value = ""
  const response = await GetAPI(inventoryEndpoint())

  if (isApiError(response)) {
    pageError.value = response.message ?? "Could not load the inventory."
    loading.value = false
    return
  }

  inventory.value = response as InventoryDto
  loading.value = false
  await ensureDefaultEntry()
}

function resetItemForm() {
  itemForm.name = ""
  itemForm.description = ""
  itemForm.category = "equipment"
  itemForm.rarity = ""
  itemForm.quantity = 1
  itemForm.hasValue = false
  itemForm.valueAmount = ""
  itemForm.valueDenomination = "gp"
  formError.value = ""
}

function showAddItemForm() {
  resetItemForm()
  viewMode.value = ViewModes.Create
}

function showEditItemForm() {
  if (!selectedEntry.value) return

  itemForm.name = selectedEntry.value.name
  itemForm.description = selectedEntry.value.description
  itemForm.category = selectedEntry.value.category
  itemForm.rarity = selectedEntry.value.rarity ?? ""
  itemForm.quantity = selectedEntry.value.quantity
  itemForm.hasValue = selectedEntry.value.unitValue !== null
  itemForm.valueAmount = selectedEntry.value.unitValue?.amount ?? ""
  itemForm.valueDenomination =
    selectedEntry.value.unitValue?.denomination ?? "gp"
  formError.value = ""
  viewMode.value = ViewModes.Edit
}

function itemPayload(): InventoryItemCreateDto {
  return {
    name: itemForm.name.trim(),
    description: itemForm.description.trim(),
    category: itemForm.category,
    rarity: itemForm.rarity || null,
    quantity: itemForm.quantity,
    unitValue: itemForm.hasValue
      ? {
          amount: itemForm.valueAmount,
          denomination: itemForm.valueDenomination,
        }
      : null,
  }
}

async function createItem() {
  if (!selectedCampaignId.value || !itemForm.name.trim()) return

  formError.value = ""
  const existingIds = new Set(items.value.map((item) => item.id))
  const response = await PostAPI(inventoryEndpoint("/items"), itemPayload())
  if (isApiError(response)) {
    formError.value = response.message ?? "Could not add the item."
    return
  }

  inventory.value = response as InventoryDto
  const createdItem = inventory.value.items.find((item) => !existingIds.has(item.id))
  resetItemForm()
  viewMode.value = ViewModes.Details
  if (createdItem) await openEntry(createdItem.id, true)
}

async function updateItem() {
  if (!selectedEntry.value || !selectedCampaignId.value) return

  formError.value = ""
  const itemId = selectedEntry.value.id
  const payload: InventoryItemUpdateDto = itemPayload()
  const response = await PatchAPI(
    inventoryEndpoint(`/items/${itemId}`),
    payload,
  )
  if (isApiError(response)) {
    formError.value = response.message ?? "Could not update the item."
    return
  }

  inventory.value = response as InventoryDto
  resetItemForm()
  viewMode.value = ViewModes.Details
  await openEntry(itemId, true)
}

async function deleteItem() {
  if (!selectedEntry.value || !selectedCampaignId.value) return

  const response = await DeleteAPI(
    inventoryEndpoint(`/items/${selectedEntry.value.id}`),
  )
  showDeleteConfirmation.value = false
  if (isApiError(response)) {
    pageError.value = response.message ?? "Could not remove the item."
    return
  }

  inventory.value = response as InventoryDto
  viewMode.value = ViewModes.Details
  await replaceWithFirstEntry()
}

function openPurseManager() {
  for (const denomination of currencyDenominations) {
    purseChanges[denomination] = 0
  }
  formError.value = ""
  showPurseManager.value = true
}

function normalizedPurseChange(denomination: CurrencyDenomination): number {
  const value = Number(purseChanges[denomination])
  return Number.isInteger(value) && value > 0 ? value : 0
}

async function updatePurse(action: PurseAction) {
  if (!inventory.value) return

  formError.value = ""
  const balances: PurseBalancesUpdateDto = {}

  for (const denomination of currencyDenominations) {
    const change = normalizedPurseChange(denomination)
    if (change === 0) continue

    const currentAmount = inventory.value.purse.balances[denomination]
    const resultingAmount =
      action === "deposit" ? currentAmount + change : currentAmount - change
    if (resultingAmount < 0) {
      formError.value = `You cannot withdraw more ${denomination} than the purse contains.`
      return
    }
    balances[denomination] = resultingAmount
  }

  if (Object.keys(balances).length === 0) {
    formError.value = "Enter at least one currency amount."
    return
  }

  const payload: PurseUpdateDto = { balances }
  const response = await PatchAPI(inventoryEndpoint("/purse"), payload)
  if (isApiError(response)) {
    formError.value = response.message ?? "Could not update the purse."
    return
  }

  inventory.value = response as InventoryDto
  showPurseManager.value = false
}

onBeforeMount(fetchInventory)
</script>

<template>
  <section class="inventory-view">
    <p v-if="loading" class="empty-text">Loading inventory...</p>
    <p v-else-if="pageError" class="form-error">{{ pageError }}</p>

    <template v-else-if="inventory">
      <header class="inventory-header">
        <div class="inventory-heading">
          <div>
            <h2>{{ inventory.name }}</h2>
            <p>Owned by {{ ownerNames }}</p>
          </div>

          <button type="button" @click="openPurseManager">
            Manage purse
          </button>
        </div>

        <div class="wealth-summary" aria-label="Inventory value summary">
          <div>
            <span>Funds</span>
            <strong>{{ formatGold(totalFunds) }}</strong>
          </div>
          <div>
            <span>Inventory value</span>
            <strong>{{ formatGold(inventoryValue) }}</strong>
          </div>
          <div>
            <span>Total wealth</span>
            <strong>{{ formatGold(totalWealth) }}</strong>
          </div>
          <small v-if="unvaluedItemCount > 0">
            {{ unvaluedItemCount }} unvalued
            {{ unvaluedItemCount === 1 ? "item is" : "items are" }} excluded
          </small>
        </div>

        <div class="purse-strip">
          <div
            v-for="denomination in displayedCurrencyDenominations"
            :key="denomination"
            class="coin-balance"
          >
            <span>{{ denomination }}</span>
            <strong>{{ inventory.purse.balances[denomination].toLocaleString() }}</strong>
          </div>
        </div>
      </header>

      <div class="inventory-layout">
        <aside class="resource-list-panel inventory-list-panel">
          <div class="resource-list-header">
            <h3>Items</h3>
            <button type="button" @click="showAddItemForm">Add item</button>
          </div>

          <div class="inventory-filters">
            <input
              v-model="itemSearch"
              type="search"
              aria-label="Search inventory"
              placeholder="Search items..."
            />
            <select v-model="categoryFilter" aria-label="Filter by category">
              <option value="all">All categories</option>
              <option v-for="category in itemCategories" :key="category" :value="category">
                {{ displayName(category) }}
              </option>
            </select>
            <select v-model="itemSort" aria-label="Sort inventory">
              <option value="rarity_desc">Rarity: high–low</option>
              <option value="name_asc">Name: A–Z</option>
              <option value="name_desc">Name: Z–A</option>
              <option value="value_desc">Value: high–low</option>
              <option value="value_asc">Value: low–high</option>
            </select>
          </div>

          <ul v-if="filteredItems.length > 0" class="resource-list">
            <li v-for="item in filteredItems" :key="item.id">
              <button
                type="button"
                class="resource-list-item inventory-list-item"
                :class="{
                  selected:
                    viewMode === ViewModes.Details && selectedEntry?.id === item.id,
                }"
                @click="openEntry(item.id)"
              >
                <span class="item-list-meta-row">
                  <span class="item-list-meta">
                    <span>{{ displayName(item.category) }}</span>
                    <span class="item-separator">·</span>
                    <span
                      v-if="item.rarity"
                      class="rarity-label"
                      :class="rarityClass(item.rarity)"
                    >
                      {{ displayName(item.rarity) }}
                    </span>
                    <span v-else class="rarity-label rarity-none">Unrated</span>
                    <span class="item-separator">·</span>
                    <span class="item-total-value">
                      {{ item.totalValue ? `${item.totalValue.amount} gp total` : "Unvalued" }}
                    </span>
                  </span>
                  <span class="item-quantity">×{{ item.quantity }}</span>
                </span>
                <span class="item-name-row">
                  <span class="resource-list-title">{{ item.name }}</span>
                  <span class="item-separator">·</span>
                  <span class="item-unit-value">
                    {{
                      item.unitValue
                        ? `${item.unitValue.amount} ${item.unitValue.denomination} each`
                        : "No value assigned"
                    }}
                  </span>
                </span>
              </button>
            </li>
          </ul>

          <p v-else class="empty-text">
            {{ items.length === 0 ? "No items have been added yet." : "No items match these filters." }}
          </p>
        </aside>

        <article class="resource-detail-panel inventory-detail-panel">
          <template v-if="viewMode === ViewModes.Create || viewMode === ViewModes.Edit">
            <header class="resource-detail-header">
              <p class="resource-detail-kicker">
                {{ viewMode === ViewModes.Create ? "New item" : "Edit item" }}
              </p>
              <h3>{{ viewMode === ViewModes.Create ? "Add to inventory" : selectedEntry?.name }}</h3>
            </header>

            <form
              class="resource-form item-form"
              @submit.prevent="viewMode === ViewModes.Create ? createItem() : updateItem()"
            >
              <label>
                Name
                <input v-model="itemForm.name" type="text" required maxlength="200" />
              </label>

              <div class="form-row three-columns">
                <label>
                  Category
                  <select v-model="itemForm.category">
                    <option v-for="category in itemCategories" :key="category" :value="category">
                      {{ displayName(category) }}
                    </option>
                  </select>
                </label>
                <label>
                  Rarity
                  <select v-model="itemForm.rarity">
                    <option value="">None</option>
                    <option v-for="rarity in itemRarities" :key="rarity" :value="rarity">
                      {{ displayName(rarity) }}
                    </option>
                  </select>
                </label>
                <label>
                  Quantity
                  <input v-model.number="itemForm.quantity" type="number" min="1" step="1" required />
                </label>
              </div>

              <label class="value-toggle">
                <input v-model="itemForm.hasValue" type="checkbox" />
                Assign a unit value
              </label>

              <div v-if="itemForm.hasValue" class="form-row value-fields">
                <label>
                  Unit value
                  <input v-model="itemForm.valueAmount" type="number" min="0" step="0.01" required />
                </label>
                <label>
                  Denomination
                  <select v-model="itemForm.valueDenomination">
                    <option
                      v-for="denomination in currencyDenominations"
                      :key="denomination"
                      :value="denomination"
                    >
                      {{ denomination }}
                    </option>
                  </select>
                </label>
              </div>

              <label>
                Description
                <textarea v-model="itemForm.description" rows="9" />
              </label>

              <p v-if="formError" class="form-error">{{ formError }}</p>

              <div class="resource-form-actions">
                <button type="submit">
                  {{ viewMode === ViewModes.Create ? "Add item" : "Save changes" }}
                </button>
                <button type="button" class="secondary" @click="viewMode = ViewModes.Details">
                  Cancel
                </button>
              </div>
            </form>
          </template>

          <template v-else-if="selectedEntry">
            <header class="resource-detail-header with-actions">
              <div class="resource-detail-title">
                <p class="resource-detail-kicker">
                  <span>{{ displayName(selectedEntry.category) }}</span>
                  <span
                    v-if="selectedEntry.rarity"
                    class="rarity-label"
                    :class="rarityClass(selectedEntry.rarity)"
                  >
                    {{ displayName(selectedEntry.rarity) }}
                  </span>
                </p>
                <h3>{{ selectedEntry.name }}</h3>
              </div>

              <div class="resource-detail-actions">
                <button type="button" class="secondary" @click="showEditItemForm">Edit</button>
                <button type="button" class="danger" @click="showDeleteConfirmation = true">Delete</button>
              </div>
            </header>

            <dl class="item-facts">
              <div><dt>Quantity</dt><dd>{{ selectedEntry.quantity }}</dd></div>
              <div>
                <dt>Unit value</dt>
                <dd>{{ selectedEntry.unitValue ? `${selectedEntry.unitValue.amount} ${selectedEntry.unitValue.denomination}` : "Not valued" }}</dd>
              </div>
              <div>
                <dt>Total value</dt>
                <dd>{{ selectedEntry.totalValue ? `${selectedEntry.totalValue.amount} ${selectedEntry.totalValue.denomination}` : "Not valued" }}</dd>
              </div>
            </dl>

            <p class="resource-description">
              {{ selectedEntry.description || "No description has been added yet." }}
            </p>
          </template>

          <template v-else>
            <div class="inventory-empty-detail">
              <h3>{{ items.length === 0 ? "Your inventory is empty" : "Select an item" }}</h3>
              <p class="empty-text">
                {{ items.length === 0 ? "Add an item to begin cataloguing the party's equipment and valuables." : "Choose an item from the list to see its details." }}
              </p>
              <button v-if="items.length === 0" type="button" @click="showAddItemForm">Add first item</button>
            </div>
          </template>
        </article>
      </div>
    </template>

    <Popup v-if="showPurseManager" title="Adjust purse" @close="showPurseManager = false">
      <form class="purse-form" @submit.prevent="updatePurse('deposit')">
        <div class="purse-inputs">
          <label v-for="denomination in displayedCurrencyDenominations" :key="denomination">
            {{ denomination }}
            <input
              v-model.number="purseChanges[denomination]"
              type="number"
              min="0"
              step="1"
            />
            <small v-if="inventory">
              Current: {{ inventory.purse.balances[denomination] }}
            </small>
          </label>
        </div>

        <p v-if="formError" class="form-error">{{ formError }}</p>
      </form>

      <template #footer>
        <button type="button" @click="updatePurse('deposit')">Deposit</button>
        <button type="button" class="danger" @click="updatePurse('withdraw')">Withdraw</button>
        <button type="button" class="secondary" @click="showPurseManager = false">Cancel</button>
      </template>
    </Popup>

    <ConfirmationPopup
      v-if="showDeleteConfirmation && selectedEntry"
      title="Remove item?"
      :message="`Remove ${selectedEntry.name} from the inventory?`"
      confirm-text="Remove"
      @confirm="deleteItem"
      @cancel="showDeleteConfirmation = false"
    />
  </section>
</template>

<style scoped>
.inventory-view {
  display: grid;
  gap: 1rem;
}

.inventory-header {
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.035);
}

.inventory-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.9rem 1rem 0.65rem;
}

.inventory-heading h2,
.inventory-heading p {
  margin: 0;
}

.inventory-heading h2 {
  font-size: clamp(1.4rem, 2vw, 1.75rem);
}

.inventory-heading p {
  margin-top: 0.15rem;
  color: var(--color-text-muted);
  font-size: 0.85rem;
}

.wealth-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr)) auto;
  align-items: center;
  border-block: 1px solid var(--color-border);
  background: rgba(0, 0, 0, 0.12);
}

.wealth-summary > div {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 0.5rem;
  min-width: 0;
  padding: 0.65rem 1rem;
  border-right: 1px solid var(--color-border);
}

.wealth-summary span,
.wealth-summary small {
  color: var(--color-text-muted);
}

.wealth-summary span {
  font-size: 0.78rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.wealth-summary strong {
  color: var(--color-accent-soft);
  white-space: nowrap;
}

.wealth-summary small {
  max-width: 12rem;
  padding: 0 1rem;
  font-size: 0.75rem;
}

.purse-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  min-height: 2.3rem;
}

.coin-balance {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  padding: 0.45rem 0.75rem;
  border-right: 1px solid rgba(255, 255, 255, 0.055);
}

.coin-balance:last-child {
  border-right: 0;
}

.coin-balance span {
  color: var(--color-text-muted);
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
}

.inventory-layout {
  display: grid;
  grid-template-columns: minmax(19rem, 3fr) minmax(22rem, 2fr);
  gap: 1rem;
  align-items: start;
}

.inventory-list-panel {
  width: 100%;
  max-width: none;
}

.inventory-filters {
  display: grid;
  grid-template-columns: minmax(10rem, 1fr) minmax(9rem, 0.42fr) minmax(10rem, 0.46fr);
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.inventory-filters input,
.inventory-filters select {
  padding: 0.55rem 0.65rem;
}

.inventory-list-item {
  grid-template-columns: 1fr;
  gap: 0.15rem;
  padding: 0.6rem 0.7rem;
}

.item-list-meta-row,
.item-name-row {
  display: flex;
  align-items: center;
  min-width: 0;
}

.item-list-meta-row {
  justify-content: space-between;
  gap: 0.75rem;
}

.item-list-meta {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 0.3rem;
  color: var(--color-text-muted);
  font-size: 0.72rem;
  white-space: nowrap;
}

.item-list-meta > span:first-child {
  color: var(--color-accent-soft);
  font-weight: 700;
}

.item-total-value,
.item-unit-value,
.item-separator {
  color: var(--color-text-muted);
}

.item-quantity {
  flex: 0 0 auto;
  color: var(--color-text-muted);
  font-size: 0.75rem;
}

.item-name-row {
  gap: 0.35rem;
}

.item-name-row .resource-list-title {
  min-width: 0;
  overflow: hidden;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-unit-value {
  flex: 0 0 auto;
  font-size: 0.76rem;
}

.rarity-label {
  display: inline-flex;
  align-items: center;
  margin-left: 0.35rem;
  padding: 0.05rem 0.4rem;
  background: transparent;
  color: var(--rarity-color);
  font-size: 0.85rem;
  font-weight: 700;
  line-height: 1.35;
  text-shadow: 0 0 0.35rem currentColor;
  vertical-align: middle;
}

.inventory-list-item .rarity-label {
  margin-left: 0;
  padding: 0 0.32rem;
  font-size: 0.67rem;
  line-height: 1.3;
}

.resource-detail-kicker {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.resource-detail-kicker .rarity-label {
  margin-left: 0;
}

.rarity-common {
  --rarity-color: #f1e6d0;
}

.rarity-uncommon {
  --rarity-color: #62d26f;
}

.rarity-rare {
  --rarity-color: #5aa9ff;
}

.rarity-very-rare {
  --rarity-color: #c084fc;
}

.rarity-legendary {
  --rarity-color: #ff9f43;
}

.rarity-artifact {
  --rarity-color: #ff625f;
}

.rarity-none {
  --rarity-color: var(--color-text-muted);
  opacity: 0.8;
  text-shadow: none;
}

.inventory-detail-panel {
  min-height: 28rem;
}

.item-facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
  margin: 0 0 1.5rem;
}

.item-facts div {
  padding: 0.8rem;
  border: 1px solid var(--color-border);
  border-radius: 0.65rem;
  background: rgba(0, 0, 0, 0.14);
}

.item-facts dt {
  color: var(--color-text-muted);
  font-size: 0.75rem;
  text-transform: uppercase;
}

.item-facts dd {
  margin: 0.25rem 0 0;
  color: var(--color-accent-soft);
  font-weight: 700;
}

.form-row {
  display: grid;
  gap: 0.75rem;
}

.three-columns {
  grid-template-columns: 1fr 1fr 0.7fr;
}

.value-fields {
  grid-template-columns: minmax(0, 1fr) minmax(8rem, 0.4fr);
}

.value-toggle {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  width: fit-content;
}

.value-toggle input {
  width: auto;
}

.inventory-empty-detail {
  display: grid;
  place-items: center;
  align-content: center;
  min-height: 24rem;
  text-align: center;
}

.inventory-empty-detail h3,
.inventory-empty-detail p {
  margin: 0 0 0.75rem;
}

.purse-form {
  display: grid;
  gap: 1rem;
}

.purse-inputs {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.5rem;
}

.purse-inputs label {
  text-align: center;
  text-transform: uppercase;
}

.purse-inputs input {
  padding-inline: 0.35rem;
  text-align: center;
}

.purse-inputs small {
  color: var(--color-text-muted);
  font-size: 0.7rem;
  text-transform: none;
}

@media (max-width: 1000px) {
  .inventory-layout {
    grid-template-columns: minmax(16rem, 0.8fr) minmax(0, 1.2fr);
  }

  .wealth-summary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .wealth-summary small {
    grid-column: 1 / -1;
    max-width: none;
    padding: 0.35rem 1rem;
    text-align: center;
  }

  .inventory-filters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .inventory-filters input {
    grid-column: 1 / -1;
  }
}

@media (max-width: 760px) {
  .inventory-layout,
  .three-columns,
  .value-fields {
    grid-template-columns: 1fr;
  }

  .inventory-list-panel {
    position: static;
    max-height: none;
  }

  .wealth-summary > div {
    display: grid;
    gap: 0.15rem;
    padding-inline: 0.55rem;
    text-align: center;
  }

  .purse-strip {
    overflow-x: auto;
  }

  .coin-balance {
    min-width: 5rem;
  }
}

@media (max-width: 520px) {
  .inventory-heading {
    align-items: flex-start;
  }

  .wealth-summary {
    grid-template-columns: 1fr;
  }

  .wealth-summary > div {
    display: flex;
    justify-content: space-between;
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
    text-align: left;
  }

  .purse-inputs {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .inventory-filters,
  .item-facts {
    grid-template-columns: 1fr;
  }
}
</style>
