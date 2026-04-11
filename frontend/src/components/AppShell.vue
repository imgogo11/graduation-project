<script setup lang="ts">
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";
import { useRuntimeStore } from "@/stores/runtime";


const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const runtime = useRuntimeStore();
const navItems = [
  { label: "Overview", to: "/overview", subtitle: "Health / Imports / Stats" },
  { label: "Trading", to: "/trading", subtitle: "Upload / Charts / Algo" },
  { label: "Analysis Center", to: "/analysis", subtitle: "Indicators / Risk / Quality" },
  { label: "Risk Radar", to: "/risk-radar", subtitle: "3D Anomalies / Context / Profiles" },
];

function logout() {
  auth.clearSession();
  router.replace("/login");
}
</script>

<template>
  <div class="shell">
    <header class="shell__header">
      <div class="shell__hero">
        <div class="shell__eyebrow">Stock Trading Data Management and Analysis System Based on C++ Algorithm Module</div>
        <h1 class="shell__title">基于 C++ 算法模块的股票交易数据管理与分析系统设计与实现</h1>
        <p class="shell__subtitle">
          统一承接用户注册登录、CSV/XLSX 历史交易数据上传、按用户隔离的数据管理，以及基于
          C++ 算法模块和 Python 分析层的多维度交易分析能力。
        </p>
      </div>

      <div class="shell__meta">
        <div class="shell__meta-chip">
          <span class="shell__meta-label">API</span>
          <span class="mono">{{ runtime.apiLabel }}</span>
        </div>
        <div class="shell__meta-chip">
          <span class="shell__meta-label">当前用户</span>
          <span>{{ auth.state.user?.username || "--" }} / {{ auth.state.user?.role || "--" }}</span>
        </div>
        <div class="shell__meta-chip">
          <span class="shell__meta-label">联调状态</span>
          <span>{{ runtime.lastSyncText }}</span>
        </div>
        <el-button type="primary" plain @click="logout">退出登录</el-button>
      </div>
    </header>

    <nav class="shell__nav">
      <RouterLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="shell__nav-item"
        :class="{ 'shell__nav-item--active': route.path === item.to }"
      >
        <span class="shell__nav-title">{{ item.label }}</span>
        <span class="shell__nav-subtitle">{{ item.subtitle }}</span>
      </RouterLink>
    </nav>

    <main class="shell__content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  padding: 28px;
}

.shell__header {
  position: relative;
  overflow: hidden;
  display: flex;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
  padding: 32px;
  border: 1px solid var(--panel-border);
  border-radius: 32px;
  background:
    linear-gradient(135deg, rgba(255, 252, 246, 0.92), rgba(255, 247, 234, 0.84)),
    linear-gradient(120deg, rgba(11, 143, 140, 0.08), rgba(242, 140, 40, 0.1));
  box-shadow: var(--shadow-soft);
}

.shell__header::after {
  content: "";
  position: absolute;
  right: -48px;
  top: -48px;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(11, 143, 140, 0.18) 0%, rgba(11, 143, 140, 0) 72%);
}

.shell__hero,
.shell__meta {
  position: relative;
  z-index: 1;
}

.shell__eyebrow {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.22em;
  color: var(--accent-orange);
  font-weight: 700;
}

.shell__title {
  margin: 12px 0;
  font-size: clamp(34px, 4.4vw, 52px);
  line-height: 1;
}

.shell__subtitle {
  max-width: 720px;
  margin: 0;
  color: var(--text-secondary);
  font-size: 15px;
  line-height: 1.72;
}

.shell__meta {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: min(100%, 320px);
}

.shell__meta-chip {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px solid rgba(24, 50, 47, 0.08);
  background: rgba(255, 255, 255, 0.62);
  backdrop-filter: blur(8px);
}

.shell__meta-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: var(--text-soft);
  font-weight: 700;
}

.shell__nav {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.shell__nav-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 18px 20px;
  border-radius: 20px;
  border: 1px solid rgba(24, 50, 47, 0.08);
  background: rgba(255, 255, 255, 0.56);
  box-shadow: var(--shadow-card);
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    background 0.18s ease;
}

.shell__nav-item:hover {
  transform: translateY(-1px);
  border-color: rgba(11, 143, 140, 0.2);
}

.shell__nav-item--active {
  border-color: rgba(11, 143, 140, 0.32);
  background: linear-gradient(135deg, rgba(11, 143, 140, 0.12), rgba(255, 255, 255, 0.72));
}

.shell__nav-title {
  font-size: 16px;
  font-weight: 700;
}

.shell__nav-subtitle {
  font-size: 12px;
  color: var(--text-secondary);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.shell__content {
  margin-top: 22px;
  padding-bottom: 18px;
}

@media (max-width: 768px) {
  .shell {
    padding: 16px;
  }

  .shell__header {
    padding: 22px;
    border-radius: 24px;
  }

  .shell__title {
    font-size: 32px;
  }
}
</style>
