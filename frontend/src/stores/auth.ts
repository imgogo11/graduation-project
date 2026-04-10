import { computed, reactive, readonly } from "vue";

import type { AuthTokenRead, UserRead } from "@/api/types";


const STORAGE_KEY = "graduation-project.auth";

interface AuthState {
  accessToken: string;
  user: UserRead | null;
}

function loadInitialState(): AuthState {
  const emptyState: AuthState = { accessToken: "", user: null };
  if (typeof window === "undefined") {
    return emptyState;
  }

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return emptyState;
  }

  try {
    const parsed = JSON.parse(raw) as AuthState;
    return {
      accessToken: parsed.accessToken || "",
      user: parsed.user || null,
    };
  } catch {
    return emptyState;
  }
}

const state = reactive<AuthState>(loadInitialState());

function persistState() {
  if (typeof window === "undefined") {
    return;
  }

  if (!state.accessToken || !state.user) {
    window.localStorage.removeItem(STORAGE_KEY);
    return;
  }

  window.localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      accessToken: state.accessToken,
      user: state.user,
    })
  );
}

export function getStoredAccessToken() {
  return state.accessToken;
}

export function useAuthStore() {
  const isAuthenticated = computed(() => Boolean(state.accessToken && state.user));
  const isAdmin = computed(() => state.user?.role === "admin");
  const username = computed(() => state.user?.username || "");

  function applySession(payload: AuthTokenRead) {
    state.accessToken = payload.access_token;
    state.user = payload.user;
    persistState();
  }

  function setUser(user: UserRead) {
    state.user = user;
    persistState();
  }

  function clearSession() {
    state.accessToken = "";
    state.user = null;
    persistState();
  }

  return {
    state: readonly(state),
    isAuthenticated,
    isAdmin,
    username,
    applySession,
    setUser,
    clearSession,
  };
}
