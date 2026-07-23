
import { invalidateCampaignSearch } from "@/stores/searchStore"

export const baseUrl = import.meta.env.DEV ? "http://localhost:8000/" : "/"
export const apiUrl = baseUrl + "api/"

const fetchTimeout = 3000;

function fetchError(x) {
  console.log(`Fetch error: ${x}`)
  window.err = x
  const error = `Fetch error ${x}`
  return {
    success: false,
    error,
    message: error,
  }
}

function formatErrorDetail(detail, response) {
  if (typeof detail === "string" && detail) {
    return detail
  }
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((entry) => entry?.msg)
      .filter(Boolean)
      .join("; ")
  }
  return (
    response.statusText
    || `Request failed with HTTP status ${response.status}`
  )
}

async function statusCodeHandler(response) {
  if (response.ok) {
    if (response.status === 204) {
      return null
    }
    const text = await response.text()
    return text ? keysToCamelCase(JSON.parse(text)) : null
  }

  let body = null
  try {
    body = await response.json()
  } catch {
    // Some server/proxy failures do not include a JSON response body.
  }
  const error = formatErrorDetail(body?.detail, response)
  return {
    success: false,
    status: response.status,
    error,
    message: error,
  }
}

function applyMutationSideEffects(endpoint, method, response) {
  if (
    response?.success === false
    || method.toUpperCase() === "GET"
    || endpoint.endsWith("/search")
  ) {
    return response
  }

  const campaignMatch = /^campaigns\/(\d+)(?:\/|$)/.exec(endpoint)
  if (campaignMatch) {
    invalidateCampaignSearch(Number(campaignMatch[1]))
  }
  return response
}

export async function DownloadAPI(endpoint, filename = null)
{
  return fetch(apiUrl + endpoint, {
    method: "GET",
    signal: AbortSignal.timeout ? AbortSignal.timeout(fetchTimeout) : undefined
  })
  .then(async response => {
    if (!response.ok) {
      return statusCodeHandler(response);
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob)

    const link = Object.assign(document.createElement("a"), {
      href: objectUrl,
      download: filename ?? (endpoint.split("/").pop() || endpoint)
    })
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(objectUrl)
    return { success: true, message: "File downloaded successfully." };
  })
  .catch(fetchError);
}

export async function GetAPI(endpoint, {parseResponseJson = true, method = "GET"} = {})
{
  return fetch(apiUrl + endpoint, {
    method: method,
    signal: AbortSignal.timeout ? AbortSignal.timeout(fetchTimeout) : undefined
  })
  .then(x => parseResponseJson ? statusCodeHandler(x) : x)
  .then(response =>
    applyMutationSideEffects(endpoint, method, response)
  )
  .catch(fetchError);
}
export async function DeleteAPI(endpoint, {parseResponseJson = true, method = "DELETE"} = {})
{
  return GetAPI(endpoint, {parseResponseJson, method});
}


export async function PostAPI(endpoint, data, {parseResponseJson = true, method = "POST"} = {})
{
  return fetch(apiUrl + endpoint, {
    method: method,
    headers: { "Content-Type": "application/json", },
    signal: AbortSignal.timeout ? AbortSignal.timeout(fetchTimeout) : undefined,
    body: JSON.stringify(keysToSnakeCase(data))
  })
  .then(x => parseResponseJson ? statusCodeHandler(x) : x)
  .then(response =>
    applyMutationSideEffects(endpoint, method, response)
  )
  .catch(fetchError);
}

export async function PutAPI(endpoint, data, {parseResponseJson = true} = {})
{
  return PostAPI(endpoint, data, {parseResponseJson, method: "PUT"});
}

export async function PatchAPI(endpoint, data, {parseResponseJson = true} = {})
{
  return PostAPI(endpoint, data, {parseResponseJson, method: "PATCH"});
}


export async function PostFormDataAPI(endpoint, formData, {parseResponseJson = true, method = "POST"} = {})
{
  return fetch(apiUrl + endpoint, {
    method: method,
    signal: AbortSignal.timeout ? AbortSignal.timeout(fetchTimeout) : undefined,
    body: formData
  })
  .then(x => parseResponseJson ? statusCodeHandler(x) : x)
  .then(response =>
    applyMutationSideEffects(endpoint, method, response)
  )
  .catch(fetchError);
}

export async function PutFormDataAPI(endpoint, formData, {parseResponseJson = true, method = "PUT"} = {})
{
  return PostFormDataAPI(endpoint, formData, {parseResponseJson, method});
}




function snakeToCamel(key) {
  return key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

export function keysToCamelCase(value) {
  if (Array.isArray(value)) {
    return value.map(keysToCamelCase)
  }

  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, nestedValue]) => [
        snakeToCamel(key),
        keysToCamelCase(nestedValue),
      ]),
    )
  }

    return value
  }

  function camelToSnake(key) {
    return key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
  }

  export function keysToSnakeCase(value) {
    if (Array.isArray(value)) {
      return value.map(keysToSnakeCase)
    }

    if (value !== null && typeof value === "object") {
      return Object.fromEntries(
        Object.entries(value).map(([key, nestedValue]) => [
          camelToSnake(key),
          keysToSnakeCase(nestedValue),
        ]),
      )
    }

    return value
  }
