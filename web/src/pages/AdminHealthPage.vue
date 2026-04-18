<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { NButton, NTag } from "naive-ui";

import { fetchAdminAuditLogStats } from "@/api/admin";
import { fetchHealth } from "@/api/health";
import type { AuditLogStatsRead, HealthResponse } from "@/api/types";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import StatCard from "@/components/StatCard.vue";
import { useRuntimeStore } from "@/stores/runtime";
import { getErrorMessage, toStatusTagType } from "@/utils/format";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";


const runtime = useRuntimeStore();
const loading = ref(false);
const error = ref("");
usePageErrorNotification(error, "Admin Health Error");
const health = ref<HealthResponse | null>(null);
const auditStats = ref<AuditLogStatsRead | null>(null);

const cards = computed(() => [
  {
    label: "系统状态",
    value: health.value?.status || "--",
    hint: "后端健康检查返回状态",
    tone: "teal" as const,
  },
  {
    label: "数据库连接",
    value: health.value?.database_ok ? "正常" : "异常",
    hint: "数据库连接探测结果",
    tone: health.value?.database_ok ? ("neutral" as const) : ("orange" as const),
  },
  {
    label: "失败事件总数",
    value: String(auditStats.value?.failed_events ?? 0),
    hint: "审计日志中的失败事件数量",
    tone: "berry" as const,
  },
  {
    label: "今日审计事件",
    value: String(auditStats.value?.today_events ?? 0),
    hint: "今日产生的操作访问事件",
    tone: "orange" as const,
  },
]);

async function loadPage() {
  loading.value = true;
  error.value = "";
  try {
    const [healthResponse, statsResponse] = await Promise.all([fetchHealth(), fetchAdminAuditLogStats()]);
    health.value = healthResponse;
    auditStats.value = statsResponse;
    runtime.markSynced();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadPage();
});
</script>

<template>
  <div class="page">
    <section class="page__header">
      <div>
        <div class="page__eyebrow">Admin / Health</div>
        <h2 class="page__title">系统健康状态</h2>
        <p class="page__subtitle">管理员用于确认后端连通、数据库状态及审计失败趋势的运维视图</p>
      </div>
      <div class="page__actions">
        <n-button type="primary" :loading="loading" @click="loadPage">刷新状态</n-button>
      </div>
    </section>
<section class="page__grid page__grid--stats">
      <StatCard
        v-for="item in cards"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :tone="item.tone"
      />
    </section>

    <section class="page__grid page__grid--double">
      <PanelCard title="健康详情" description="来自 /api/health 的实时信息">
        <div v-if="health" class="detail-grid">
          <div class="detail-grid__item">
            <span class="detail-grid__label">状态</span>
            <div class="detail-grid__value">
              <n-tag :type="toStatusTagType(health.status)" round>{{ health.status }}</n-tag>
            </div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">环境</span>
            <div class="detail-grid__value">{{ health.environment }}</div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">数据库</span>
            <div class="detail-grid__value">{{ health.database_ok ? "连接正常" : "连接失败" }}</div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">说明</span>
            <div class="detail-grid__value">{{ health.detail }}</div>
          </div>
        </div>
        <EmptyState v-else title="暂无健康数据" description="点击刷新后展示最新健康检查结果" />
      </PanelCard>

      <PanelCard title="审计统计概览" description="帮助定位近期异常操作与失败趋势">
        <div v-if="auditStats" class="detail-grid">
          <div class="detail-grid__item">
            <span class="detail-grid__label">总事件数</span>
            <div class="detail-grid__value">{{ auditStats.total_events }}</div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">成功事件</span>
            <div class="detail-grid__value">{{ auditStats.success_events }}</div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">失败事件</span>
            <div class="detail-grid__value">{{ auditStats.failed_events }}</div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">活跃操作</span>
            <div class="detail-grid__value">{{ auditStats.unique_actor_count }}</div>
          </div>
        </div>
        <EmptyState v-else title="暂无审计统计" description="点击刷新后展示审计统计结果" />
      </PanelCard>
    </section>
  </div>
</template>


