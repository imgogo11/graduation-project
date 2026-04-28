<script setup lang="ts">
import { computed, h, nextTick, onBeforeUnmount, onErrorCaptured, onMounted, ref, watch } from "vue";

import {
  ContractOutline,
  DocumentTextOutline,
  ExpandOutline,
  FolderOpenOutline,
  FunnelOutline,
  GridOutline,
  ListOutline,
  MenuOutline,
  NotificationsOutline,
  PeopleOutline,
  PersonCircleOutline,
  PodiumOutline,
  PulseOutline,
  SearchOutline,
  ServerOutline,
  StatsChartOutline,
} from "@vicons/ionicons5";
import {
  NAlert,
  NBadge,
  NButton,
  NDropdown,
  NIcon,
  NInput,
  NMenu,
  NPopover,
  NScrollbar,
  NTag,
  type InputInst,
  type MenuOption,
} from "naive-ui";
import { RouterView, useRoute, useRouter } from "vue-router";

import logo from "@/assets/branding/logo.png";
import { fetchAlgoIndexStatus } from "@/api/riskRadar";
import UnifiedFilterDrawer from "@/components/UnifiedFilterDrawer.vue";
import { APP_BRAND_NAME, APP_BRAND_SUBTITLE } from "@/constants/branding";
import { useAuthStore } from "@/stores/auth";
import { useDatasetContextStore } from "@/stores/datasetContext";
import { useLayoutStore } from "@/stores/layout";
import { useRuntimeStore } from "@/stores/runtime";
import { formatRoleText, formatStatusText } from "@/utils/displayText";
import { formatDateTime } from "@/utils/format";


interface NavItem {
  title: string;
  subtitle?: string;
  path?: string;
  key: string;
  iconComponent?: unknown;
  children?: NavItem[];
}

interface BreadcrumbItem {
  label: string;
  path?: string;
}

interface SearchEntry {
  key: string;
  title: string;
  path: string;
  trail: string[];
  source: "menu" | "tab";
}

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const datasetContext = useDatasetContextStore();
const layout = useLayoutStore();
const runtime = useRuntimeStore();
const isMobile = ref(false);
const routeRenderError = ref("");
const expandedMenuKeys = ref<string[]>([]);
const searchModalVisible = ref(false);
const searchKeyword = ref("");
const searchInputRef = ref<InputInst | null>(null);
const activeSearchIndex = ref(0);
const isFullscreen = ref(false);
const filterDrawerVisible = ref(false);
let algoIndexStatusRequestId = 0;

const tabs = layout.tabs;
const isAdmin = auth.isAdmin;
const defaultPath = computed(() => (isAdmin.value ? "/admin/assets" : "/workbench"));
const brandSubtitle = computed(() => (isAdmin.value ? APP_BRAND_SUBTITLE.admin : APP_BRAND_SUBTITLE.user));

const userItems: NavItem[] = [
  {
    title: "\u5de5\u4f5c\u53f0",
    key: "/workbench",
    path: "/workbench",
    iconComponent: GridOutline,
  },
  {
    title: "\u6570\u636e\u96c6",
    key: "/datasets",
    path: "/datasets",
    iconComponent: FolderOpenOutline,
  },
  {
    title: "\u5206\u6790\u4e2d\u5fc3",
    key: "/analysis",
    iconComponent: StatsChartOutline,
    children: [
      {
        title: "\u91d1\u878d\u5206\u6790",
        key: "/analysis/market",
        path: "/analysis/market",
      },
      {
        title: "\u5feb\u7167\u4e0e\u76f8\u5173\u6027",
        key: "/analysis/governance",
        path: "/analysis/governance",
      },
    ],
  },
  {
    title: "\u7b97\u6cd5\u96f7\u8fbe",
    key: "/algo-radar",
    iconComponent: PulseOutline,
    children: [
      {
        title: "\u98ce\u9669\u96f7\u8fbe",
        key: "/algo-radar/risk",
        path: "/algo-radar/risk",
      },
      {
        title: "\u7b97\u6cd5\u67e5\u8be2",
        key: "/algo-radar/algorithms",
        path: "/algo-radar/algorithms",
      },
    ],
  },
];

const adminItems: NavItem[] = [
  {
    title: "\u6570\u636e\u8d44\u4ea7",
    key: "/admin/assets",
    path: "/admin/assets",
    iconComponent: ServerOutline,
  },
  {
    title: "\u7528\u6237\u7ba1\u7406",
    key: "/admin/users",
    path: "/admin/users",
    iconComponent: PeopleOutline,
  },
  {
    title: "\u8c03\u7528\u8bb0\u5f55",
    key: "/admin/activity",
    path: "/admin/activity",
    iconComponent: DocumentTextOutline,
  },
  {
    title: "\u8fd0\u884c\u76d1\u63a7",
    key: "/admin/runs",
    path: "/admin/runs",
    iconComponent: PodiumOutline,
  },
];

const menuGroups = computed(() => [
  {
    label: isAdmin.value ? "\u7ba1\u7406\u5458\u540e\u53f0" : "\u4e1a\u52a1\u5206\u6790",
    items: isAdmin.value ? adminItems : userItems,
  },
]);
const menuOptions = computed<MenuOption[]>(() => menuGroups.value[0].items.map((item) => toMenuOption(item)));
const allowedTabPaths = computed(() => flattenNavItems(menuGroups.value[0]?.items ?? []).map((item) => item.path));

