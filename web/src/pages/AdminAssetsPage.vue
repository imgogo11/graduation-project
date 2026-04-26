<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import type { EChartsOption } from "echarts";
import { NTable } from "naive-ui";

import { fetchAdminAssetOverview } from "@/api/admin";
import type { AdminAssetOverviewRead, AdminAssetSummaryRead } from "@/api/types";
import EChartPanel from "@/components/EChartPanel.vue";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";
import { useRuntimeStore } from "@/stores/runtime";
import { formatCompact, formatDate, formatDateTime, formatPercent, getErrorMessage } from "@/utils/format";


type GrowthGranularity = "day" | "month";

const EMPTY_SUMMARY: AdminAssetSummaryRead = {
  owner_count: 0,
  unique_stock_count: 0,
  largest_dataset_records: 0,
  median_dataset_records: 0,
  first_trade_date: null,
  last_trade_date: null,
  latest_imported_at: null,
};

const runtime = useRuntimeStore();
const loading = ref(false);
const error = ref("");
usePageErrorNotification(error, "数据资产加载失败");
const overview = ref<AdminAssetOverviewRead | null>(null);
const growthGranularity = ref<GrowthGranularity>("month");

const summary = computed(() => overview.value?.summary ?? EMPTY_SUMMARY);

const summaryPills = computed(() => [
  {
    label: "资产用户数",
    value: String(summary.value.owner_count),
  },
  {
    label: "最大单批记录",
    value: formatCompact(summary.value.largest_dataset_records, 2),
  },
  {
    label: "中位单批记录",
    value: formatCompact(summary.value.median_dataset_records, 2),
  },
]);

const coverageRangeLabel = computed(() => {
  if (!summary.value.first_trade_date || !summary.value.last_trade_date) {
    return "--";
  }
  return `${formatDate(summary.value.first_trade_date)} ~ ${formatDate(summary.value.last_trade_date)}`;
});

const growthGranularityOptions: Array<{ label: string; value: GrowthGranularity }> = [
  { label: "日", value: "day" },
  { label: "月", value: "month" },
];

const growthRows = computed(() => {
  if (growthGranularity.value === "day") {
    return (overview.value?.growth_daily ?? []).map((item) => ({
      label: item.day,
      cumulative_datasets: item.cumulative_datasets,
      cumulative_records: item.cumulative_records,
    }));
  }

  return (overview.value?.growth ?? []).map((item) => ({
    label: item.month,
    cumulative_datasets: item.cumulative_datasets,
    cumulative_records: item.cumulative_records,
  }));
});

const growthChartOption = computed<EChartsOption | null>(() => {
  const rows = growthRows.value;
  if (!rows.length) {
    return null;
  }

  const showPoint = rows.length === 1;

  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(15, 23, 42, 0.92)",
      borderWidth: 0,
      textStyle: { color: "#f8fafc" },
    },
    legend: {
      top: 0,
      textStyle: { color: "#526072" },
    },
    grid: {
      left: 48,
      right: 24,
      top: 56,
      bottom: 28,
    },
    xAxis: {
      type: "category",
      data: rows.map((item) => item.label),
      axisLabel: {
        color: "#526072",
        hideOverlap: true,
      },
    },
    yAxis: [
      {
        type: "value",
        name: "数据集",
        axisLabel: { color: "#526072" },
        splitLine: {
          lineStyle: { color: "rgba(82, 96, 114, 0.12)" },
        },
      },
      {
        type: "value",
        name: "记录",
        axisLabel: { color: "#526072" },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        type: "line",
        name: "累计数据集数",
        smooth: true,
        showSymbol: showPoint,
        symbolSize: showPoint ? 10 : 6,
        lineStyle: { width: 3, color: "#2f6fed" },
        areaStyle: { color: "rgba(47, 111, 237, 0.12)" },
        data: rows.map((item) => item.cumulative_datasets),
      },
      {
        type: "line",
        name: "累计记录数",
        yAxisIndex: 1,
        smooth: true,
        showSymbol: showPoint,
        symbolSize: showPoint ? 10 : 6,
        lineStyle: { width: 3, color: "#f05a28" },
        areaStyle: { color: "rgba(240, 90, 40, 0.10)" },
        data: rows.map((item) => item.cumulative_records),
      },
    ],
  };
});

