<script setup lang="ts">
import { computed, onBeforeUnmount, onErrorCaptured, onMounted, ref, watch } from "vue";

import {
  DocumentTextOutline,
  FolderOpenOutline,
  GridOutline,
  MenuOutline,
  PeopleOutline,
  PodiumOutline,
  PulseOutline,
  ServerOutline,
  SpeedometerOutline,
  StatsChartOutline,
} from "@vicons/ionicons5";
import { NAlert, NAvatar, NButton, NDropdown, NIcon } from "naive-ui";
import { RouterView, useRoute, useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";
import { useDatasetContextStore } from "@/stores/datasetContext";
import { useLayoutStore } from "@/stores/layout";
import { useRuntimeStore } from "@/stores/runtime";


interface NavItem {
  title: string;
  subtitle: string;
  path: string;
  icon: unknown;
}

interface BreadcrumbItem {
  label: string;
  path?: string;
}

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const datasetContext = useDatasetContextStore();
const layout = useLayoutStore();
const runtime = useRuntimeStore();
const isMobile = ref(false);
const routeRenderError = ref("");

const tabs = layout.tabs;
const isAdmin = auth.isAdmin;
const defaultPath = computed(() => (isAdmin.value ? "/admin/overview" : "/workbench"));
const brandSubtitle = computed(() => (isAdmin.value ? "系统运维与后台管理" : "交易数据分析工作区"));

const userItems: NavItem[] = [
  {
    title: "工作台",
    subtitle: "全局状态与当前数据摘要",
    path: "/workbench",
    icon: GridOutline,
  },
  {
    title: "数据集管理",
    subtitle: "导入、预览与上下文切换",
    path: "/datasets",
    icon: FolderOpenOutline,
  },
  {
    title: "分析中心",
    subtitle: "指标分析、风险与对比",
    path: "/analysis",
    icon: StatsChartOutline,
  },
  {
    title: "算法雷达",
    subtitle: "异常、排行与风险事件",
    path: "/algo-radar",
    icon: PulseOutline,
  },
];

const adminItems: NavItem[] = [
  {
    title: "系统概览",
    subtitle: "用户规模、运行与审计总览",
    path: "/admin/overview",
    icon: SpeedometerOutline,
  },
  {
    title: "系统健康",
    subtitle: "服务连通性与失败事件",
    path: "/admin/health",
    icon: PulseOutline,
  },
  {
    title: "用户管理",
    subtitle: "账户启停、编辑与删除",
    path: "/admin/users",
    icon: PeopleOutline,
  },
  {
    title: "用户调用记录",
    subtitle: "关键操作与分析访问日志",
    path: "/admin/activity",
    icon: DocumentTextOutline,
  },
  {
    title: "数据资产总览",
    subtitle: "用户维度数据集与记录分布",
    path: "/admin/assets",
    icon: ServerOutline,
  },
  {
    title: "运行监控",
    subtitle: "导入批次与索引状态",
    path: "/admin/runs",
    icon: PodiumOutline,
  },
];

const menuGroups = computed(() => [
  {
    label: isAdmin.value ? "管理员后台" : "业务分析",
    items: isAdmin.value ? adminItems : userItems,
  },
]);

const breadcrumbs = computed<BreadcrumbItem[]>(() => {
  const items: BreadcrumbItem[] = [
    { label: isAdmin.value ? "管理员首页" : "业务首页", path: defaultPath.value },
  ];
  const sectionTitle = typeof route.meta.sectionTitle === "string" ? route.meta.sectionTitle : "";
  const title = typeof route.meta.title === "string" ? route.meta.title : "";

  if (sectionTitle && sectionTitle !== title) {
    items.push({ label: sectionTitle });
  }

  if (title) {
    items.push({ label: title });
  }

  return items;
});

const dropdownOptions = computed(() => [
  {
    label: `退出登录 (${auth.state.user?.username || "当前用户"})`,
    key: "logout",
  },
]);

function isItemActive(path: string) {
  return route.path === path || route.path.startsWith(`${path}/`);
}

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
    void router.replace("/login");
  }
}

function buildRenderErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message || "页面渲染异常，请刷新后重试。";
  }
  return String(error || "页面渲染异常，请刷新后重试。");
}

function reloadCurrentPage() {
  if (typeof window !== "undefined") {
    window.location.reload();
  }
}