const breadcrumbs = computed<BreadcrumbItem[]>(() => {
  const items = menuGroups.value[0]?.items ?? [];
  const trail = findMenuTrail(route.path, items);
  const groupLabel = menuGroups.value[0]?.label;
  const breadcrumbs: BreadcrumbItem[] = [];

  if (groupLabel) {
    breadcrumbs.push({ label: groupLabel });
  }

  for (const item of trail) {
    breadcrumbs.push({
      label: item.title,
      path: item.path,
    });
  }

  return breadcrumbs.length ? breadcrumbs : [{ label: typeof route.meta.title === "string" ? route.meta.title : "\u5f53\u524d\u9875\u9762" }];
});

const showDatasetContextInTopbar = computed(
  () =>
    !isAdmin.value &&
    ["/workbench", "/datasets", "/analysis", "/algo-radar"].some((prefix) => route.path === prefix || route.path.startsWith(`${prefix}/`))
);

const currentContextBatch = computed(() => {
  if (!datasetContext.state.importRunId) {
    return "\u672A\u9009\u62E9";
  }

  return `#${datasetContext.state.importRunDisplayId ?? datasetContext.state.importRunId}`;
});

const currentContextStock = computed(() => datasetContext.state.stockCode || "\u5168\u90E8\u80A1\u7968");
const currentContextDateRange = computed(
  () => `${datasetContext.state.startDate || "\u8D77\u59CB\u4E0D\u9650"} ~ ${datasetContext.state.endDate || "\u7ED3\u675F\u4E0D\u9650"}`
);

const topbarContextItems = computed(() => {
  if (!showDatasetContextInTopbar.value) {
    return [];
  }

  return [
    {
      label: "\u5F53\u524D\u6279\u6B21",
      value: currentContextBatch.value,
    },
    {
      label: "\u5F53\u524D\u80A1\u7968",
      value: currentContextStock.value,
    },
    {
      label: "\u65E5\u671F\u8303\u56F4",
      value: currentContextDateRange.value,
    },
  ];
});

const showUnifiedFilterButton = computed(() => showDatasetContextInTopbar.value);

const dropdownOptions = computed(() => [
  {
    label: `\u9000\u51fa\u767b\u5f55 (${auth.state.user?.username || "\u5f53\u524d\u7528\u6237"})`,
    key: "logout",
  },
]);

function toCompactTitle(title: string) {
  return title.includes("/") ? title.split("/").at(-1)?.trim() || title : title;
}

function resolveNavigationTitle(path: string, fallbackTitle = "") {
  const items = menuGroups.value[0]?.items ?? [];
  const trail = findMenuTrail(path, items);
  const menuTitle = trail.at(-1)?.title;
  return menuTitle || toCompactTitle(fallbackTitle);
}

function isItemActive(path: string) {
  return route.path === path || route.path.startsWith(`${path}/`);
}

function toMenuOption(item: NavItem): MenuOption {
  return {
    key: item.key,
    title: item.title,
    path: item.path,
    iconComponent: item.iconComponent,
    props: {
      title: item.title,
    },
    children: item.children?.map((child) => toMenuOption(child)),
  };
}

function renderMenuLabel(option: MenuOption) {
  const title = typeof option.title === "string" ? option.title : typeof option.label === "string" ? option.label : "";
  return h("span", { class: "shell__menu-title", title }, title);
}

function renderMenuIcon(option: MenuOption) {
  const icon = option.iconComponent;
  if (!icon) {
    return null;
  }
  return h(NIcon, { size: 18 }, { default: () => h(icon as never) });
}

function flattenNavItems(items: NavItem[], trail: string[] = []): SearchEntry[] {
  return items.flatMap((item) => {
    const nextTrail = [...trail, item.title];
    const currentEntries: SearchEntry[] = item.path
      ? [
          {
            key: `menu:${item.path}`,
            title: item.title,
            path: item.path,
            trail: nextTrail,
            source: "menu",
          },
        ]
      : [];

    return [...currentEntries, ...(item.children ? flattenNavItems(item.children, nextTrail) : [])];
  });
}

function findMenuTrail(targetPath: string, items: NavItem[], trail: NavItem[] = []): NavItem[] {
  for (const item of items) {
    const nextTrail = [...trail, item];
    if (item.path === targetPath) {
      return nextTrail;
    }
    if (item.children?.length) {
      const matched = findMenuTrail(targetPath, item.children, nextTrail);
      if (matched.length) {
        return matched;
      }
    }
  }
  return [];
}

function findAncestorKeys(targetPath: string, items: NavItem[], ancestors: string[] = []): string[] {
  for (const item of items) {
    if (item.path === targetPath) {
      return ancestors;
    }
    if (item.children?.length) {
      const matched = findAncestorKeys(targetPath, item.children, [...ancestors, item.key]);
      if (matched.length || item.children.some((child) => child.path === targetPath)) {
        return matched;
      }
    }
  }
  return [];
}

function syncExpandedMenuKeys() {
  const items = menuGroups.value[0]?.items ?? [];
  const ancestorKeys = findAncestorKeys(route.path, items);
  const merged = new Set<string>([...expandedMenuKeys.value, ...ancestorKeys]);
  expandedMenuKeys.value = Array.from(merged);
}

function toggleMenuKey(key: string) {
  if (expandedMenuKeys.value.includes(key)) {
    expandedMenuKeys.value = expandedMenuKeys.value.filter((item) => item !== key);
    return;
  }
  expandedMenuKeys.value = [...expandedMenuKeys.value, key];
}

function handleMenuValue(value: string | number, item: MenuOption) {
  const key = String(value);
  if (Array.isArray(item.children) && item.children.length) {
    toggleMenuKey(key);
    return;
  }
  const path = typeof item.path === "string" ? item.path : key;
  openRoute(path);
}

function handleExpandedKeysUpdate(keys: Array<string | number>) {
  expandedMenuKeys.value = keys.map((item) => String(item));
}

