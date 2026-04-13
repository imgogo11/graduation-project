import { deleteJson, getJson, patchJson, postJson } from "@/api/http";
import type {
  AdminManagedUserDeleteResponse,
  AdminManagedUserRead,
  AuthTokenRead,
  UserRead,
} from "@/api/types";


export function registerUser(payload: { username: string; password: string }) {
  return postJson<AuthTokenRead>("/api/auth/register", payload);
}

export function loginUser(payload: { username: string; password: string }) {
  return postJson<AuthTokenRead>("/api/auth/login", payload);
}

export function fetchCurrentUser() {
  return getJson<UserRead>("/api/auth/me");
}

export function fetchAdminUsers(query?: string) {
  return getJson<AdminManagedUserRead[]>("/api/admin/users", query ? { query } : undefined);
}

export function updateAdminUser(
  userId: number,
  payload: {
    username?: string;
    password?: string;
    is_active?: boolean;
  }
) {
  return patchJson<AdminManagedUserRead>(`/api/admin/users/${userId}`, payload);
}

export function disableAdminUser(userId: number) {
  return postJson<AdminManagedUserRead>(`/api/admin/users/${userId}/disable`);
}

export function enableAdminUser(userId: number) {
  return postJson<AdminManagedUserRead>(`/api/admin/users/${userId}/enable`);
}

export function deleteAdminUser(userId: number) {
  return deleteJson<AdminManagedUserDeleteResponse>(`/api/admin/users/${userId}`);
}
