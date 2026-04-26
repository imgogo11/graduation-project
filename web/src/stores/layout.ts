import { computed, reactive, readonly } from "vue";


const STORAGE_KEY = "graduation-project.layout";
const LEGACY_TAB_REDIRECTS: Record<string, VisitedTab> = {
  "/admin/overview": {
    path: "/admin/assets",
    title: "\u6570\u636e\u8d44\u4ea7\u603b\u89c8",
    affix: true,
  },
  "/admin/health": {
    path: "/admin/assets",
    title: "\u6570\u636e\u8d44\u4ea7\u603b\u89c8",
    affix: true,
  },
};

interface VisitedTab {
  path: string;
  title: string;
  affix?: boolean;
}

interface LayoutState {
  sidebarCollapsed: boolean;
  mobileSidebarOpen: boolean;
  visitedTabs: VisitedTab[];
}

function normalizeVisitedTabs(value: unknown): VisitedTab[] {
  if (!Array.isArray(value)) {
    return [];
  }

  const normalized = new Map<string, VisitedTab>();
  for (const item of value) {
    if (!item || typeof item !== "object") {
      continue;
    }

    const candidate = item as Partial<VisitedTab>;
    if (typeof candidate.path !== "string" || typeof candidate.title !== "string") {
      continue;
    }

    const redirected = LEGACY_TAB_REDIRECTS[candidate.path];
    const normalizedItem = redirected ?? {
      path: candidate.path,
      title: candidate.title,
      affix: Boolean(candidate.affix),
    };
    if (normalizedItem.path === "/admin/users" && normalizedItem.affix) {
      normalizedItem.affix = false;
    }
    const existing = normalized.get(normalizedItem.path);

    if (existing) {
      existing.affix = Boolean(existing.affix || normalizedItem.affix);
      continue;
    }

    normalized.set(normalizedItem.path, { ...normalizedItem });
  }

  return Array.from(normalized.values());
}

function loadInitialState(): LayoutState {
  const defaultState: LayoutState = {
    sidebarCollapsed: false,
    mobileSidebarOpen: false,
    visitedTabs: [],
  };

  if (typeof window === "undefined") {
    return defaultState;
  }

  const raw = window.sessionStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return defaultState;
  }

  try {
    const parsed = JSON.parse(raw) as Partial<LayoutState>;
    return {
      sidebarCollapsed: Boolean(parsed.sidebarCollapsed),
      mobileSidebarOpen: false,
      visitedTabs: normalizeVisitedTabs(parsed.visitedTabs),
    };
  } catch {
    return defaultState;
  }
}

const state = reactive<LayoutState>(loadInitialState());

function persistState() {
  if (typeof window === "undefined") {
    return;
  }

  const payload: LayoutState = {
    sidebarCollapsed: state.sidebarCollapsed,
    mobileSidebarOpen: false,
    visitedTabs: state.visitedTabs.map((item) => ({
      path: item.path,
      title: item.title,
      affix: Boolean(item.affix),
    })),
  };

  if (!payload.sidebarCollapsed && payload.visitedTabs.length === 0) {
    window.sessionStorage.removeItem(STORAGE_KEY);
    return;
  }

  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

export function useLayoutStore() {
  const tabs = computed(() => state.visitedTabs);

  function toggleSidebarCollapsed() {
    state.sidebarCollapsed = !state.sidebarCollapsed;
    persistState();
  }

  function setSidebarCollapsed(collapsed: boolean) {
    state.sidebarCollapsed = collapsed;
    persistState();
  }

  function openMobileSidebar() {
    state.mobileSidebarOpen = true;
  }

  function closeMobileSidebar() {
    state.mobileSidebarOpen = false;
  }

  function visitTab(tab: VisitedTab) {
    if (!tab.title) {
      return;
    }

    const existing = state.visitedTabs.find((item) => item.path === tab.path);
    if (existing) {
      existing.title = tab.title;
      existing.affix = tab.affix;
      persistState();
      return;
    }

    state.visitedTabs.push(tab);
    persistState();
  }

  function removeTab(path: string) {
    const index = state.visitedTabs.findIndex((item) => item.path === path);
    if (index >= 0) {
      state.visitedTabs.splice(index, 1);
      persistState();
    }
  }

  function pruneTabs(allowedPaths: string[]) {
    const allowed = new Set(allowedPaths);
    const nextTabs = state.visitedTabs.filter((item) => allowed.has(item.path));

    if (nextTabs.length === state.visitedTabs.length) {
      return;
    }

    state.visitedTabs.splice(0, state.visitedTabs.length, ...nextTabs);
    persistState();
  }

  function resetLayout() {
    state.sidebarCollapsed = false;
    state.mobileSidebarOpen = false;
    const affixTabs = state.visitedTabs.filter((item) => item.affix);
    state.visitedTabs.splice(0, state.visitedTabs.length, ...affixTabs);
    persistState();
  }

  return {
    state: readonly(state),
    tabs,
    toggleSidebarCollapsed,
    setSidebarCollapsed,
    openMobileSidebar,
    closeMobileSidebar,
    visitTab,
    removeTab,
    pruneTabs,
    resetLayout,
  };
}
