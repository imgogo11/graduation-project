<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { NButton, NTable, NTag } from "naive-ui";

import { fetchAdminOverview } from "@/api/admin";
import { fetchHealth } from "@/api/health";
import type { AdminOverviewRead, HealthResponse } from "@/api/types";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import StatCard from "@/components/StatCard.vue";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";
import { useRuntimeStore } from "@/stores/runtime";
import { formatCompact, formatDateTime, getErrorMessage, toStatusTagType } from "@/utils/format";
import { formatStatusText } from "@/utils/displayText";

const runtime = useRuntimeStore();
const loading = ref(false);
const error = ref("");
usePageErrorNotification(error, "管理概览加载失败");
const overview = ref<AdminOverviewRead | null>(null);
const health = ref<HealthResponse | null>(null);

const cards = computed(() => {
  if (!overview.value) {
    return [];
  }

  const metrics = overview.value.metrics;
  return [
    {
      label: "普通用户数",
      value: String(metrics.total_users),
      hint: "系统中的普通用户数量",
      tone: "teal" as const,
    },
    {
      label: "启用用户",
      value: String(metrics.active_users),
      hint: "当前处于启用状态的普通用户",
      tone: "orange" as const,
    },
    {
      label: "数据集批次数",
      value: String(metrics.total_runs),
      hint: "全部可见导入批次",
      tone: "berry" as const,
    },
    {
      label: "累计记录",
      value: formatCompact(metrics.total_records, 2),
      hint: "所有可见批次的记录总量",
      tone: "neutral" as const,
    },
    {
      label: "今日审计事件",
      value: String(metrics.today_events),
      hint: "当天关键操作和分析访问事件",
      tone: "teal" as const,
    },
    {
      label: "24小时失败事件",
      value: String(metrics.failed_events_24h),
      hint: "最近24小时失败操作数量",
      tone: "orange" as const,
    },
  ];
});

async function loadOverview() {
  loading.value = true;
  error.value = "";

  try {
    const [overviewResponse, healthResponse] = await Promise.all([fetchAdminOverview(), fetchHealth()]);
    overview.value = overviewResponse;
    health.value = healthResponse;
    runtime.markSynced();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadOverview();
});
</script>

<template>
  <div class="page">
    <section class="page__header">
      <div>
        <div class="page__eyebrow">管理后台 / 系统概览</div>
        <h2 class="page__title">管理员后台概览</h2>
        <p class="page__subtitle">集中查看系统规模、系统健康详情与运行状态，作为管理员登录后的默认首页。</p>
      </div>
      <div class="page__actions">
        <n-button type="primary" :loading="loading" @click="loadOverview">刷新概览</n-button>
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
              <n-tag :type="toStatusTagType(health.status)" round>{{ formatStatusText(health.status) }}</n-tag>
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

      <PanelCard title="最近运行批次" description="快速查看导入批次与算法索引状态。">
        <div v-if="overview?.recent_runs.length" class="data-table-wrap">
          <n-table class="data-table" striped size="small" :single-line="false">
            <thead>
              <tr>
                <th>批次</th>
                <th>数据集</th>
                <th>所属用户</th>
                <th>运行状态</th>
                <th>索引状态</th>
                <th>完成时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in overview?.recent_runs" :key="row.import_run_id">
                <td>#{{ row.display_id }}</td>
                <td>{{ row.dataset_name }}</td>
                <td>{{ row.owner_username || "--" }}</td>
                <td>
                  <n-tag :type="toStatusTagType(row.run_status)" round size="small">
                    {{ formatStatusText(row.run_status) }}
                  </n-tag>
                </td>
                <td>
                  <n-tag :type="toStatusTagType(row.algo_index_status)" round size="small">
                    {{ formatStatusText(row.algo_index_status) }}
                  </n-tag>
                </td>
                <td>{{ formatDateTime(row.completed_at || row.started_at) }}</td>
              </tr>
            </tbody>
          </n-table>
        </div>
        <EmptyState v-else title="暂无运行批次" description="导入数据后，这里会展示最近批次。" />
      </PanelCard>
    </section>
  </div>
</template>
