import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "@/stores/auth";


const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      redirect: "/login",
    },
    {
      path: "/login",
      name: "login",
      component: () => import("@/pages/LoginPage.vue"),
      meta: {
        guestOnly: true,
        layout: "auth",
        title: "登录",
      },
    },
    {
      path: "/register",
      name: "register",
      component: () => import("@/pages/RegisterPage.vue"),
      meta: {
        guestOnly: true,
        layout: "auth",
        title: "注册",
      },
    },
    {
      path: "/workbench",
      name: "workbench",
      component: () => import("@/pages/WorkbenchPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "user",
        title: "工作台",
        affix: true,
      },
    },
    {
      path: "/datasets",
      name: "datasets",
      component: () => import("@/pages/DatasetsPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "user",
        title: "数据集管理",
      },
    },
    {
      path: "/analysis",
      name: "analysis",
      component: () => import("@/pages/AnalysisCenterPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "user",
        title: "分析中心",
      },
    },
    {
      path: "/algo-radar",
      name: "algo-radar",
      component: () => import("@/pages/AlgoRadarPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "user",
        title: "算法雷达",
      },
    },
    {
      path: "/admin/overview",
      name: "admin-overview",
      component: () => import("@/pages/AdminOverviewPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "admin",
        title: "系统概览",
        sectionTitle: "管理员后台",
        affix: true,
      },
    },
    {
      path: "/admin/health",
      redirect: "/admin/overview",
    },
    {
      path: "/admin/users",
      name: "admin-users",
      component: () => import("@/pages/AdminUsersPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "admin",
        title: "用户管理",
        sectionTitle: "管理员后台",
      },
    },
    {
      path: "/admin/activity",
      name: "admin-activity",
      component: () => import("@/pages/AdminActivityPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "admin",
        title: "用户调用记录",
        sectionTitle: "管理员后台",
      },
    },
    {
      path: "/admin/assets",
      name: "admin-assets",
      component: () => import("@/pages/AdminAssetsPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "admin",
        title: "数据资产总览",
        sectionTitle: "管理员后台",
      },
    },
    {
      path: "/admin/runs",
      name: "admin-runs",
      component: () => import("@/pages/AdminRunsPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "admin",
        title: "运行监控",
        sectionTitle: "管理员后台",
      },
    },
    {
      path: "/system/users",
      redirect: "/admin/users",
    },
    {
      path: "/overview",
      redirect: "/workbench",
    },
    {
      path: "/analysis-center",
      redirect: "/analysis",
    },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();

  if (to.meta.requiresAuth && !auth.isAuthenticated.value) {
    return {
      name: "login",
      query: {
        redirect: to.fullPath,
      },
    };
  }

  if (to.meta.guestOnly && auth.isAuthenticated.value) {
    return auth.isAdmin.value ? { path: "/admin/overview" } : { path: "/workbench" };
  }

  const audience = to.meta.audience;
  if (audience === "admin" && !auth.isAdmin.value) {
    return { path: "/workbench" };
  }

  if (audience === "user" && auth.isAdmin.value) {
    return { path: "/admin/overview" };
  }

  return true;
});

router.onError((error, to) => {
  const message = error instanceof Error ? error.message : String(error);
  const isDynamicImportError =
    /Failed to fetch dynamically imported module/i.test(message) ||
    /Importing a module script failed/i.test(message) ||
    /error loading dynamically imported module/i.test(message);

  if (isDynamicImportError && typeof window !== "undefined") {
    const reloadKey = `router-dynamic-import-reload:${to.fullPath}`;
    const shouldReload = window.sessionStorage.getItem(reloadKey) !== "1";

    if (shouldReload) {
      window.sessionStorage.setItem(reloadKey, "1");
      window.location.assign(to.fullPath);
      return;
    }

    window.sessionStorage.removeItem(reloadKey);
    if (import.meta.env.DEV) {
      console.error("[router] dynamic import failed after reload", error);
    }
    return;
  }

  if (import.meta.env.DEV) {
    console.error("[router] navigation error", error);
  }
});

export default router;
