import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "@/stores/auth";


const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      redirect: "/overview",
    },
    {
      path: "/login",
      name: "login",
      component: () => import("@/pages/LoginPage.vue"),
      meta: {
        guestOnly: true,
        layout: "auth",
      },
    },
    {
      path: "/register",
      name: "register",
      component: () => import("@/pages/RegisterPage.vue"),
      meta: {
        guestOnly: true,
        layout: "auth",
      },
    },
    {
      path: "/overview",
      name: "overview",
      component: () => import("@/pages/OverviewPage.vue"),
      meta: {
        requiresAuth: true,
      },
    },
    {
      path: "/analysis-center",
      name: "analysis-center",
      component: () => import("@/pages/AnalysisCenterPage.vue"),
      meta: {
        requiresAuth: true,
      },
    },
    {
      path: "/algo-radar",
      name: "algo-radar",
      component: () => import("@/pages/AlgoRadarPage.vue"),
      meta: {
        requiresAuth: true,
      },
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
    return {
      name: "overview",
    };
  }

  return true;
});

export default router;
