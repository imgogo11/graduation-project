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
        title: "\u767b\u5f55",
      },
    },
    {
      path: "/register",
      name: "register",
      component: () => import("@/pages/RegisterPage.vue"),
      meta: {
        guestOnly: true,
        layout: "auth",
        title: "\u6ce8\u518c",
      },
    },
    {
      path: "/workbench",
      name: "workbench",
      component: () => import("@/pages/WorkbenchPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "user",
        title: "\u5de5\u4f5c\u53f0",
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
        title: "\u6570\u636e\u96c6\u7ba1\u7406",
      },
    },
    {
      path: "/analysis",
      redirect: "/analysis/market",
    },
    {
      path: "/analysis/market",
      name: "analysis-market",
      component: () => import("@/pages/AnalysisCenterPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "user",
        title: "\u5206\u6790\u4e2d\u5fc3 / \u91d1\u878d\u5206\u6790",
        sectionTitle: "\u5206\u6790\u4e2d\u5fc3",
      },
    },
    {
      path: "/analysis/governance",
      name: "analysis-governance",
      component: () => import("@/pages/AnalysisCenterPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "user",
        title: "\u5206\u6790\u4e2d\u5fc3 / \u5feb\u7167\u4e0e\u76f8\u5173\u6027",
        sectionTitle: "\u5206\u6790\u4e2d\u5fc3",
      },
    },
    {
      path: "/algo-radar",
      redirect: "/algo-radar/risk",
    },
    {
      path: "/algo-radar/risk",
      name: "algo-radar-risk",
      component: () => import("@/pages/AlgoRadarPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "user",
        title: "\u7b97\u6cd5\u96f7\u8fbe / \u98ce\u9669\u96f7\u8fbe",
        sectionTitle: "\u7b97\u6cd5\u96f7\u8fbe",
      },
    },
    {
      path: "/algo-radar/algorithms",
      name: "algo-radar-algorithms",
      component: () => import("@/pages/AlgoRadarPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "user",
        title: "\u7b97\u6cd5\u96f7\u8fbe / \u7b97\u6cd5\u67e5\u8be2\u4e0e\u4e8b\u4ef6\u4e0a\u4e0b\u6587",
        sectionTitle: "\u7b97\u6cd5\u96f7\u8fbe",
      },
    },
    {
      path: "/admin/overview",
      redirect: "/admin/assets",
    },
    {
      path: "/admin/health",
      redirect: "/admin/assets",
    },
    {
      path: "/admin/users",
      name: "admin-users",
      component: () => import("@/pages/AdminUsersPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "admin",
        title: "\u7528\u6237\u7ba1\u7406",
        sectionTitle: "\u7ba1\u7406\u5458\u540e\u53f0",
      },
    },
    {
      path: "/admin/activity",
      name: "admin-activity",
      component: () => import("@/pages/AdminActivityPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "admin",
        title: "\u7528\u6237\u8c03\u7528\u8bb0\u5f55",
        sectionTitle: "\u7ba1\u7406\u5458\u540e\u53f0",
      },
    },
    {
      path: "/admin/assets",
      name: "admin-assets",
      component: () => import("@/pages/AdminAssetsPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "admin",
        title: "\u6570\u636e\u8d44\u4ea7\u603b\u89c8",
        sectionTitle: "\u7ba1\u7406\u5458\u540e\u53f0",
        affix: true,
      },
    },
    {
      path: "/admin/runs",
      name: "admin-runs",
      component: () => import("@/pages/AdminRunsPage.vue"),
      meta: {
        requiresAuth: true,
        audience: "admin",
        title: "\u8fd0\u884c\u76d1\u63a7",
        sectionTitle: "\u7ba1\u7406\u5458\u540e\u53f0",
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
      redirect: "/analysis/market",
    },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();

  if (to.path === "/admin/overview" || to.path === "/admin/health") {
    return { path: "/admin/assets" };
  }

  if (to.meta.requiresAuth && !auth.isAuthenticated.value) {
    return {
      name: "login",
      query: {
        redirect: to.fullPath,
      },
    };
  }

  if (to.meta.guestOnly && auth.isAuthenticated.value) {
    return auth.isAdmin.value ? { path: "/admin/assets" } : { path: "/workbench" };
  }

  const audience = to.meta.audience;
  if (audience === "admin" && !auth.isAdmin.value) {
    return { path: "/workbench" };
  }

  if (audience === "user" && auth.isAdmin.value) {
    return { path: "/admin/assets" };
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
