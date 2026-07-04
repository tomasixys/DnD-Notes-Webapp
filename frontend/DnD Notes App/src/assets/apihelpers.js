export const baseUrl = import.meta.env.DEV ? "http://localhost:5173/" : "/"

const fetchTimeout = 3000;

async function statusCodeHandler(response) {
    switch (response.status) {
        case 200:
            return response.json();
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

export async function RunCommand(command)
{
    return fetch(baseUrl + "command/" + command, {
        method: "POST",
        signal: AbortSignal.timeout ? AbortSignal.timeout(fetchTimeout) : undefined
    })
    .then(statusCodeHandler)
    .catch(fetchError);
}

export async function FetchAPI(endpoint)
{
    return fetch(baseUrl + "api/" + endpoint, {
        signal: AbortSignal.timeout ? AbortSignal.timeout(fetchTimeout) : undefined
    })
    .then(statusCodeHandler)
    .catch(fetchError);
}

export async function PostAPI(endpoint, data, {parseResponseJson = true} = {})
{
    return fetch(baseUrl + "api/" + endpoint, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        signal: AbortSignal.timeout ? AbortSignal.timeout(fetchTimeout) : undefined,
        body: JSON.stringify(data)
    })
    .then(x => parseResponseJson ? statusCodeHandler(x) : x)
    .catch(fetchError);
}
