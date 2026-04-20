<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { NButton, NForm, NFormItem, NInput, NPagination, NSelect, NTable, NTag } from "naive-ui";

import { fetchAdminAuditLogStats, fetchAdminAuditLogs } from "@/api/admin";
import type { AuditLogListRead, AuditLogStatsRead } from "@/api/types";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import StatCard from "@/components/StatCard.vue";
import { useRuntimeStore } from "@/stores/runtime";
import { formatAuditCategory, formatAuditEvent } from "@/utils/audit";
import { formatDateTime, getErrorMessage } from "@/utils/format";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";


type SuccessFilter = "all" | "success" | "failed";

const runtime = useRuntimeStore();
const loading = ref(false);
const error = ref("");
usePageErrorNotification(error, "调用记录加载失败");
const logs = ref<AuditLogListRead | null>(null);
const stats = ref<AuditLogStatsRead | null>(null);
const page = ref(1);
const pageSize = ref(20);

const actorUserIdInput = ref("");
const category = ref("");
const successFilter = ref<SuccessFilter>("all");
const startAt = ref("");
const endAt = ref("");

const successOptions = [
  { label: "全部结果", value: "all" },
  { label: "仅成功", value: "success" },
  { label: "仅失败", value: "failed" },
];

const categoryOptions = computed(() =>
  (stats.value?.category_breakdown || []).map((item) => ({
    label: `${formatAuditCategory(item.category)} (${item.total})`,
    value: item.category,
  }))
);

const actorUserId = computed(() => {
  const parsed = Number(actorUserIdInput.value.trim());
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
});

const successValue = computed(() => {
  if (successFilter.value === "success") {
    return true;
  }
  if (successFilter.value === "failed") {
    return false;
  }
  return undefined;
});

const cards = computed(() => [
  {
    label: "总事件数",
    value: String(stats.value?.total_events ?? 0),
    hint: "当前筛选条件下审计事件总量",
    tone: "teal" as const,
  },
  {
    label: "成功事件",
    value: String(stats.value?.success_events ?? 0),
    hint: "状态码 < 400 的事件数",
    tone: "neutral" as const,
  },
  {
    label: "失败事件",
    value: String(stats.value?.failed_events ?? 0),
    hint: "状态码 >= 400 的事件数",
    tone: "berry" as const,
  },
  {
    label: "今日事件",
    value: String(stats.value?.today_events ?? 0),
    hint: "当天累计审计事件",
    tone: "orange" as const,
  },
]);

function toIso(value: string) {
  if (!value) {
    return undefined;
  }
  const iso = new Date(value).toISOString();
  return iso === "Invalid Date" ? undefined : iso;
}

async function loadStats() {
  stats.value = await fetchAdminAuditLogStats({
    actor_user_id: actorUserId.value,
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
    actor_user_id: actorUserId.value,
    category: category.value || undefined,
    success: successValue.value,
    start_at: toIso(startAt.value),
    end_at: toIso(endAt.value),
  });
}

async function refreshPage() {
  loading.value = true;
  error.value = "";
  try {
    await Promise.all([loadStats(), loadLogs()]);
    runtime.markSynced();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loading.value = false;
  }
}

function applyFilter() {
  page.value = 1;
  void refreshPage();
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
    <section class="page__header">
      <div>
        <div class="page__eyebrow">管理后台 / 调用记录</div>
        <h2 class="page__title">用户调用记录</h2>
        <p class="page__subtitle">汇总关键操作与分析访问审计日志，用于管理员追踪系统后台行为</p>
      </div>
      <div class="page__actions">
        <n-button type="primary" :loading="loading" @click="refreshPage">刷新</n-button>
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

    <PanelCard title="审计统计概览" description="帮助定位近期异常操作与失败趋势">
      <div v-if="stats" class="detail-grid">
        <div class="detail-grid__item">
          <span class="detail-grid__label">总事件数</span>
          <div class="detail-grid__value">{{ stats.total_events }}</div>
        </div>
        <div class="detail-grid__item">
          <span class="detail-grid__label">成功事件</span>
          <div class="detail-grid__value">{{ stats.success_events }}</div>
        </div>
        <div class="detail-grid__item">
          <span class="detail-grid__label">失败事件</span>
          <div class="detail-grid__value">{{ stats.failed_events }}</div>
        </div>
        <div class="detail-grid__item">
          <span class="detail-grid__label">活跃操作</span>
          <div class="detail-grid__value">{{ stats.unique_actor_count }}</div>
        </div>
      </div>
      <EmptyState v-else title="暂无审计统计" description="点击刷新后展示审计统计结果" />
    </PanelCard>

    <PanelCard title="审计日志" description="支持按用户、分类、结果和时间范围筛选">
      <n-form class="filter-form filter-form--audit" style="margin-bottom: 16px;">
        <n-form-item label="用户ID">
          <n-input v-model:value="actorUserIdInput" clearable placeholder="输入用户ID" />
        </n-form-item>
        <n-form-item label="分类">
          <n-select
            v-model:value="category"
            clearable
            filterable
            :options="categoryOptions"
            placeholder="选择分类"
            style="min-width: 180px;"
          />
        </n-form-item>
        <n-form-item label="结果">
          <n-select
            v-model:value="successFilter"
            :options="successOptions"
            style="min-width: 140px;"
          />
        </n-form-item>
        <n-form-item label="开始时间">
          <input v-model="startAt" type="datetime-local" />
        </n-form-item>
        <n-form-item label="结束时间">
          <input v-model="endAt" type="datetime-local" />
        </n-form-item>
        <n-form-item label="&nbsp;" class="filter-form__action-item">
          <n-button
            class="filter-form__action-btn filter-form__action-btn--highlight"
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