watch(
  () => route.fullPath,
  () => {
    routeRenderError.value = "";
    const title = typeof route.meta.title === "string" ? route.meta.title : "";
    layout.visitTab({
      path: route.path,
      title,
      affix: Boolean(route.meta.affix),
    });
    layout.closeMobileSidebar();
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
  window.addEventListener("resize", syncViewport);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", syncViewport);
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
        <div class="shell__brand-badge">S</div>
        <div v-if="!layout.state.sidebarCollapsed || isMobile" class="shell__brand-copy">
          <div class="shell__brand-title">Stock FastAPI Admin</div>
          <div class="shell__brand-subtitle">{{ brandSubtitle }}</div>
        </div>
      </div>

      <div class="shell__nav">
        <section v-for="group in menuGroups" :key="group.label" class="shell__group">
          <div v-if="!layout.state.sidebarCollapsed || isMobile" class="shell__group-label">{{ group.label }}</div>
          <button
            v-for="item in group.items"
            :key="item.path"
            type="button"
            class="shell__nav-item"
            :class="{ 'shell__nav-item--active': isItemActive(item.path) }"
            :title="layout.state.sidebarCollapsed && !isMobile ? item.title : undefined"
            @click="openRoute(item.path)"
          >
            <span class="shell__nav-icon">
              <n-icon size="18">
                <component :is="item.icon" />
              </n-icon>
            </span>
            <span v-if="!layout.state.sidebarCollapsed || isMobile" class="shell__nav-copy">
              <span class="shell__nav-title">{{ item.title }}</span>
              <span class="shell__nav-subtitle">{{ item.subtitle }}</span>
            </span>
          </button>
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

        <div class="shell__topbar-right">
          <div class="shell__meta-chip">
            <span class="shell__meta-label">系统状态</span>
            <span>{{ runtime.syncStatusText }}</span>
          </div>
          <div class="shell__meta-chip shell__meta-chip--wide">
            <span class="shell__meta-label">最近同步</span>
            <span>{{ runtime.lastSyncText }}</span>
          </div>
          <n-dropdown trigger="click" :options="dropdownOptions" @select="handleDropdownSelect">
            <button type="button" class="shell__user">
              <n-avatar round :size="34" color="#f05a28">
                {{ auth.state.user?.username?.slice(0, 1).toUpperCase() || "U" }}
              </n-avatar>
              <span class="shell__user-copy">
                <strong>{{ auth.state.user?.username || "未登录" }}</strong>
                <span>{{ auth.state.user?.role || "--" }}</span>
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
          <span>{{ item.title }}</span>
          <span v-if="!item.affix" class="shell__tab-close" @click.stop="closeTab(item.path)">×</span>
        </button>
      </div>

      <main class="shell__content">
        <n-alert
          v-if="routeRenderError"
          title="页面渲染失败"
          type="error"
          :show-icon="true"
          class="shell__route-error"
        >
          <div>{{ routeRenderError }}</div>
          <div class="toolbar-row" style="margin-top: 10px;">
            <n-button size="small" @click="reloadCurrentPage">刷新页面</n-button>
          </div>
        </n-alert>
        <RouterView v-else />
      </main>
    </div>
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

.shell__brand-badge {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  font-size: 18px;
  font-weight: 800;
  color: #fff;
  background: linear-gradient(135deg, var(--accent-primary), #ff8050);
  box-shadow: 0 12px 30px rgba(240, 90, 40, 0.22);
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

.shell__nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px;
  border: 0;
  border-radius: 18px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  text-align: left;
  transition:
    background 0.18s ease,
    transform 0.18s ease,
    color 0.18s ease;
}

.shell__nav-item:hover {
  background: rgba(47, 111, 237, 0.06);
  transform: translateX(2px);
}

.shell__nav-item--active {
  background: linear-gradient(135deg, rgba(240, 90, 40, 0.14), rgba(47, 111, 237, 0.08));
  color: var(--accent-primary);
}

.shell__nav-icon {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  background: rgba(248, 250, 252, 0.9);
  flex-shrink: 0;
}

.shell__nav-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.shell__nav-title {
  font-weight: 700;
}

.shell__nav-subtitle {
  color: var(--text-soft);
  font-size: 12px;
  line-height: 1.5;
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
  justify-content: space-between;
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
  gap: 10px;
  padding: 4px;
  border: 0;
  background: transparent;
  cursor: pointer;
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

  .shell__meta-chip {
    display: none;
  }

  .shell__user-copy {
    display: none;
  }
}
</style>