const sizeBucketChartOption = computed<EChartsOption | null>(() => {
  const rows = overview.value?.size_buckets ?? [];
  if (!rows.length) {
    return null;
  }

  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(15, 23, 42, 0.92)",
      borderWidth: 0,
      textStyle: { color: "#f8fafc" },
      formatter: (params: any) => {
        const points = Array.isArray(params) ? params : [params];
        const point = rows[points[0]?.dataIndex ?? 0];
        if (!point) {
          return "";
        }
        return [
          point.bucket_label,
          `${points[0]?.seriesName || "数据集数"}：${point.dataset_count}`,
          `记录规模：${formatCompact(point.record_count, 2)}`,
        ].join("<br/>");
      },
    },
    grid: {
      left: 52,
      right: 24,
      top: 40,
      bottom: 28,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: rows.map((item) => item.bucket_label),
      axisLabel: { color: "#526072" },
    },
    yAxis: {
      type: "value",
      name: "数据集数",
      nameLocation: "end",
      nameGap: 18,
      nameRotate: 0,
      nameTextStyle: {
        color: "#526072",
        align: "left",
        verticalAlign: "bottom",
        padding: [0, 0, 6, 4],
      },
      axisLabel: { color: "#526072" },
      splitLine: {
        lineStyle: { color: "rgba(82, 96, 114, 0.12)" },
      },
    },
    series: [
      {
        type: "bar",
        name: "数据集数",
        barMaxWidth: 42,
        itemStyle: {
          color: "#2f6fed",
          borderRadius: [8, 8, 0, 0],
        },
        data: rows.map((item) => item.dataset_count),
      },
    ],
  };
});

