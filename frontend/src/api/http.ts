import { getStoredAccessToken } from "@/stores/auth";

type QueryValue = string | number | boolean | null | undefined;


export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function buildUrl(path: string, params?: object) {
  const base = (import.meta.env.VITE_API_BASE || "").replace(/\/$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const search = new URLSearchParams();

  if (params) {
    for (const [key, value] of Object.entries(params as Record<string, QueryValue>)) {
      if (value === undefined || value === null || value === "") {
        continue;
      }
      search.append(key, String(value));
    }
  }

  const query = search.toString();
  return `${base}${normalizedPath}${query ? `?${query}` : ""}`;
}

async function parseError(response: Response) {
  try {
    const payload = (await response.json()) as { detail?: string | { message?: string } };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    if (payload.detail && typeof payload.detail === "object" && "message" in payload.detail) {
      return payload.detail.message || response.statusText || "Request failed";
    }
    return response.statusText || "Request failed";
  } catch {
    return response.statusText || "Request failed";
  }
}

function buildHeaders(extraHeaders?: HeadersInit) {
  const token = getStoredAccessToken();
  const headers = new Headers(extraHeaders);
  headers.set("Accept", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

async function requestJson<T>(path: string, init: RequestInit, params?: object) {
  const response = await fetch(buildUrl(path, params), {
    ...init,
    headers: buildHeaders(init.headers),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await parseError(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function getJson<T>(path: string, params?: object) {
  return requestJson<T>(
    path,
    {
      method: "GET",
    },
    params
  );
}

export async function postJson<T>(path: string, body?: object) {
  return requestJson<T>(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
}

export async function postForm<T>(path: string, formData: FormData) {
  const response = await fetch(buildUrl(path), {
    method: "POST",
    headers: buildHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw new ApiError(response.status, await parseError(response));
  }

  return (await response.json()) as T;
}

export async function deleteJson<T>(path: string) {
  return requestJson<T>(path, {
    method: "DELETE",
  });
}
