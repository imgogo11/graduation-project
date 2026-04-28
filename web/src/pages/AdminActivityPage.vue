<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";

import {
  NButton,
  NDataTable,
  NDatePicker,
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NTag,
  useMessage,
  type DataTableColumns,
} from "naive-ui";

import { fetchAdminAuditLogStats, fetchAdminAuditLogs } from "@/api/admin";
import type { AuditLogListRead, AuditLogStatsRead } from "@/api/types";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import { useRuntimeStore } from "@/stores/runtime";
import { formatAuditCategory, formatAuditEvent } from "@/utils/audit";
import { formatDateTime, getErrorMessage } from "@/utils/format";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";


type SuccessFilter = "all" | "success" | "failed";

const runtime = useRuntimeStore();
const message = useMessage();
const loading = ref(false);
const error = ref("");
usePageErrorNotification(error, "调用记录加载失败");
const logs = ref<AuditLogListRead | null>(null);
const stats = ref<AuditLogStatsRead | null>(null);
const page = ref(1);
const pageSize = ref(20);

const actorUsernameInput = ref("");
const category = ref("");
const successFilter = ref<SuccessFilter>("all");
const startAt = ref("");
const endAt = ref("");

const successOptions = [
  { label: "全部", value: "all" },
  { label: "仅成功", value: "success" },
  { label: "仅失败", value: "failed" },
];

const activityTableScrollX = 1280;
const activityTableMaxHeight = "min(48vh, 420px)";
const activityPageSizes = [10, 20, 50, 100];

const categoryOptions = computed(() =>
  (stats.value?.category_breakdown || []).map((item) => ({
    label: `${formatAuditCategory(item.category)} (${item.total})`,
    value: item.category,
  }))
);

const actorUsernameKeyword = computed(() => actorUsernameInput.value.trim() || undefined);

const successValue = computed(() => {
  if (successFilter.value === "success") {
    return true;
  }
  if (successFilter.value === "failed") {
    return false;
  }
  return undefined;
});

const statPills = computed(() => [
  {
    label: "总事件数",
    value: String(stats.value?.total_events ?? 0),
  },
  {
    label: "成功事件",
    value: String(stats.value?.success_events ?? 0),
  },
  {
    label: "失败事件",
    value: String(stats.value?.failed_events ?? 0),
  },
  {
    label: "今日事件",
    value: String(stats.value?.today_events ?? 0),
  },
]);
const startAtPickerValue = computed({
  get: () => startAt.value || undefined,
  set: (value: string | null | undefined) => {
    startAt.value = value ?? "";
  },
});
const endAtPickerValue = computed({
  get: () => endAt.value || undefined,
  set: (value: string | null | undefined) => {
    endAt.value = value ?? "";
  },
});

const activityTableColumns: DataTableColumns<AuditLogListRead["rows"][number]> = [
  {
    title: "时间",
    key: "occurred_at",
    width: 220,
    className: "admin-table-time-column",
    render(row) {
      return h("span", { class: "admin-table-time" }, formatDateTime(row.occurred_at));
    },
  },
  {
    title: "分类",
    key: "category",
    width: 150,
    render(row) {
      return formatAuditCategory(row.category);
    },
  },
  {
    title: "事件",
    key: "event_type",
    width: 170,
    render(row) {
      return formatAuditEvent(row.event_type);
    },
  },
  {
    title: "执行人",
    key: "actor_username_snapshot",
    width: 150,
    render(row) {
      return row.actor_username_snapshot || "--";
    },
  },
  {
    title: "目标",
    key: "target_label",
    width: 150,
    ellipsis: {
      tooltip: true,
    },
    render(row) {
      return row.target_label || "--";
    },
  },
  {
    title: "路径",
    key: "request_path",
    width: 300,
    ellipsis: {
      tooltip: true,
    },
    render(row) {
      return row.request_path || "--";
    },
  },
  {
    title: "结果",
    key: "success",
    width: 140,
    render(row) {
      return h(
        NTag,
        {
          type: row.success ? "success" : "error",
          round: true,
          size: "small",
        },
        { default: () => (row.success ? "成功" : `失败(${row.status_code || "-"})`) }
      );
    },
  },
];

const activityTablePagination = computed(() => ({
  page: page.value,
  pageSize: pageSize.value,
  itemCount: logs.value?.total || 0,
  pageSizes: activityPageSizes,
  showSizePicker: true,
  onUpdatePage: updatePage,
  onUpdatePageSize: updatePageSize,
}));

function getActivityRowKey(row: AuditLogListRead["rows"][number]) {
  return row.id;
}

function toIso(value: string | null | undefined) {
  if (!value) {
    return undefined;
  }
  const iso = new Date(value).toISOString();
  return iso === "Invalid Date" ? undefined : iso;
}