async function loadPage() {
  loading.value = true;
  error.value = "";
  try {
    overview.value = await fetchAdminAssetOverview();
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
    <section class="assets-layout-row">
      <PanelCard class="assets-panel assets-panel--table" title="所属用户资产分布">
        <div v-if="overview?.owner_rows.length" class="data-table-wrap assets-table-wrap">
          <n-table class="data-table assets-table assets-table--owner" striped size="small" :single-line="false">
            <thead>
              <tr>
                <th>用户ID</th>
                <th>用户</th>
                <th>数据集数</th>
                <th>记录</th>
                <th>记录占比</th>
                <th>平均单批规模</th>
                <th>最近入库</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in overview.owner_rows" :key="row.owner_user_id">
                <td>{{ row.owner_user_id }}</td>
                <td>{{ row.owner_username || "--" }}</td>
                <td>{{ row.dataset_count }}</td>
                <td>{{ formatCompact(row.record_count, 2) }}</td>
                <td>{{ formatPercent(row.record_share_ratio, 2) }}</td>
                <td>{{ formatCompact(row.avg_records_per_dataset, 2) }}</td>
                <td>{{ formatDate(row.latest_completed_at) }}</td>
              </tr>
            </tbody>
          </n-table>
        </div>
        <EmptyState
          v-else
          title="暂无所属用户资产分布"
          description="当前没有可展示的用户资产分布统计。"
        />
      </PanelCard>

      <PanelCard class="assets-panel assets-panel--chart" title="资产累积增长">
        <template #title>
          <span class="assets-card__title">
            <span>资产累积增长</span>
            <span class="assets-card__stats">
              <span v-for="item in summaryPills" :key="item.label" class="pill assets-card__pill">
                {{ item.label }} {{ item.value }}
              </span>
            </span>
          </span>
        </template>
        <template #actions>
          <div class="assets-segmented" aria-label="资产增长视图切换">
            <button
              v-for="option in growthGranularityOptions"
              :key="option.value"
              type="button"
              class="assets-segmented__button"
              :class="{ 'assets-segmented__button--active': growthGranularity === option.value }"
              :aria-pressed="growthGranularity === option.value"
              @click="growthGranularity = option.value"
            >
              {{ option.label }}
            </button>
          </div>
        </template>

        <div class="detail-grid assets-card__meta">
          <div class="detail-grid__item">
            <span class="detail-grid__label">覆盖时间范围</span>
            <div class="detail-grid__value">{{ coverageRangeLabel }}</div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">最近入库</span>
            <div class="detail-grid__value">{{ formatDateTime(summary.latest_imported_at) }}</div>
          </div>
        </div>

        <div v-if="growthChartOption" class="assets-chart-wrap">
          <EChartPanel :option="growthChartOption" :loading="loading" height="100%" />
        </div>
        <EmptyState
          v-else
          title="暂无资产增长数据"
          description="完成至少一次有效数据导入后，这里会展示累计资产的增长趋势。"
        />
      </PanelCard>
    </section>

    <section class="assets-layout-row">
      <PanelCard class="assets-panel assets-panel--table" title="大数据集 TOP 10">
        <div v-if="overview?.top_datasets.length" class="data-table-wrap assets-table-wrap">
          <n-table class="data-table assets-table assets-table--datasets" striped size="small" :single-line="false">
            <thead>
              <tr>
                <th>数据集</th>
                <th>所属用户</th>
                <th>记录</th>
                <th>完成时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in overview.top_datasets" :key="row.run_id">
                <td>#{{ row.display_id }} · {{ row.dataset_name }}</td>
                <td>{{ row.owner_username || "--" }}</td>
                <td>{{ formatCompact(row.record_count, 2) }}</td>
                <td>{{ formatDate(row.completed_at) }}</td>
              </tr>
            </tbody>
          </n-table>
        </div>
        <EmptyState
          v-else
          title="暂无大数据集排行"
          description="完成有效导入后，这里会展示记录规模最大的资产数据集。"
        />
      </PanelCard>

      <PanelCard class="assets-panel assets-panel--chart" title="单批规模分层">
        <div v-if="sizeBucketChartOption" class="assets-chart-wrap">
          <EChartPanel :option="sizeBucketChartOption" :loading="loading" height="100%" />
        </div>
        <EmptyState
          v-else
          title="暂无规模分层"
          description="当前没有可用于统计的数据集规模分层。"
        />
      </PanelCard>
    </section>
  </div>
</template>

<style scoped>
.assets-layout-row {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: 16px;
  align-items: stretch;
}

.assets-panel {
  display: grid;
  grid-template-rows: auto 1fr;
  height: 100%;
}

.assets-panel--table :deep(.panel-card__body),
.assets-panel--chart :deep(.panel-card__body) {
  display: flex;
  flex-direction: column;
}

.assets-card__title {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.assets-card__stats {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.assets-card__pill {
  padding: 5px 10px;
  font-size: 12px;
}

.assets-card__meta {
  margin-bottom: 16px;
}

.assets-segmented {
  display: inline-flex;
  align-items: center;
  padding: 4px;
  border-radius: 999px;
  background: rgba(47, 111, 237, 0.08);
}

.assets-segmented__button {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  padding: 7px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.18s ease, color 0.18s ease;
}

.assets-segmented__button--active {
  background: #fff;
  color: var(--accent-blue);
  box-shadow: 0 8px 20px rgba(47, 111, 237, 0.12);
}

.assets-chart-wrap {
  flex: 1;
  min-height: 320px;
}

.assets-chart-wrap :deep(.chart-panel) {
  height: 100%;
}

.assets-chart-wrap :deep(.chart-panel__canvas) {
  height: 100% !important;
}

.assets-table-wrap {
  flex: 1;
  max-height: none;
  min-height: 320px;
  resize: none;
  overflow-x: visible;
}

.assets-table {
  width: 100%;
  min-width: 0;
  table-layout: fixed;
}

.assets-table :deep(th),
.assets-table :deep(td) {
  padding: 12px 10px;
  font-size: 13px;
  line-height: 1.5;
  white-space: normal;
  word-break: break-word;
}

.assets-table--owner :deep(th:nth-child(1)),
.assets-table--owner :deep(td:nth-child(1)) {
  width: 9%;
}

.assets-table--owner :deep(th:nth-child(2)),
.assets-table--owner :deep(td:nth-child(2)) {
  width: 13%;
}

.assets-table--owner :deep(th:nth-child(3)),
.assets-table--owner :deep(td:nth-child(3)) {
  width: 12%;
}

.assets-table--owner :deep(th:nth-child(4)),
.assets-table--owner :deep(td:nth-child(4)) {
  width: 12%;
}

.assets-table--owner :deep(th:nth-child(5)),
.assets-table--owner :deep(td:nth-child(5)) {
  width: 14%;
}

.assets-table--owner :deep(th:nth-child(6)),
.assets-table--owner :deep(td:nth-child(6)) {
  width: 18%;
}

.assets-table--owner :deep(th:nth-child(7)),
.assets-table--owner :deep(td:nth-child(7)) {
  width: 22%;
}

.assets-table--datasets :deep(th:nth-child(1)),
.assets-table--datasets :deep(td:nth-child(1)) {
  width: 42%;
}

.assets-table--datasets :deep(th:nth-child(2)),
.assets-table--datasets :deep(td:nth-child(2)) {
  width: 18%;
}

.assets-table--datasets :deep(th:nth-child(3)),
.assets-table--datasets :deep(td:nth-child(3)) {
  width: 16%;
}

.assets-table--datasets :deep(th:nth-child(4)),
.assets-table--datasets :deep(td:nth-child(4)) {
  width: 24%;
}

@media (max-width: 1280px) {
  .assets-layout-row {
    grid-template-columns: 1fr;
  }
}
</style>