const quickSearchEntries = computed<SearchEntry[]>(() => {
  const menuEntries = flattenNavItems(menuGroups.value[0]?.items ?? []);
  const tabEntries: SearchEntry[] = tabs.value.map((item) => ({
    key: `tab:${item.path}`,
    title: resolveNavigationTitle(item.path, item.title),
    path: item.path,
    trail: [resolveNavigationTitle(item.path, item.title)],
    source: "tab",
  }));
  const merged = new Map<string, SearchEntry>();
  [...tabEntries, ...menuEntries].forEach((item) => {
    merged.set(item.path, item);
  });
  return Array.from(merged.values());
});

const filteredSearchEntries = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return [];
  }
  return quickSearchEntries.value.filter((item) => {
    const haystack = [item.title, ...item.trail, item.path].join(" ").toLowerCase();
    return haystack.includes(keyword);
  });
});

const visibleSearchEntries = computed(() => filteredSearchEntries.value.slice(0, 8));
const activeSearchEntry = computed(() => visibleSearchEntries.value[activeSearchIndex.value] ?? null);
const hasSearchKeyword = computed(() => Boolean(searchKeyword.value.trim()));

const statusHasAttention = computed(() => runtime.syncStatusText.value !== "\u5df2\u540c\u6b65" || Boolean(routeRenderError.value));
const algoIndexStatusTagType = computed(() => (runtime.state.algoIndexStatus?.statusText === "\u5c31\u7eea" ? "success" : "warning"));

function syncViewport() {
  if (typeof window === "undefined") {
    return;
  }

  isMobile.value = window.innerWidth < 960;
  if (!isMobile.value) {
    layout.closeMobileSidebar();
  }
}

function toggleNavigation() {
  if (isMobile.value) {
    if (layout.state.mobileSidebarOpen) {
      layout.closeMobileSidebar();
    } else {
      layout.openMobileSidebar();
    }
    return;
  }

  layout.toggleSidebarCollapsed();
}

function openRoute(path: string) {
  layout.closeMobileSidebar();
  void router.push(path);
}

function openSearchModal() {
  searchKeyword.value = "";
  activeSearchIndex.value = 0;
  searchModalVisible.value = true;
  void nextTick(() => {
    searchInputRef.value?.focus();
  });
}

function openFilterDrawer(event?: MouseEvent) {
  (event?.currentTarget as HTMLElement | null)?.blur();
  filterDrawerVisible.value = true;
}

function closeSearchModal() {
  searchModalVisible.value = false;
  searchKeyword.value = "";
  activeSearchIndex.value = 0;
}

function handleSearchSelect(path: string) {
  closeSearchModal();
  openRoute(path);
}

function moveSearchSelection(direction: 1 | -1) {
  if (!visibleSearchEntries.value.length) {
    activeSearchIndex.value = 0;
    return;
  }

  const lastIndex = visibleSearchEntries.value.length - 1;
  if (direction > 0) {
    activeSearchIndex.value = activeSearchIndex.value >= lastIndex ? 0 : activeSearchIndex.value + 1;
    return;
  }

  activeSearchIndex.value = activeSearchIndex.value <= 0 ? lastIndex : activeSearchIndex.value - 1;
}

function handleSearchConfirm() {
  const target = activeSearchEntry.value ?? visibleSearchEntries.value[0];
  if (!target) {
    return;
  }
  handleSearchSelect(target.path);
}

function handleSearchInputKeydown(event: KeyboardEvent) {
  if (event.key === "ArrowDown") {
    event.preventDefault();
    moveSearchSelection(1);
    return;
  }

  if (event.key === "ArrowUp") {
    event.preventDefault();
    moveSearchSelection(-1);
    return;
  }

  if (event.key === "Enter") {
    event.preventDefault();
    handleSearchConfirm();
    return;
  }

  if (event.key === "Escape") {
    event.preventDefault();
    closeSearchModal();
  }
}

function closeTab(path: string) {
  const targetTab = tabs.value.find((item) => item.path === path);
  if (targetTab?.affix) {
    return;
  }

  layout.removeTab(path);

  if (route.path === path) {
    const fallback = tabs.value[tabs.value.length - 1];
    void router.push(fallback?.path || defaultPath.value);
  }
}

function handleDropdownSelect(key: string) {
  if (key === "logout") {
    auth.clearSession();
    datasetContext.resetScope();
    layout.resetLayout();
    runtime.setAlgoIndexStatus(null);
    void router.replace("/login");
  }
}

async function refreshAlgoIndexStatus(importRunId: number | undefined) {
  const requestId = ++algoIndexStatusRequestId;
  if (!importRunId || !auth.state.accessToken) {
    runtime.setAlgoIndexStatus(null);
    return;
  }

  try {
    const status = await fetchAlgoIndexStatus({ import_run_id: importRunId });
    if (requestId !== algoIndexStatusRequestId) {
      return;
    }
    runtime.setAlgoIndexStatus({
      statusText: formatStatusText(status.status),
      completedAtText: status.build_completed_at ? formatDateTime(status.build_completed_at) : "",
      stockCount: status.stock_count ?? null,
    });
  } catch {
    if (requestId === algoIndexStatusRequestId) {
      runtime.setAlgoIndexStatus(null);
    }
  }
}

function buildRenderErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message || "\u9875\u9762\u6e32\u67d3\u5f02\u5e38\uff0c\u8bf7\u5237\u65b0\u540e\u91cd\u8bd5\u3002";
  }
  return String(error || "\u9875\u9762\u6e32\u67d3\u5f02\u5e38\uff0c\u8bf7\u5237\u65b0\u540e\u91cd\u8bd5\u3002");
}

function reloadCurrentPage() {
  if (typeof window !== "undefined") {
    window.location.reload();
  }
}

function syncFullscreenState() {
  if (typeof document === "undefined") {
    return;
  }
  isFullscreen.value = Boolean(document.fullscreenElement);
}

