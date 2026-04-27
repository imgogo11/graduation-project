<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { NButton, NDatePicker, NForm, NFormItem, NInput, NPagination, NSelect, NTable, NTag, useMessage } from "naive-ui";

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

      <div v-if="logs?.rows.length" class="data-table-wrap">
        <n-table class="data-table" striped size="small" :single-line="false">
          <thead>
            <tr>
              <th>时间</th>
              <th>分类</th>
              <th>事件</th>
              <th>执行人</th>
              <th>目标</th>
              <th>路径</th>
              <th>结果</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in logs?.rows" :key="row.id">
              <td>{{ formatDateTime(row.occurred_at) }}</td>
              <td>{{ formatAuditCategory(row.category) }}</td>
              <td>{{ formatAuditEvent(row.event_type) }}</td>
              <td>{{ row.actor_username_snapshot || "--" }}</td>
              <td>{{ row.target_label || "--" }}</td>
              <td>{{ row.request_path || "--" }}</td>
              <td>
                <n-tag :type="row.success ? 'success' : 'error'" round size="small">
                  {{ row.success ? "成功" : `失败(${row.status_code || "-"})` }}
                </n-tag>
              </td>
            </tr>
          </tbody>
        </n-table>
        <div class="table-pagination">
          <n-pagination
            :page="page"
            :page-size="pageSize"
            :item-count="logs?.total || 0"
            :page-sizes="[10, 20, 50, 100]"
            show-size-picker
            @update:page="updatePage"
            @update:page-size="updatePageSize"
          />
        </div>
      </div>
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
