<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { NButton, NTable, NTag } from "naive-ui";

import { fetchAdminOverview } from "@/api/admin";
import type { AdminOverviewRead } from "@/api/types";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import StatCard from "@/components/StatCard.vue";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";
import { useRuntimeStore } from "@/stores/runtime";
import { formatCompact, formatDateTime, getErrorMessage, toStatusTagType } from "@/utils/format";

const runtime = useRuntimeStore();
const loading = ref(false);
const error = ref("");
usePageErrorNotification(error, "Admin Overview Error");
const overview = ref<AdminOverviewRead | null>(null);

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
      label: "24h失败事件",
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
    overview.value = await fetchAdminOverview();
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
        <div class="page__eyebrow">Admin / Overview</div>
        <h2 class="page__title">管理员后台概览</h2>
        <p class="page__subtitle">集中查看系统规模、运行状态与最近关键操作，作为管理员登录后的默认首页。</p>
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
      <PanelCard title="最近审计事件" description="用于快速回看关键操作与分析访问轨迹。">
        <div v-if="overview?.recent_audit_logs.length" class="data-table-wrap">
          <n-table class="data-table" striped size="small" :single-line="false">
            <thead>
              <tr>
                <th>时间</th>
                <th>分类</th>
                <th>事件</th>
                <th>执行人</th>
                <th>结果</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in overview?.recent_audit_logs" :key="row.id">
                <td>{{ formatDateTime(row.occurred_at) }}</td>
                <td>{{ row.category }}</td>
                <td>{{ row.event_type }}</td>
                <td>{{ row.actor_username_snapshot || "--" }}</td>
                <td>
                  <n-tag :type="row.success ? 'success' : 'error'" round size="small">
                    {{ row.success ? "成功" : "失败" }}
                  </n-tag>
                </td>
              </tr>
            </tbody>
          </n-table>
        </div>
        <EmptyState v-else title="暂无审计事件" description="当前还没有可展示的审计事件。" />
      </PanelCard>

      <PanelCard title="最近运行批次" description="快速查看导入批次与算法索引状态。">
        <div v-if="overview?.recent_runs.length" class="data-table-wrap">
          <n-table class="data-table" striped size="small" :single-line="false">
            <thead>
              <tr>
                <th>批次</th>
                <th>数据集</th>
                <th>Owner</th>
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
                  <n-tag :type="toStatusTagType(row.run_status)" round size="small">{{ row.run_status }}</n-tag>
                </td>
                <td>
                  <n-tag :type="toStatusTagType(row.algo_index_status)" round size="small">
                    {{ row.algo_index_status }}
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
