<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from "vue";
import { SyncOutline } from "@vicons/ionicons5";

import { NButton, NDataTable, NIcon, NTag, useMessage, type DataTableColumns } from "naive-ui";

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

const runsTableScrollX = 1420;
const runsTableMaxHeight = "min(48vh, 420px)";

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

const runsTableColumns: DataTableColumns<AdminRunMonitorRowRead> = [
  {
    title: "批次",
    key: "display_id",
    width: 110,
    render(row) {
      return `#${row.display_id}`;
    },
  },
  {
    title: "数据集",
    key: "dataset_name",
    width: 200,
    ellipsis: {
      tooltip: true,
    },
  },
  {
    title: "所属用户",
    key: "owner_username",
    width: 150,
    render(row) {
      return row.owner_username || "--";
    },
  },
  {
    title: "运行状态",
    key: "run_status",
    width: 140,
    render(row) {
      return h(
        NTag,
        {
          type: toStatusTagType(row.run_status),
          round: true,
          size: "small",
        },
        { default: () => formatStatusText(row.run_status) }
      );
    },
  },
  {
    title: "索引状态",
    key: "algo_index_status",
    width: 140,
    render(row) {
      return h(
        NTag,
        {
          type: toStatusTagType(row.algo_index_status),
          round: true,
          size: "small",
        },
        { default: () => formatStatusText(row.algo_index_status) }
      );
    },
  },
  {
    title: "记录",
    key: "record_count",
    width: 120,
    render(row) {
      return formatCompact(row.record_count ?? null, 2);
    },
  },
  {
    title: "完成时间",
    key: "completed_at",
    width: 210,
    className: "admin-table-time-column",
    render(row) {
      return h("span", { class: "admin-table-time" }, formatDateTime(row.completed_at || row.started_at));
    },
  },
  {
    title: "错误信息",
    key: "algo_last_error",
    width: 210,
    ellipsis: {
      tooltip: true,
    },
    render(row) {
      return row.algo_last_error || "--";
    },
  },
  {
    title: "操作",
    key: "actions",
    width: 100,
    render(row) {
      return h(
        NButton,
        {
          text: true,
          type: "warning",
          disabled: !canRebuild(row),
          loading: Boolean(rowLoading[row.import_run_id]),
          onClick: () => rebuildIndex(row),
        },
        {
          icon: () => h(NIcon, null, { default: () => h(SyncOutline) }),
          default: () => "重建索引",
        }
      );
    },
  },
];

const runsTablePagination = computed(() => ({
  page: rowsPager.page.value,
  pageSize: rowsPager.pageSize.value,
  itemCount: rowsPager.total.value,
  pageSizes: rowsPager.pageSizes,
  showSizePicker: true,
  onUpdatePage: rowsPager.setPage,
  onUpdatePageSize: rowsPager.setPageSize,
}));

function getRunRowKey(row: AdminRunMonitorRowRead) {
  return row.import_run_id;
}

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

      <n-data-table
        v-if="rowsPager.total.value"
        class="admin-runs-table"
        :columns="runsTableColumns"
        :data="rows"
        :pagination="runsTablePagination"
        :row-key="getRunRowKey"
        :max-height="runsTableMaxHeight"
        :scroll-x="runsTableScrollX"
        :scrollbar-props="{ trigger: 'none' }"
        :single-line="false"
        striped
        size="small"
      />

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

.admin-runs-table {
  border-radius: 18px;
  overflow: visible;
}

:deep(.admin-runs-table .n-data-table-th) {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  white-space: nowrap;
}

:deep(.admin-runs-table .n-data-table-td) {
  vertical-align: top;
}

:deep(.admin-runs-table .admin-table-time-column),
:deep(.admin-runs-table .admin-table-time) {
  white-space: nowrap;
}

:deep(.admin-runs-table .n-data-table__pagination) {
  padding: 0 12px 10px;
  border-top: 1px solid var(--panel-border);
  background: #fff;
}
</style>
