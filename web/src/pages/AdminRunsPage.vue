<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { NButton, NInputNumber, NPagination, NTable, NTag, useMessage } from "naive-ui";

import { fetchAdminRunsMonitor } from "@/api/admin";
import { rebuildAlgoIndex } from "@/api/riskRadar";
import type { AdminRunMonitorRead, AdminRunMonitorRowRead } from "@/api/types";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import StatCard from "@/components/StatCard.vue";
import { useTablePager } from "@/composables/useTablePager";
import { useRuntimeStore } from "@/stores/runtime";
import { formatCompact, formatDateTime, getErrorMessage, toStatusTagType } from "@/utils/format";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";


const message = useMessage();
const runtime = useRuntimeStore();
const loading = ref(false);
const error = ref("");
usePageErrorNotification(error, "Admin Runs Error");
const monitor = ref<AdminRunMonitorRead | null>(null);
const limit = ref(60);
const rowLoading = reactive<Record<number, boolean>>({});

const rows = computed(() => monitor.value?.rows || []);
const rowsPager = useTablePager(rows, {
  initialPageSize: 20,
  pageSizes: [10, 20, 50, 100],
});

const cards = computed(() => [
  {
    label: "监控批次总数",
    value: String(monitor.value?.total_runs ?? 0),
    hint: "当前返回的批次数",
    tone: "teal" as const,
  },
  {
    label: "索引就绪",
    value: String(monitor.value?.ready_indexes ?? 0),
    hint: "状态为 ready 的索引数",
    tone: "neutral" as const,
  },
  {
    label: "索引待处理",
    value: String(monitor.value?.pending_indexes ?? 0),
    hint: "状态为 pending/building 的索引数",
    tone: "orange" as const,
  },
  {
    label: "索引失败",
    value: String(monitor.value?.failed_indexes ?? 0),
    hint: "状态为 failed 的索引数",
    tone: "berry" as const,
  },
]);

function canRebuild(row: AdminRunMonitorRowRead) {
  return row.run_status === "completed" && row.algo_index_status !== "building";
}

async function loadPage() {
  loading.value = true;
  error.value = "";
  try {
    monitor.value = await fetchAdminRunsMonitor({ limit: limit.value });
    runtime.markSynced();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loading.value = false;
  }
}

async function rebuildIndex(row: AdminRunMonitorRowRead) {
  if (!canRebuild(row)) {
    return;
  }
  const confirmed = window.confirm(
    `确认重建批次 #${row.display_id} 的算法索引吗？\n\n用途：重新计算该批次用于风险雷达异常分析的索引。\n建议在索引 failed、数据更新后或分析结果异常时使用。`
  );
  if (!confirmed) {
    return;
  }

  rowLoading[row.import_run_id] = true;
  error.value = "";
  try {
    await rebuildAlgoIndex(row.import_run_id);
    message.success(`已触发批次 #${row.display_id} 的索引重建任务`);
    await loadPage();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    rowLoading[row.import_run_id] = false;
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
        <div class="page__eyebrow">Admin / Runs</div>
        <h2 class="page__title">运行监控</h2>
        <p class="page__subtitle">监控导入批次和算法索引状态，重建索引用于重新计算风险雷达异常分析依赖的索引结果</p>
      </div>
      <div class="page__actions">
        <span>批次上限</span>
        <n-input-number v-model:value="limit" :min="1" :max="200" />
        <n-button type="primary" :loading="loading" @click="loadPage">刷新监控</n-button>
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

    <PanelCard title="批次与索引状态" description="显示导入运行状态、索引状态和错误信息">
      <div class="inline-hint" style="margin-bottom: 12px;">
        重建索引：会重新计算该批次的算法索引，主要用于修复索引失败、数据更新后的重新同步，或排查分析结果异常。
      </div>
      <div v-if="rowsPager.total.value" class="data-table-wrap">
        <n-table class="data-table" striped size="small" :single-line="false">
          <thead>
            <tr>
              <th>批次</th>
              <th>数据</th>
              <th>Owner</th>
              <th>运行状态</th>
              <th>索引状态</th>
              <th>记录</th>
              <th>完成时间</th>
              <th>错误信息</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rowsPager.pagedRows.value" :key="row.import_run_id">
              <td>#{{ row.display_id }}</td>
              <td>{{ row.dataset_name }}</td>
              <td>{{ row.owner_username || "--" }}</td>
              <td>
                <n-tag :type="toStatusTagType(row.run_status)" round size="small">
                  {{ row.run_status }}
                </n-tag>
              </td>
              <td>
                <n-tag :type="toStatusTagType(row.algo_index_status)" round size="small">
                  {{ row.algo_index_status }}
                </n-tag>
              </td>
              <td>{{ formatCompact(row.record_count ?? null, 2) }}</td>
              <td>{{ formatDateTime(row.completed_at || row.started_at) }}</td>
              <td>{{ row.algo_last_error || "--" }}</td>
              <td>
                <n-button
                  size="small"
                  type="warning"
                  :disabled="!canRebuild(row)"
                  :loading="Boolean(rowLoading[row.import_run_id])"
                  @click="rebuildIndex(row)"
                >
                  重建索引
                </n-button>
              </td>
            </tr>
          </tbody>
        </n-table>
        <div class="table-pagination">
          <n-pagination
            :page="rowsPager.page.value"
            :page-size="rowsPager.pageSize.value"
            :item-count="rowsPager.total.value"
            :page-sizes="rowsPager.pageSizes"
            show-size-picker
            @update:page="rowsPager.setPage"
            @update:page-size="rowsPager.setPageSize"
          />
        </div>
      </div>
      <EmptyState v-else title="暂无运行监控数据" description="导入批次创建后这里会展示状态信息" />
    </PanelCard>
  </div>
</template>