async function toggleFullscreen() {
  if (typeof document === "undefined") {
    return;
  }
  if (document.fullscreenElement) {
    await document.exitFullscreen();
    return;
  }
  await document.documentElement.requestFullscreen();
}

function handleGlobalKeydown(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    if (searchModalVisible.value) {
      void nextTick(() => {
        searchInputRef.value?.focus();
      });
      return;
    }
    openSearchModal();
  }

  if (event.key === "Escape" && searchModalVisible.value) {
    event.preventDefault();
    closeSearchModal();
  }
}

watch(searchKeyword, () => {
  activeSearchIndex.value = 0;
});

watch(visibleSearchEntries, (entries) => {
  if (!entries.length) {
    activeSearchIndex.value = 0;
    return;
  }

  if (activeSearchIndex.value > entries.length - 1) {
    activeSearchIndex.value = entries.length - 1;
  }
});

watch(
  allowedTabPaths,
  (paths) => {
    layout.pruneTabs(paths);
  },
  { immediate: true }
);

watch(
  [() => datasetContext.state.importRunId, () => auth.state.accessToken],
  ([importRunId]) => {
    void refreshAlgoIndexStatus(importRunId);
  },
  { immediate: true }
);

watch(
  () => route.fullPath,
  () => {
    routeRenderError.value = "";
    const title = resolveNavigationTitle(route.path, typeof route.meta.title === "string" ? route.meta.title : "");
    layout.visitTab({
      path: route.path,
      title,
      affix: Boolean(route.meta.affix) || route.path === "/admin/assets",
    });
    layout.closeMobileSidebar();
    syncExpandedMenuKeys();
  },
  { immediate: true }
);

onErrorCaptured((error) => {
  routeRenderError.value = buildRenderErrorMessage(error);
  if (import.meta.env.DEV) {
    console.error("[app-shell] route render error", error);
  }
  return false;
});

onMounted(() => {
  syncViewport();
  syncFullscreenState();
  window.addEventListener("resize", syncViewport);
  window.addEventListener("keydown", handleGlobalKeydown);
  document.addEventListener("fullscreenchange", syncFullscreenState);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", syncViewport);
  window.removeEventListener("keydown", handleGlobalKeydown);
  document.removeEventListener("fullscreenchange", syncFullscreenState);
});
</script>

