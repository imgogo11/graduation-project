<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { SyncOutline } from "@vicons/ionicons5";

import { NButton, NIcon, NPagination, NTable, NTag, useMessage } from "naive-ui";

import { fetchAdminRunsMonitor } from "@/api/admin";
import { fetchImportStats } from "@/api/imports";
import { rebuildAlgoIndex } from "@/api/riskRadar";
import type { AdminRunMonitorRead, AdminRunMonitorRowRead, ImportStatsRead } from "@/api/types";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import { useTablePager } from "@/composables/useTablePager";
import { useRuntimeStore } from "@/stores/runtime";
import { formatCompact, formatDateTime, getErrorMessage, toStatusTagType } from "@/utils/format";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";
import { formatStatusText } from "@/utils/displayText";


const message = useMessage();
const runtime = useRuntimeStore();
const loading = ref(false);
const error = ref("");
usePageErrorNotification(error, "运行监控加载失败");
const monitor = ref<AdminRunMonitorRead | null>(null);
const importStats = ref<ImportStatsRead | null>(null);
const rowLoading = reactive<Record<number, boolean>>({});
const MONITOR_LIMIT = 60;

const rows = computed(() => monitor.value?.rows || []);
const rowsPager = useTablePager(rows, {
  initialPageSize: 20,
  pageSizes: [10, 20, 50, 100],
});

const indexSummaryPills = computed(() => [
  {
    label: "索引就绪",
    value: String(monitor.value?.ready_indexes ?? 0),
  },
  {
    label: "索引待处理",
    value: String(monitor.value?.pending_indexes ?? 0),
  },
  {
    label: "索引失败",
    value: String(monitor.value?.failed_indexes ?? 0),
  },
]);

const importSummaryPills = computed(() => [
  {
    label: "总导入批次",
    value: String(importStats.value?.total_runs ?? 0),
  },
  {
    label: "导入成功批次",
    value: String(importStats.value?.completed_runs ?? 0),
  },
  {
    label: "导入失败批次",
    value: String(importStats.value?.failed_runs ?? 0),
  },
]);

function canRebuild(row: AdminRunMonitorRowRead) {
  return row.run_status === "completed" && row.algo_index_status !== "building";
}

async function loadPage() {
  loading.value = true;
  error.value = "";
  try {
    const [monitorResponse, statsResponse] = await Promise.all([
      fetchAdminRunsMonitor({ limit: MONITOR_LIMIT }),
      fetchImportStats(),
    ]);
    monitor.value = monitorResponse;
    importStats.value = statsResponse;
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
    message.error(error.value);
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
    <PanelCard title="批次与索引状态">
      <template #title>
        <span class="runs-card__title">
          <span>批次与索引状态</span>
          <span class="runs-card__summary">
            <span class="runs-card__stats">
              <span v-for="item in importSummaryPills" :key="item.label" class="pill runs-card__pill">
                {{ item.label }} {{ item.value }}
              </span>
            </span>
            <span class="runs-card__stats">
              <span v-for="item in indexSummaryPills" :key="item.label" class="pill runs-card__pill">
                {{ item.label }} {{ item.value }}
              </span>
            </span>
          </span>
        </span>
      </template>

      <div class="inline-hint" style="margin-bottom: 12px;">
        重建索引：会重新计算该批次的算法索引，适用于索引失效、数据更新后同步，或分析结果校验场景。
      </div>

      <div v-if="rowsPager.total.value" class="data-table-wrap">
        <n-table class="data-table" striped size="small" :single-line="false">
          <thead>
            <tr>
              <th>批次</th>
              <th>数据集</th>
              <th>所属用户</th>
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
                  {{ formatStatusText(row.run_status) }}
                </n-tag>
              </td>
              <td>
                <n-tag :type="toStatusTagType(row.algo_index_status)" round size="small">
                  {{ formatStatusText(row.algo_index_status) }}
                </n-tag>
              </td>
              <td>{{ formatCompact(row.record_count ?? null, 2) }}</td>
              <td>{{ formatDateTime(row.completed_at || row.started_at) }}</td>
              <td>{{ row.algo_last_error || "--" }}</td>
              <td>
                <n-button
                  text
                  type="warning"
                  :disabled="!canRebuild(row)"
                  :loading="Boolean(rowLoading[row.import_run_id])"
                  @click="rebuildIndex(row)"
                >
                  <template #icon>
                    <n-icon><SyncOutline /></n-icon>
                  </template>
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

<style scoped>
.runs-card__title {
  display: inline-flex;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}

.runs-card__summary {
  display: inline-flex;
  flex-direction: column;
  gap: 8px;
}

.runs-card__stats {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.runs-card__pill {
  padding: 5px 10px;
  font-size: 12px;
}
</style>
