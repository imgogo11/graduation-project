<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { NButton, NTable } from "naive-ui";

import { fetchImportRuns, fetchImportStats } from "@/api/imports";
import type { ImportRunRead, ImportStatsRead } from "@/api/types";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import StatCard from "@/components/StatCard.vue";
import { useRuntimeStore } from "@/stores/runtime";
import { formatCompact, formatDateTime, getErrorMessage } from "@/utils/format";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";


const runtime = useRuntimeStore();
const loading = ref(false);
const error = ref("");
usePageErrorNotification(error, "Admin Assets Error");
const stats = ref<ImportStatsRead | null>(null);
const runs = ref<ImportRunRead[]>([]);

const cards = computed(() => [
  {
    label: "总导入批次",
    value: String(stats.value?.total_runs ?? 0),
    hint: "系统内全部可见批次数",
    tone: "teal" as const,
  },
  {
    label: "成功批次",
    value: String(stats.value?.completed_runs ?? 0),
    hint: "状态为 completed 的批次数",
    tone: "orange" as const,
  },
  {
    label: "失败批次",
    value: String(stats.value?.failed_runs ?? 0),
    hint: "状态为 failed 的批次数",
    tone: "berry" as const,
  },
  {
    label: "累计记录",
    value: formatCompact(stats.value?.total_records ?? null, 2),
    hint: "全部导入记录总量",
    tone: "neutral" as const,
  },
  {
    label: "可用数据",
    value: String(stats.value?.available_datasets ?? 0),
    hint: "去重后的可用数据集数",
    tone: "teal" as const,
  },
]);

async function loadPage() {
  loading.value = true;
  error.value = "";
  try {
    const statsResponse = await fetchImportStats();
    const runsResponse = await fetchImportRuns({
      limit: Math.max(statsResponse.total_runs, 1),
    });
    stats.value = statsResponse;
    runs.value = runsResponse;
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
        <div class="page__eyebrow">Admin / Assets</div>
        <h2 class="page__title">数据资产总览</h2>
        <p class="page__subtitle">从管理员维度查看全体用户的数据规模、Owner 分布和最近导入动态</p>
      </div>
      <div class="page__actions">
        <n-button type="primary" :loading="loading" @click="loadPage">刷新数据</n-button>
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
      <PanelCard title="Owner 数据分布" description="按用户查看导入批次与记录规模">
        <div v-if="stats?.owner_summaries.length" class="data-table-wrap">
          <n-table class="data-table" striped size="small" :single-line="false">
            <thead>
              <tr>
                <th>用户ID</th>
                <th>用户</th>
                <th>批次</th>
                <th>记录</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in stats?.owner_summaries" :key="row.owner_user_id">
                <td>{{ row.owner_user_id }}</td>
                <td>{{ row.owner_username || "--" }}</td>
                <td>{{ row.runs }}</td>
                <td>{{ formatCompact(row.records, 2) }}</td>
              </tr>
            </tbody>
          </n-table>
        </div>
        <EmptyState v-else title="暂无 Owner 分布" description="当前没有可展示的用户数据分布统计" />
      </PanelCard>

      <PanelCard title="最近导入批次" description="按时间回看导入批次和归属用户">
        <div v-if="runs.length" class="data-table-wrap">
          <n-table class="data-table" striped size="small" :single-line="false">
            <thead>
              <tr>
                <th>批次</th>
                <th>数据</th>
                <th>Owner</th>
                <th>记录</th>
                <th>完成时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in runs.slice(0, 20)" :key="row.id">
                <td>#{{ row.display_id }}</td>
                <td>{{ row.dataset_name }}</td>
                <td>{{ row.owner_username || "--" }}</td>
                <td>{{ formatCompact(row.record_count ?? null, 2) }}</td>
                <td>{{ formatDateTime(row.completed_at || row.started_at) }}</td>
              </tr>
            </tbody>
          </n-table>
        </div>
        <EmptyState v-else title="暂无导入批次" description="完成导入后这里会展示最近批次" />
      </PanelCard>
    </section>
  </div>
</template>