<template>
  <div class="shell">
    <div
      v-if="layout.state.mobileSidebarOpen && isMobile"
      class="shell__backdrop"
      @click="layout.closeMobileSidebar"
    />

    <aside
      class="shell__sidebar"
      :class="{
        'shell__sidebar--collapsed': layout.state.sidebarCollapsed && !isMobile,
        'shell__sidebar--mobile-open': layout.state.mobileSidebarOpen && isMobile,
      }"
    >
      <div class="shell__brand">
        <div class="shell__brand-logo-wrap">
          <img class="shell__brand-logo" :src="logo" :alt="APP_BRAND_NAME" />
        </div>
        <div v-if="!layout.state.sidebarCollapsed || isMobile" class="shell__brand-copy">
          <div class="shell__brand-title">{{ APP_BRAND_NAME }}</div>
          <div class="shell__brand-subtitle">{{ brandSubtitle }}</div>
        </div>
      </div>

      <div class="shell__nav">
        <section v-for="group in menuGroups" :key="group.label" class="shell__group">
          <div v-if="!layout.state.sidebarCollapsed || isMobile" class="shell__group-label">{{ group.label }}</div>
          <n-menu
            :options="menuOptions"
            :value="route.path"
            :expanded-keys="expandedMenuKeys"
            :collapsed="layout.state.sidebarCollapsed && !isMobile"
            :collapsed-width="72"
            :collapsed-icon-size="20"
            :indent="20"
            :render-label="renderMenuLabel"
            :render-icon="renderMenuIcon"
            @update:value="handleMenuValue"
            @update:expanded-keys="handleExpandedKeysUpdate"
          />
        </section>
      </div>
    </aside>

    <div class="shell__main">
      <header class="shell__topbar">
        <div class="shell__topbar-left">
          <n-button quaternary circle @click="toggleNavigation">
            <template #icon>
              <n-icon size="18">
                <MenuOutline />
              </n-icon>
            </template>
          </n-button>

          <div class="shell__crumbs">
            <template v-for="(item, index) in breadcrumbs" :key="`${item.label}-${index}`">
              <button
                v-if="item.path"
                type="button"
                class="shell__crumb shell__crumb--button"
                @click="openRoute(item.path)"
              >
                {{ item.label }}
              </button>
              <span v-else class="shell__crumb">{{ item.label }}</span>
              <span v-if="index < breadcrumbs.length - 1" class="shell__crumb-separator">/</span>
            </template>
          </div>
        </div>

        <div v-if="topbarContextItems.length" class="shell__topbar-context" aria-label="dataset context">
          <span v-for="item in topbarContextItems" :key="item.label" class="shell__context-chip">
            <span class="shell__context-label">{{ item.label }}</span>
            <span class="shell__context-value">{{ item.value }}</span>
          </span>
        </div>

        <div class="shell__topbar-right">
          <div class="shell__tool-row">
            <div v-if="showUnifiedFilterButton" class="shell__tool-item">
              <button type="button" class="shell__tool-btn" @click="openFilterDrawer">
                <n-icon size="18"><FunnelOutline /></n-icon>
              </button>
              <span class="shell__tool-tip">筛选器</span>
            </div>

            <div class="shell__tool-item">
              <button type="button" class="shell__tool-btn" @click="openSearchModal">
                <n-icon size="18"><SearchOutline /></n-icon>
              </button>
              <span class="shell__tool-tip">&#x641C;&#x7D22;</span>
            </div>

            <div class="shell__tool-item">
              <button type="button" class="shell__tool-btn" @click="toggleFullscreen">
                <n-icon size="18">
                  <component :is="isFullscreen ? ContractOutline : ExpandOutline" />
                </n-icon>
              </button>
              <span class="shell__tool-tip">{{ isFullscreen ? '\u9000\u51fa\u5168\u5c4f' : '\u5168\u5c4f' }}</span>
            </div>

            <div class="shell__tool-item">
              <n-popover trigger="click" placement="bottom-end">
                <template #trigger>
                  <button type="button" class="shell__tool-btn">
                    <n-badge dot :show="statusHasAttention">
                      <n-icon size="18"><NotificationsOutline /></n-icon>
                    </n-badge>
                  </button>
                </template>
                <div class="shell__status-panel">
                  <div class="shell__status-row">
                    <span class="shell__status-label">&#x5F53;&#x524D;&#x9875;&#x9762;</span>
                    <span>{{ breadcrumbs.map((item) => item.label).join(" / ") }}</span>
                  </div>
                  <div class="shell__status-row">
                    <span class="shell__status-label">&#x7CFB;&#x7EDF;&#x72B6;&#x6001;</span>
                    <n-tag size="small" :type="runtime.syncStatusText.value === '\u5df2\u540c\u6b65' ? 'success' : 'warning'">
                      {{ runtime.syncStatusText }}
                    </n-tag>
                  </div>
                  <div class="shell__status-row">
                    <span class="shell__status-label">&#x6700;&#x8FD1;&#x540C;&#x6B65;</span>
                    <span>{{ runtime.lastSyncText }}</span>
                  </div>
                  <div v-if="runtime.state.algoIndexStatus" class="shell__status-row">
                    <span class="shell__status-label">算法索引</span>
                    <n-tag size="small" :type="algoIndexStatusTagType">
                      {{ runtime.state.algoIndexStatus.statusText }}
                    </n-tag>
                  </div>
                  <div v-if="runtime.state.algoIndexStatus?.completedAtText" class="shell__status-row">
                    <span class="shell__status-label">索引完成</span>
                    <span>{{ runtime.state.algoIndexStatus.completedAtText }}</span>
                  </div>
                  <div v-if="runtime.state.algoIndexStatus?.stockCount !== null && runtime.state.algoIndexStatus?.stockCount !== undefined" class="shell__status-row">
                    <span class="shell__status-label">索引股票</span>
                    <span>{{ runtime.state.algoIndexStatus.stockCount }}</span>
                  </div>
                  <div class="shell__status-row">
                    <span class="shell__status-label">&#x6253;&#x5F00;&#x9875;&#x7B7E;</span>
                    <span>{{ tabs.length }}</span>
                  </div>
                </div>
              </n-popover>
              <span class="shell__tool-tip">&#x7CFB;&#x7EDF;&#x72B6;&#x6001;</span>
            </div>
          </div>
          <n-dropdown trigger="click" :options="dropdownOptions" @select="handleDropdownSelect">
            <button type="button" class="shell__user">
              <n-icon class="shell__user-icon" :component="PersonCircleOutline" />
              <span class="shell__user-copy">
                <strong>{{ auth.state.user?.username || "\u672a\u767b\u5f55" }}</strong>
                <span>{{ auth.state.user?.role ? formatRoleText(auth.state.user.role) : "--" }}</span>
              </span>
            </button>
          </n-dropdown>
        </div>
      </header>

        <div class="shell__tabs">
          <button
            v-for="item in tabs"
            :key="item.path"
            type="button"
            class="shell__tab"
            :class="{ 'shell__tab--active': route.path === item.path }"
            @click="openRoute(item.path)"
          >
            <span>{{ resolveNavigationTitle(item.path, item.title) }}</span>
            <span v-if="!item.affix" class="shell__tab-close" @click.stop="closeTab(item.path)">&times;</span>
          </button>
        </div>

      <main class="shell__content">
        <n-alert
          v-if="routeRenderError"
          title="&#x9875;&#x9762;&#x6E32;&#x67D3;&#x5931;&#x8D25;"
          type="error"
          :show-icon="true"
          class="shell__route-error"
        >
          <div>{{ routeRenderError }}</div>
          <div class="toolbar-row" style="margin-top: 10px;">
            <n-button size="small" @click="reloadCurrentPage">&#x5237;&#x65B0;&#x9875;&#x9762;</n-button>
          </div>
        </n-alert>
        <RouterView v-else />
      </main>
    </div>

    <div v-if="searchModalVisible" class="shell__search-overlay" @click.self="closeSearchModal">
      <div class="shell__search-shell">
        <div class="shell__search-panel" role="dialog" aria-modal="true">
          <div class="shell__search-body">
            <n-input
              ref="searchInputRef"
              v-model:value="searchKeyword"
              class="shell__search-input"
              placeholder="&#x8BF7;&#x8F93;&#x5165;&#x5173;&#x952E;&#x8BCD;&#x641C;&#x7D22;&#x83DC;&#x5355;&#x6216;&#x9875;&#x9762;"
              clearable
              @keydown="handleSearchInputKeydown"
            >
              <template #prefix>
                <n-icon size="18" color="rgba(100, 116, 139, 0.72)">
                  <SearchOutline />
                </n-icon>
              </template>
            </n-input>

            <div class="shell__search-caption">&#x641C;&#x7D22;&#x8303;&#x56F4;&#xFF1A;&#x4FA7;&#x8FB9;&#x680F;&#x83DC;&#x5355;&#x4E0E;&#x5F53;&#x524D;&#x5DF2;&#x6253;&#x5F00;&#x9875;&#x7B7E;</div>

            <div class="shell__search-result-wrap">
              <n-scrollbar class="shell__search-scrollbar">
                <div v-if="visibleSearchEntries.length" class="shell__search-results">
                  <button
                    v-for="(item, index) in visibleSearchEntries"
                    :key="item.key"
                    type="button"
                    class="shell__search-result"
                    :class="{ 'shell__search-result--active': index === activeSearchIndex }"
                    @mouseenter="activeSearchIndex = index"
                    @click="handleSearchSelect(item.path)"
                  >
                    <div class="shell__search-result-main">
                      <div class="shell__search-result-title">
                        <n-icon size="16" color="var(--accent-blue)">
                          <ListOutline />
                        </n-icon>
                        <span>{{ item.title }}</span>
                      </div>
                      <div class="shell__search-item-path">{{ item.trail.join(" / ") }}</div>
                    </div>
                    <n-tag size="small" round :type="item.source === 'tab' ? 'warning' : 'info'">
                      {{ item.source === "tab" ? '\u9875\u7b7e' : '\u83dc\u5355' }}
                    </n-tag>
                  </button>
                </div>
                <div v-else-if="hasSearchKeyword" class="shell__search-empty">&#x6682;&#x65E0;&#x641C;&#x7D22;&#x7ED3;&#x679C;</div>
                <div v-else class="shell__search-placeholder">&#x8F93;&#x5165;&#x5173;&#x952E;&#x8BCD;&#x540E;&#x53EF;&#x5FEB;&#x901F;&#x5B9A;&#x4F4D;&#x83DC;&#x5355;&#x9875;&#x9762;&#x6216;&#x5DF2;&#x6253;&#x5F00;&#x9875;&#x7B7E;</div>
              </n-scrollbar>
            </div>

            <div class="shell__search-footer">
              <div class="shell__search-shortcuts">
                <span class="shell__shortcut">
                  <kbd>Enter</kbd>
                  <span>&#x786E;&#x8BA4;</span>
                </span>
                <span class="shell__shortcut">
                  <kbd>Up</kbd>
                  <kbd>Down</kbd>
                  <span>&#x5207;&#x6362;</span>
                </span>
                <span class="shell__shortcut">
                  <kbd>Esc</kbd>
                  <span>&#x5173;&#x95ED;</span>
                </span>
              </div>
              <div v-if="visibleSearchEntries.length" class="shell__search-count">
                {{ activeSearchIndex + 1 }} / {{ visibleSearchEntries.length }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <UnifiedFilterDrawer v-if="showUnifiedFilterButton" v-model:show="filterDrawerVisible" />
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  display: flex;
}

