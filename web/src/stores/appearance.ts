import { computed, reactive, readonly } from "vue";


const STORAGE_KEY = "graduation-project.appearance";

type ThemeMode = "light" | "dark";

interface AppearanceState {
  themeMode: ThemeMode;
}

function applyThemeModeToDocument(mode: ThemeMode) {
  if (typeof document === "undefined") {
    return;
  }
  document.documentElement.dataset.theme = mode;
}

function loadInitialState(): AppearanceState {
  const defaultState: AppearanceState = { themeMode: "light" };
  if (typeof window === "undefined") {
    return defaultState;
  }

  const raw = window.localStorage.getItem(STORAGE_KEY);
  const nextMode: ThemeMode = raw === "dark" ? "dark" : "light";
  applyThemeModeToDocument(nextMode);
  return { themeMode: nextMode };
}

const state = reactive<AppearanceState>(loadInitialState());

function persistState() {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, state.themeMode);
}

export function useAppearanceStore() {
  const isDark = computed(() => state.themeMode === "dark");

  function setThemeMode(mode: ThemeMode) {
    state.themeMode = mode;
    applyThemeModeToDocument(mode);
    persistState();
  }

  function toggleThemeMode() {
    setThemeMode(state.themeMode === "dark" ? "light" : "dark");
  }

  return {
    state: readonly(state),
    isDark,
    setThemeMode,
    toggleThemeMode,
  };
}
