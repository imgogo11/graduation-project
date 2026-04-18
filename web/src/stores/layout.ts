import { computed, reactive, readonly } from "vue";


interface VisitedTab {
  path: string;
  title: string;
  affix?: boolean;
}

const state = reactive({
  sidebarCollapsed: false,
  mobileSidebarOpen: false,
  visitedTabs: [] as VisitedTab[],
});

export function useLayoutStore() {
  const tabs = computed(() => state.visitedTabs);

  function toggleSidebarCollapsed() {
    state.sidebarCollapsed = !state.sidebarCollapsed;
  }

  function setSidebarCollapsed(collapsed: boolean) {
    state.sidebarCollapsed = collapsed;
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
      return;
    }

    state.visitedTabs.push(tab);
  }

  function removeTab(path: string) {
    const index = state.visitedTabs.findIndex((item) => item.path === path);
    if (index >= 0) {
      state.visitedTabs.splice(index, 1);
    }
  }

  function resetLayout() {
    state.sidebarCollapsed = false;
    state.mobileSidebarOpen = false;
    const affixTabs = state.visitedTabs.filter((item) => item.affix);
    state.visitedTabs.splice(0, state.visitedTabs.length, ...affixTabs);
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
    resetLayout,
  };
}