.shell__backdrop {
  position: fixed;
  inset: 0;
  z-index: 39;
  background: rgba(15, 23, 42, 0.38);
}

.shell__sidebar {
  position: sticky;
  top: 0;
  z-index: 40;
  width: var(--shell-sidebar-width);
  min-width: var(--shell-sidebar-width);
  height: 100vh;
  padding: 20px 14px;
  border-right: 1px solid var(--panel-border);
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(16px);
  transition:
    width 0.2s ease,
    min-width 0.2s ease,
    transform 0.2s ease;
}

.shell__sidebar--collapsed {
  width: var(--shell-sidebar-collapsed-width);
  min-width: var(--shell-sidebar-collapsed-width);
}

.shell__brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 10px 18px;
}

.shell__brand-logo-wrap {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  overflow: hidden;
  background: #fff;
  border: 1px solid rgba(82, 96, 114, 0.14);
  box-shadow: 0 12px 30px rgba(240, 90, 40, 0.22);
  flex-shrink: 0;
}

.shell__brand-logo {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.shell__brand-copy {
  min-width: 0;
}

.shell__brand-title {
  font-size: 15px;
  font-weight: 700;
}

.shell__brand-subtitle {
  margin-top: 4px;
  color: var(--text-soft);
  font-size: 12px;
}

.shell__nav {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin-top: 10px;
}

.shell__group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.shell__group-label {
  padding: 0 10px;
  color: var(--text-soft);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.shell__nav :deep(.n-menu) {
  background: transparent;
}

.shell__nav :deep(.n-menu-item),
.shell__nav :deep(.n-submenu) {
  margin-top: 10px;
}

.shell__nav :deep(.n-menu-item-content),
.shell__nav :deep(.n-menu-item-content-header) {
  min-height: 48px;
  box-sizing: border-box;
  padding-left: 12px !important;
  padding-right: 12px !important;
}

.shell__nav :deep(.n-menu-item-content),
.shell__nav :deep(.n-submenu-children .n-menu-item-content),
.shell__nav :deep(.n-submenu-children .n-menu-item-content-header),
.shell__nav :deep(.n-submenu .n-menu-item-content-header) {
  border-radius: 8px;
}

.shell__nav :deep(.n-menu-item-content::before),
.shell__nav :deep(.n-menu-item-content-header::before) {
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  border-radius: 8px;
  border: 0;
  background: transparent;
  box-shadow: none;
}

.shell__nav :deep(.n-menu-item-content--selected),
.shell__nav :deep(.n-menu-item-content-header--active) {
  color: var(--accent-primary);
}

.shell__nav :deep(.n-menu-item-content:hover::before),
.shell__nav :deep(.n-menu-item-content-header:hover::before) {
  background: rgba(15, 23, 42, 0.035);
}

.shell__nav :deep(.n-submenu-children) {
  margin: 8px 0 2px 22px;
  padding-left: 0;
  border-left: 0;
}

.shell__nav :deep(.n-submenu-children .n-menu-item),
.shell__nav :deep(.n-submenu-children .n-submenu) {
  margin-top: 4px;
}

.shell__nav :deep(.n-submenu-children .n-menu-item-content),
.shell__nav :deep(.n-submenu-children .n-menu-item-content-header) {
  min-height: 42px;
  padding-left: 18px !important;
  padding-right: 14px !important;
}

.shell__nav :deep(.n-submenu-children .n-menu-item-content::before),
.shell__nav :deep(.n-submenu-children .n-menu-item-content-header::before) {
  background: transparent;
}

.shell__nav :deep(.n-submenu-children .n-menu-item-content:hover::before),
.shell__nav :deep(.n-submenu-children .n-menu-item-content-header:hover::before) {
  background: rgba(79, 70, 229, 0.04);
}

.shell__nav :deep(.n-menu-item-content--selected::before),
.shell__nav :deep(.n-menu-item-content-header--active::before) {
  background: rgba(79, 70, 229, 0.10);
  box-shadow: none;
}

.shell__nav :deep(.n-menu-item-content-header--active::before) {
  background: transparent;
}

.shell__nav :deep(.n-submenu-children .n-menu-item-content--selected::before) {
  background: rgba(79, 70, 229, 0.12);
}

.shell__nav :deep(.n-menu-item-content__icon),
.shell__nav :deep(.n-menu-item-content__arrow) {
  width: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.shell__nav :deep(.n-menu-item-content__icon) {
  color: rgba(15, 23, 42, 0.88);
}

.shell__nav :deep(.n-menu-item-content__arrow) {
  color: rgba(15, 23, 42, 0.72);
}

.shell__nav :deep(.n-menu-item-content--selected .n-menu-item-content__icon),
.shell__nav :deep(.n-menu-item-content-header--active .n-menu-item-content__icon),
.shell__nav :deep(.n-menu-item-content-header--active .n-menu-item-content__arrow) {
  color: #4f46e5;
}

.shell__nav :deep(.n-menu-item-content-header),
.shell__nav :deep(.n-menu-item-content) {
  align-items: center;
}

.shell__nav :deep(.n-menu-item-content-header .n-menu-item-content-header__content) {
  display: flex;
  align-items: center;
  justify-content: flex-start;
}

.shell__menu-title {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  width: 100%;
  min-height: 100%;
  font-weight: 700;
  font-size: 15px;
  line-height: 1;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.shell__main {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.shell__topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  height: var(--shell-header-height);
  padding: 0 22px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 16px;
  border-bottom: 1px solid var(--panel-border);
  background: rgba(244, 247, 251, 0.88);
  backdrop-filter: blur(16px);
}

.shell__topbar-left,
.shell__topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.shell__topbar-right {
  margin-left: auto;
}

.shell__topbar-context {
  min-width: 0;
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  overflow-x: auto;
  scrollbar-width: none;
}

.shell__topbar-context::-webkit-scrollbar {
  display: none;
}

.shell__context-chip {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(82, 96, 114, 0.10);
  background: rgba(255, 255, 255, 0.9);
  color: var(--text-secondary);
  font-size: 12px;
  white-space: nowrap;
  flex-shrink: 0;
}

.shell__context-label {
  color: var(--text-soft);
  font-weight: 700;
}

.shell__context-value {
  min-width: 0;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.shell__tool-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-right: 14px;
  margin-right: 4px;
  border-right: 1px solid var(--panel-border);
}

.shell__tool-item {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.shell__tool-btn {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(82, 96, 114, 0.10);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
  color: var(--text-secondary);
  cursor: pointer;
  transition:
    transform 0.18s ease,
    background 0.18s ease,
    color 0.18s ease,
    border-color 0.18s ease;
}

.shell__tool-btn:hover {
  transform: translateY(-1px);
  color: var(--accent-primary);
  background: rgba(255, 255, 255, 0.98);
  border-color: rgba(240, 90, 40, 0.16);
}

.shell__tool-tip {
  position: absolute;
  top: calc(100% + 12px);
  left: 50%;
  z-index: 12;
  transform: translateX(-50%) translateY(-4px);
  padding: 10px 14px;
  border-radius: 8px;
  background: rgba(28, 30, 36, 0.96);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.22);
  color: #ffffff;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition:
    opacity 0.16s ease,
    transform 0.16s ease,
    visibility 0.16s ease;
}

.shell__tool-tip::before {
  content: "";
  position: absolute;
  left: 50%;
  bottom: calc(100% - 2px);
  width: 10px;
  height: 10px;
  transform: translateX(-50%) rotate(45deg);
  background: rgba(28, 30, 36, 0.96);
}

.shell__tool-item:hover .shell__tool-tip,
.shell__tool-item:focus-within .shell__tool-tip {
  opacity: 1;
  visibility: visible;
  transform: translateX(-50%) translateY(0);
}

.shell__status-panel {
  min-width: 280px;
  display: grid;
  gap: 12px;
}

.shell__status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-secondary);
  font-size: 13px;
}

.shell__status-label {
  color: var(--text-soft);
  font-weight: 700;
}

.shell__search-body {
  display: grid;
  gap: 14px;
  width: 100%;
}

.shell__search-shell {
  width: min(700px, calc(100vw - 32px));
  max-width: 100%;
}

.shell__search-overlay {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 78px 16px 24px;
  background: rgba(15, 23, 42, 0.34);
  backdrop-filter: blur(3px);
}

.shell__search-panel {
  width: 100%;
  padding: 18px 18px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.985);
  box-shadow:
    0 20px 44px rgba(15, 23, 42, 0.18),
    0 4px 12px rgba(15, 23, 42, 0.08);
  border: 1px solid rgba(129, 140, 162, 0.14);
}

.shell__search-input {
  width: 100%;
}

.shell__search-input :deep(.n-input) {
  width: 100%;
  border-radius: 14px;
}

.shell__search-input :deep(.n-input-wrapper) {
  min-height: 52px;
  padding-left: 14px;
  padding-right: 14px;
}

.shell__search-input :deep(.n-input__input-el) {
  font-size: 15px;
}

.shell__search-caption {
  padding: 0 2px;
  color: var(--text-soft);
  font-size: 12px;
}

.shell__search-result-wrap {
  width: 100%;
  min-height: 0;
  max-height: 248px;
}

.shell__search-scrollbar {
  max-height: 248px;
}

.shell__search-results {
  display: grid;
  gap: 10px;
  width: 100%;
}

.shell__search-result {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 14px;
  border: 1px solid transparent;
  border-radius: 14px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background 0.18s ease,
    color 0.18s ease,
    transform 0.18s ease,
    box-shadow 0.18s ease;
}

.shell__search-result:hover,
.shell__search-result--active {
  border-color: rgba(88, 196, 146, 0.28);
  background: linear-gradient(135deg, #dff7eb 0%, #c8f1dd 100%);
  color: #20543c;
  box-shadow: 0 14px 28px rgba(88, 196, 146, 0.18);
  transform: translateY(-1px);
}

.shell__search-result-main {
  min-width: 0;
  display: grid;
  gap: 6px;
}

.shell__search-result-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
}

.shell__search-result--active .shell__search-result-title,
.shell__search-result:hover .shell__search-result-title,
.shell__search-result--active :deep(.n-tag),
.shell__search-result:hover :deep(.n-tag) {
  color: #20543c;
}

.shell__search-item-path {
  color: var(--text-soft);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.shell__search-result--active .shell__search-item-path,
.shell__search-result:hover .shell__search-item-path {
  color: rgba(32, 84, 60, 0.72);
}

.shell__search-result :deep(.n-tag) {
  transition:
    background 0.18s ease,
    color 0.18s ease,
    border-color 0.18s ease;
}

.shell__search-result--active :deep(.n-tag),
.shell__search-result:hover :deep(.n-tag) {
  border-color: rgba(88, 196, 146, 0.32);
  background: rgba(255, 255, 255, 0.66);
}

.shell__search-placeholder {
  padding: 8px 4px 2px;
  color: var(--text-soft);
  font-size: 13px;
}

.shell__search-empty {
  min-height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(148, 163, 184, 0.92);
  font-size: 15px;
  font-weight: 600;
}

.shell__search-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
  margin-top: 4px;
  padding-top: 12px;
  border-top: 1px solid rgba(226, 232, 240, 0.92);
}

.shell__search-shortcuts {
  display: flex;
  align-items: center;
  gap: 18px;
  flex-wrap: wrap;
}

.shell__shortcut {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-soft);
  font-size: 12px;
}

