
export const baseUrl = import.meta.env.DEV ? "http://localhost:8000/" : "/"
export const apiUrl = baseUrl + "api/"

const fetchTimeout = 3000;

function fetchError(x) {
    console.log(`Fetch error: ${x}`);
    window.err = x;
    return {"success": false, "message": `Fetch error ${x}`};
}

async function statusCodeHandler(response) {
  switch (response.status) {
    case 200:
    case 201: {
      const data = await response.json();
      return keysToCamelCase(data);
    }
    case 204:
      return { success: true };
    case 400:
      return {
        success: false,
        status: 400,
        message: "Bad Request: " + (response.statusText || "The server could not understand the request."),
      };
    case 401:
      return {
        success: false,
        status: 401,
        message: "Unauthorized",
      };
    case 500:
      return {
        success: false,
        status: 500,
        message: `Internal Server Error: ${response.statusText}`,
      };
    default:
      return {
        success: false,
        status: response.status,
        message: `Request failed. HTTP error code: ${response.status}: ${response.statusText}`,
      };
  }
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

export async function GetAPI(endpoint)
{
  return fetch(apiUrl + endpoint, {
    method: "GET",
    signal: AbortSignal.timeout ? AbortSignal.timeout(fetchTimeout) : undefined
  })
  .then(statusCodeHandler)
  .catch(fetchError);
}

export async function PostAPI(endpoint, data, {parseResponseJson = true} = {})
{
  return fetch(apiUrl + endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json", },
    signal: AbortSignal.timeout ? AbortSignal.timeout(fetchTimeout) : undefined,
    body: JSON.stringify(keysToSnakeCase(data))
  })
  .then(x => parseResponseJson ? statusCodeHandler(x) : x)
  .catch(fetchError);
}

export async function PostFormDataAPI(endpoint, formData, {parseResponseJson = true} = {})
{
  return fetch(apiUrl + endpoint, {
    method: "POST",
    signal: AbortSignal.timeout ? AbortSignal.timeout(fetchTimeout) : undefined,
    body: formData
  })
  .then(x => parseResponseJson ? statusCodeHandler(x) : x)
  .catch(fetchError);
}

export async function PutAPI(endpoint, data, {parseResponseJson = true} = {})
{
  return fetch(apiUrl + endpoint, {
    method: "PUT",
    headers: { "Content-Type": "application/json", },
    signal: AbortSignal.timeout ? AbortSignal.timeout(fetchTimeout) : undefined,
    body: JSON.stringify(keysToSnakeCase(data))
  })
  .then(x => parseResponseJson ? statusCodeHandler(x) : x)
  .catch(fetchError);
}

export async function PutFormDataAPI(endpoint, formData, {parseResponseJson = true} = {})
{
  return fetch(apiUrl + endpoint, {
    method: "PUT",
    signal: AbortSignal.timeout ? AbortSignal.timeout(fetchTimeout) : undefined,
    body: formData
  })
  .then(x => parseResponseJson ? statusCodeHandler(x) : x)
  .catch(fetchError);
}

export async function DeleteAPI(endpoint, {parseResponseJson = true} = {})
{
  return fetch(apiUrl + endpoint, {
    method: "DELETE",
    signal: AbortSignal.timeout ? AbortSignal.timeout(fetchTimeout) : undefined
  })
  .then(x => parseResponseJson ? statusCodeHandler(x) : x)
  .catch(fetchError);
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