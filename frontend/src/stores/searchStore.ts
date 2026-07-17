import { ref } from "vue"
import type { SearchResourceType, SearchResponseDto } from "@/types/DataTransferObjects"

type CachedSearch = {
  key: string
  campaignId: number
  response: SearchResponseDto
  cachedAt: number
}

const cachedSearch = ref<CachedSearch | null>(null)

function createSearchKey(
  campaignId: number,
  query: string,
  resourceTypes: SearchResourceType[])
{
  const normalizedQuery = query.trim().toLowerCase()
  const normalizedTypes = [...new Set(resourceTypes)].sort()
  return JSON.stringify([campaignId, normalizedQuery, normalizedTypes])
}

function getCachedSearch(
  campaignId: number,
  query: string,
  resourceTypes: SearchResourceType[],
): SearchResponseDto | null
{
  const key = createSearchKey(campaignId, query, resourceTypes)
  if (cachedSearch.value?.key !== key) return null

  return cachedSearch.value.response
}

function cacheSearch(
  campaignId: number,
  query: string,
  resourceTypes: SearchResourceType[],
  response: SearchResponseDto)
{
  cachedSearch.value = {
    key: createSearchKey(campaignId, query, resourceTypes),
    campaignId,
    response,
    cachedAt: Date.now(),
  }
}

function clearSearchCache() {
  cachedSearch.value = null
}

function invalidateCampaignSearch(campaignId: number) {
  if (cachedSearch.value?.campaignId === campaignId) {
    clearSearchCache()
  }
}

export function useSearchStore() {
  return {
    getCachedSearch,
    cacheSearch,
    invalidateCampaignSearch,
    clearSearchCache,
  }
}