.shell__shortcut kbd {
  min-width: 28px;
  height: 24px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-bottom-width: 2px;
  border-radius: 8px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  box-shadow: 0 3px 8px rgba(15, 23, 42, 0.08);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  font-family: inherit;
}

.shell__search-count {
  color: var(--text-soft);
  font-size: 12px;
  font-weight: 700;
}

.shell__crumbs {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.shell__crumb {
  color: var(--text-secondary);
  font-size: 13px;
}

.shell__crumb--button {
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}

.shell__crumb--button:hover {
  color: var(--accent-primary);
}

.shell__crumb-separator {
  color: var(--text-soft);
}

.shell__meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  border-radius: 999px;
  border: 1px solid var(--panel-border);
  background: rgba(255, 255, 255, 0.88);
  color: var(--text-secondary);
  font-size: 12px;
}

.shell__meta-chip--wide {
  max-width: 280px;
}

.shell__meta-label {
  font-weight: 700;
  color: var(--text-soft);
}

.shell__user {
  display: inline-flex;
  align-items: center;
  gap: 14px;
  padding: 4px 6px;
  border: 0;
  background: transparent;
  color: var(--text-primary);
  cursor: pointer;
}

.shell__user-icon {
  flex: 0 0 auto;
  width: 40px;
  height: 40px;
  font-size: 40px;
  color: rgba(15, 23, 42, 0.82);
}

