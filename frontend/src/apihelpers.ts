import { invalidateCampaignSearch } from "@/stores/searchStore"

export const baseUrl = import.meta.env.DEV ? "http://localhost:8000/" : "/"
export const apiUrl = baseUrl + "api/"

const fetchTimeout = 3000
const unsafeMethods = new Set(["POST", "PUT", "PATCH", "DELETE"])

export type ApiFailureKind =
  | "authentication"
  | "authorization"
  | "not-found"
  | "conflict"
  | "validation"
  | "server"
  | "network"

export type ApiFailure = {
  success: false
  status?: number
  kind: ApiFailureKind
  error: string
  message: string
}

type ApiSecurityConfiguration = {
  csrfToken: () => string | null
  onFailure: (failure: ApiFailure) => void
}

let securityConfiguration: ApiSecurityConfiguration = {
  csrfToken: () => null,
  onFailure: () => undefined,
}

export function configureApiSecurity(
  configuration: ApiSecurityConfiguration,
) {
  securityConfiguration = configuration
}

function failureKind(status: number): ApiFailureKind {
  if (status === 401) return "authentication"
  if (status === 403) return "authorization"
  if (status === 404) return "not-found"
  if (status === 409) return "conflict"
  if (status === 400 || status === 422) return "validation"
  return "server"
}

function networkFailure(error: unknown): ApiFailure {
  const detail = error instanceof Error ? error.message : String(error)
  return {
    success: false,
    kind: "network",
    error: `Network request failed: ${detail}`,
    message: "The server could not be reached.",
  }
}

function formatErrorDetail(detail: unknown, response: Response): string {
  if (typeof detail === "string" && detail) {
    return detail
  }
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((entry) => (
        typeof entry === "object" && entry !== null && "msg" in entry
          ? String(entry.msg)
          : ""
      ))
      .filter(Boolean)
      .join("; ")
  }
  return (
    response.statusText
    || `Request failed with HTTP status ${response.status}`
  )
}

async function responseFailure(response: Response): Promise<ApiFailure> {
  let body: { detail?: unknown } | null = null
  try {
    body = await response.json()
  } catch {
    // Some server/proxy failures do not include JSON.
  }
  const message = formatErrorDetail(body?.detail, response)
  return {
    success: false,
    status: response.status,
    kind: failureKind(response.status),
    error: message,
    message,
  }
}

function requestHeaders(
  method: string,
  headers?: HeadersInit,
): Headers {
  const result = new Headers(headers)
  if (unsafeMethods.has(method.toUpperCase())) {
    const csrfToken = securityConfiguration.csrfToken()
    if (csrfToken) {
      result.set("X-CSRF-Token", csrfToken)
    }
  }
  return result
}

async function performFetch(
  endpoint: string,
  init: RequestInit,
  { notifyFailures = true }: { notifyFailures?: boolean } = {},
): Promise<Response | ApiFailure> {
  const method = (init.method ?? "GET").toUpperCase()
  try {
    const response = await fetch(apiUrl + endpoint, {
      ...init,
      method,
      credentials: "include",
      headers: requestHeaders(method, init.headers),
      signal: AbortSignal.timeout
        ? AbortSignal.timeout(fetchTimeout)
        : undefined,
    })
    if (response.ok) return response

    const failure = await responseFailure(response)
    if (notifyFailures) securityConfiguration.onFailure(failure)
    return failure
  } catch (error) {
    const failure = networkFailure(error)
    if (notifyFailures) securityConfiguration.onFailure(failure)
    return failure
  }
}

async function parseResponse(
  result: Response | ApiFailure,
): Promise<unknown | ApiFailure> {
  if (!("ok" in result)) return result
  if (result.status === 204) return null
  const text = await result.text()
  return text ? keysToCamelCase(JSON.parse(text)) : null
}

function applyMutationSideEffects(
  endpoint: string,
  method: string,
  response: unknown | ApiFailure,
) {
  if (
    isApiFailure(response)
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

export function isApiFailure(value: unknown): value is ApiFailure {
  return (
    typeof value === "object"
    && value !== null
    && "success" in value
    && value.success === false
  )
}

type RequestOptions = {
  parseResponseJson?: boolean
  method?: string
  notifyFailures?: boolean
}

export async function GetAPI<T = unknown>(
  endpoint: string,
  {
    parseResponseJson = true,
    method = "GET",
    notifyFailures = true,
  }: RequestOptions = {},
): Promise<T | ApiFailure> {
  const result = await performFetch(
    endpoint,
    { method },
    { notifyFailures },
  )
  const response = parseResponseJson ? await parseResponse(result) : result
  return applyMutationSideEffects(endpoint, method, response) as T | ApiFailure
}

export async function DeleteAPI<T = unknown>(
  endpoint: string,
  options: RequestOptions = {},
): Promise<T | ApiFailure> {
  return GetAPI<T>(endpoint, { ...options, method: "DELETE" })
}

export async function PostAPI<T = unknown>(
  endpoint: string,
  data: unknown,
  {
    parseResponseJson = true,
    method = "POST",
    notifyFailures = true,
  }: RequestOptions = {},
): Promise<T | ApiFailure> {
  const result = await performFetch(
    endpoint,
    {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(keysToSnakeCase(data)),
    },
    { notifyFailures },
  )
  const response = parseResponseJson ? await parseResponse(result) : result
  return applyMutationSideEffects(endpoint, method, response) as T | ApiFailure
}

export async function PutAPI<T = unknown>(
  endpoint: string,
  data: unknown,
  options: RequestOptions = {},
): Promise<T | ApiFailure> {
  return PostAPI<T>(endpoint, data, { ...options, method: "PUT" })
}

export async function PatchAPI<T = unknown>(
  endpoint: string,
  data: unknown,
  options: RequestOptions = {},
): Promise<T | ApiFailure> {
  return PostAPI<T>(endpoint, data, { ...options, method: "PATCH" })
}

export async function PostFormDataAPI<T = unknown>(
  endpoint: string,
  formData: FormData,
  {
    parseResponseJson = true,
    method = "POST",
    notifyFailures = true,
  }: RequestOptions = {},
): Promise<T | ApiFailure> {
  const result = await performFetch(
    endpoint,
    { method, body: formData },
    { notifyFailures },
  )
  const response = parseResponseJson ? await parseResponse(result) : result
  return applyMutationSideEffects(endpoint, method, response) as T | ApiFailure
}

export async function PutFormDataAPI<T = unknown>(
  endpoint: string,
  formData: FormData,
  options: RequestOptions = {},
): Promise<T | ApiFailure> {
  return PostFormDataAPI<T>(
    endpoint,
    formData,
    { ...options, method: "PUT" },
  )
}

export async function DownloadAPI(
  endpoint: string,
  filename: string | null = null,
): Promise<ApiFailure | { success: true; message: string }> {
  const result = await performFetch(endpoint, { method: "GET" })
  if (!("ok" in result)) return result

  const blob = await result.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = Object.assign(document.createElement("a"), {
    href: objectUrl,
    download: filename ?? (endpoint.split("/").pop() || endpoint),
  })
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
  return {
    success: true as const,
    message: "File downloaded successfully.",
  }
}

function snakeToCamel(key: string) {
  return key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

export function keysToCamelCase(value: unknown): unknown {
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

function camelToSnake(key: string) {
  return key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
}

export function keysToSnakeCase(value: unknown): unknown {
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
