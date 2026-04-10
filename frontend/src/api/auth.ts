import { getJson, postJson } from "@/api/http";
import type { AuthTokenRead, UserRead } from "@/api/types";


export function registerUser(payload: { username: string; password: string }) {
  return postJson<AuthTokenRead>("/api/auth/register", payload);
}

export function loginUser(payload: { username: string; password: string }) {
  return postJson<AuthTokenRead>("/api/auth/login", payload);
}

export function fetchCurrentUser() {
  return getJson<UserRead>("/api/auth/me");
}