.shell__user-copy {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}

.shell__user-copy strong {
  font-size: 14px;
}

.shell__user-copy span {
  color: var(--text-soft);
  font-size: 12px;
}

.shell__tabs {
  display: flex;
  align-items: center;
  gap: 10px;
  overflow-x: auto;
  padding: 16px 22px 0;
}

.shell__tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border: 1px solid var(--panel-border);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
  color: var(--text-secondary);
  cursor: pointer;
  white-space: nowrap;
}

.shell__tab--active {
  border-color: rgba(240, 90, 40, 0.25);
  background: rgba(240, 90, 40, 0.12);
  color: var(--accent-primary);
}

.shell__tab-close {
  font-size: 16px;
  line-height: 1;
}

.shell__content {
  padding: 22px;
}

.shell__route-error {
  border-radius: 18px;
}

@media (max-width: 1200px) {
  .shell__meta-chip--wide {
    display: none;
  }
}

@media (max-width: 959px) {
  .shell__sidebar {
    position: fixed;
    left: 0;
    transform: translateX(-100%);
    box-shadow: 0 20px 60px rgba(15, 23, 42, 0.18);
  }

  .shell__sidebar--mobile-open {
    transform: translateX(0);
  }

  .shell__topbar {
    padding: 0 16px;
  }

  .shell__content {
    padding: 18px 16px 24px;
  }
}

@media (max-width: 760px) {
  .shell__topbar-right {
    gap: 8px;
  }

  .shell__search-overlay {
    padding-top: 60px;
  }

  .shell__search-panel {
    padding: 16px 14px 14px;
  }

  .shell__search-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .shell__topbar-context {
    display: none;
  }

  .shell__meta-chip {
    display: none;
  }

  .shell__user-copy {
    display: none;
  }
}
</style>