async function loadStats() {
  stats.value = await fetchAdminAuditLogStats({
    actor_username: actorUsernameKeyword.value,
    category: category.value || undefined,
    success: successValue.value,
    start_at: toIso(startAt.value),
    end_at: toIso(endAt.value),
  });
}

async function loadLogs() {
  logs.value = await fetchAdminAuditLogs({
    page: page.value,
    page_size: pageSize.value,
    actor_username: actorUsernameKeyword.value,
    category: category.value || undefined,
    success: successValue.value,
    start_at: toIso(startAt.value),
    end_at: toIso(endAt.value),
  });
}

async function refreshPage(options: { notify?: boolean } = {}) {
  loading.value = true;
  error.value = "";
  try {
    await Promise.all([loadStats(), loadLogs()]);
    runtime.markSynced();
    if (options.notify) {
      message.success("筛选已应用");
    }
  } catch (err) {
    error.value = getErrorMessage(err);
    if (options.notify) {
      message.error(error.value);
    }
  } finally {
    loading.value = false;
  }
}

function applyFilter() {
  page.value = 1;
  void refreshPage({ notify: true });
}

function updatePage(next: number) {
  page.value = next;
  void refreshPage();
}

function updatePageSize(next: number) {
  pageSize.value = next;
  page.value = 1;
  void refreshPage();
}

onMounted(() => {
  void refreshPage();
});
</script>

<template>
  <div class="page">
    <PanelCard title="调用记录">
      <template #title>
        <span class="activity-card__title">
          <span>调用记录</span>
          <span class="activity-card__stats">
            <span v-for="item in statPills" :key="item.label" class="pill activity-card__pill">
              {{ item.label }} {{ item.value }}
            </span>
          </span>
        </span>
      </template>
      <n-form class="admin-filter-grid admin-filter-grid--activity" label-placement="top">
        <n-form-item label="执行人">
          <n-input v-model:value="actorUsernameInput" clearable placeholder="输入执行人用户名" />
        </n-form-item>
        <n-form-item label="分类">
          <n-select
            v-model:value="category"
            clearable
            filterable
            :options="categoryOptions"
            placeholder="选择分类"
          />
        </n-form-item>
        <n-form-item label="结果">
          <n-select
            v-model:value="successFilter"
            :options="successOptions"
          />
        </n-form-item>
        <n-form-item label="开始时间">
          <n-date-picker v-model:formatted-value="startAtPickerValue" type="datetime" value-format="yyyy-MM-dd HH:mm:ss" clearable />
        </n-form-item>
        <n-form-item label="结束时间">
          <n-date-picker v-model:formatted-value="endAtPickerValue" type="datetime" value-format="yyyy-MM-dd HH:mm:ss" clearable />
        </n-form-item>
        <n-form-item label=" ">
          <n-button
            class="admin-filter-grid__button"
            type="warning"
            :loading="loading"
            @click="applyFilter"
          >
            应用筛选
          </n-button>
        </n-form-item>
      </n-form>

      <n-data-table
        v-if="logs?.rows.length"
        class="admin-activity-table"
        :columns="activityTableColumns"
        :data="logs.rows"
        :pagination="activityTablePagination"
        :row-key="getActivityRowKey"
        :max-height="activityTableMaxHeight"
        :scroll-x="activityTableScrollX"
        :scrollbar-props="{ trigger: 'none' }"
        :single-line="false"
        remote
        striped
        size="small"
      />
      <EmptyState v-else title="暂无调用记录" description="当前筛选条件下没有可展示的审计日志" />
    </PanelCard>
  </div>
</template>

<style scoped>
.activity-card__title {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.activity-card__stats {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.activity-card__pill {
  padding: 5px 10px;
  font-size: 12px;
}

.admin-filter-grid {
  --admin-filter-control-width: 180px;
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: var(--admin-filter-control-width);
  gap: 0 20px;
  align-items: end;
  justify-content: start;
  margin-bottom: 16px;
}

.admin-filter-grid--activity {
  grid-template-columns: repeat(6, var(--admin-filter-control-width));
}

.admin-filter-grid__button {
  width: 100%;
}

.admin-activity-table {
  border-radius: 18px;
  overflow: visible;
}

:deep(.admin-activity-table .n-data-table-th) {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  white-space: nowrap;
}

:deep(.admin-activity-table .n-data-table-td) {
  vertical-align: top;
}

:deep(.admin-activity-table .admin-table-time-column),
:deep(.admin-activity-table .admin-table-time) {
  white-space: nowrap;
}

:deep(.admin-activity-table .n-data-table__pagination) {
  padding: 0 12px 10px;
  border-top: 1px solid var(--panel-border);
  background: #fff;
}

@media (max-width: 1520px) {
  .admin-filter-grid--activity {
    grid-auto-flow: row;
    grid-template-columns: repeat(3, var(--admin-filter-control-width));
  }
}

@media (max-width: 760px) {
  .admin-filter-grid--activity {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
