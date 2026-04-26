<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import type { EChartsOption } from "echarts";
import { NButton, NTable, NTag } from "naive-ui";

import { fetchTradingSummary } from "@/api/analysis";
import { fetchImportRuns, fetchImportStats } from "@/api/imports";
import type { ImportRunRead, ImportStatsRead, TradingSummaryRead } from "@/api/types";
import EChartPanel from "@/components/EChartPanel.vue";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";
import { useDatasetContextStore } from "@/stores/datasetContext";
import { useRuntimeStore } from "@/stores/runtime";
import {
  formatCompact,
  formatDate,
  formatDateTime,
  formatNumberish,
  getErrorMessage,
  toStatusTagType,
} from "@/utils/format";
import { formatStatusText } from "@/utils/displayText";

type TrendGranularity = "day" | "month";

const runtime = useRuntimeStore();
const datasetContext = useDatasetContextStore();
const router = useRouter();

const loading = ref(false);
const error = ref("");
const trendGranularity = ref<TrendGranularity>("month");
usePageErrorNotification(error, "工作台加载失败");

const stats = ref<ImportStatsRead | null>(null);
const importRuns = ref<ImportRunRead[]>([]);
const currentSummary = ref<TradingSummaryRead | null>(null);

const currentRunId = computed(() => datasetContext.state.importRunId ?? importRuns.value[0]?.id);

const recentImportRuns = computed(() => {
  const latestRuns = importRuns.value.slice(0, 8);

  if (!currentRunId.value || latestRuns.some((item) => item.id === currentRunId.value)) {
    return latestRuns;
  }

  const selectedRun = importRuns.value.find((item) => item.id === currentRunId.value);
  if (selectedRun) {
    return [selectedRun, ...latestRuns.slice(0, 7)];
  }

  return [
    {
      id: currentRunId.value,
      display_id: currentRunId.value,
      owner_user_id: null,
      owner_username: null,
      dataset_name: "当前上下文批次（不在最近列表）",
      source_type: "context",
      source_name: "context",
      original_file_name: null,
      file_format: null,
      status: "context",
      started_at: "",
      completed_at: null,
      record_count: currentSummary.value?.record_count ?? null,
      error_message: null,
      deleted_at: null,
    } satisfies ImportRunRead,
    ...latestRuns.slice(0, 7),
  ];
});

const recentImportTitlePills = computed(() => [
  {
    label: "我的导入批次",
    value: String(stats.value?.total_runs ?? 0),
  },
  {
    label: "成功批次",
    value: String(stats.value?.completed_runs ?? 0),
  },
  {
    label: "累计记录",
    value: formatCompact(stats.value?.total_records ?? null, 2),
  },
  {
    label: "可用数据集",
    value: String(stats.value?.available_datasets ?? 0),
  },
]);

const currentDatasetTitlePills = computed(() => [
  {
    label: "当前范围记录",
    value: String(currentSummary.value?.record_count ?? 0),
  },
  {
    label: "当前范围股票",
    value: String(currentSummary.value?.stock_count ?? 0),
  },
]);

const trendGranularityOptions: Array<{ label: string; value: TrendGranularity }> = [
  { label: "日", value: "day" },
  { label: "月", value: "month" },
];

const importTrendRows = computed(() => {
  const buckets = new Map<string, { label: string; runs: number; records: number }>();

  for (const item of importRuns.value) {
    const timestamp = item.completed_at || item.started_at;
    if (!timestamp) {
      continue;
    }

    const label = trendGranularity.value === "day" ? timestamp.slice(0, 10) : timestamp.slice(0, 7);
    const bucket = buckets.get(label) ?? {
      label,
      runs: 0,
      records: 0,
    };

    bucket.runs += 1;
    bucket.records += item.record_count ?? 0;
    buckets.set(label, bucket);
  }

  return [...buckets.values()].sort((left, right) => left.label.localeCompare(right.label));
});

const importTrendOption = computed<EChartsOption | null>(() => {
  if (!importTrendRows.value.length) {
    return null;
  }

  const isDaily = trendGranularity.value === "day";

  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(15, 23, 42, 0.92)",
      borderWidth: 0,
      textStyle: { color: "#f8fafc" },
    },
    legend: {
      top: 4,
      textStyle: { color: "#526072" },
    },
    grid: {
      left: 56,
      right: 56,
      top: 68,
      bottom: isDaily ? 56 : 36,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: importTrendRows.value.map((item) => item.label),
      axisLabel: {
        color: "#526072",
        rotate: isDaily ? 35 : 0,
        hideOverlap: true,
      },
    },
    yAxis: [
      {
        type: "value",
        name: "批次",
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
        name: "导入批次",
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 3, color: "#2f6fed" },
        areaStyle: { color: "rgba(47, 111, 237, 0.12)" },
        data: importTrendRows.value.map((item) => item.runs),
      },
      {
        type: "bar",
        name: "导入记录",
        yAxisIndex: 1,
        barMaxWidth: isDaily ? 18 : 22,
        itemStyle: {
          color: "#f05a28",
          borderRadius: [6, 6, 0, 0],
        },
        data: importTrendRows.value.map((item) => item.records),
      },
    ],
  };
});

async function loadWorkbench() {
  loading.value = true;
  error.value = "";

  try {
    const statsResponse = await fetchImportStats();
    const runsResponse = await fetchImportRuns({
      limit: Math.max(statsResponse.total_runs, 1),
    });

    stats.value = statsResponse;
    importRuns.value = runsResponse;

    const selectedRunId =
      datasetContext.state.importRunId && runsResponse.some((item) => item.id === datasetContext.state.importRunId)
        ? datasetContext.state.importRunId
        : runsResponse[0]?.id;
    const selectedRun = runsResponse.find((item) => item.id === selectedRunId) ?? null;

    if (selectedRunId !== datasetContext.state.importRunId) {
      datasetContext.applyScope({
        importRunId: selectedRunId,
        importRunDisplayId: selectedRun?.display_id,
        stockCode: "",
        startDate: "",
        endDate: "",
      });
    } else if (selectedRun?.display_id !== datasetContext.state.importRunDisplayId) {
      datasetContext.applyScope({
        importRunDisplayId: selectedRun?.display_id,
      });
    }

    if (selectedRunId) {
      currentSummary.value = await fetchTradingSummary({
        import_run_id: selectedRunId,
        stock_code: datasetContext.state.stockCode || undefined,
        start_date: datasetContext.state.startDate || undefined,
        end_date: datasetContext.state.endDate || undefined,
      });
    } else {
      currentSummary.value = null;
    }

    runtime.markSynced();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loading.value = false;
  }
}

function goToDatasets() {
  void router.push({ name: "datasets" });
}

onMounted(() => {
  void loadWorkbench();
});
</script>

<template>
  <div class="page">
    <section class="page__grid page__grid--double">
      <PanelCard title="导入趋势">
        <template #actions>
          <div class="trend-segmented" aria-label="导入趋势切换">
            <button
              v-for="option in trendGranularityOptions"
              :key="option.value"
              type="button"
              class="trend-segmented__button"
              :class="{ 'trend-segmented__button--active': trendGranularity === option.value }"
              :aria-pressed="trendGranularity === option.value"
              @click="trendGranularity = option.value"
            >
              {{ option.label }}
            </button>
          </div>
        </template>
        <EChartPanel v-if="importTrendOption" :option="importTrendOption" :loading="loading" height="320px" />
        <EmptyState
          v-else
          title="暂无导入趋势数据"
          description="完成一次或多次数据导入后，这里会显示月度导入统计趋势。"
        />
      </PanelCard>

      <PanelCard title="当前数据集摘要">
        <template #title>
          <span class="page-card__title">
            <span>当前数据集摘要</span>
            <span class="page-card__stats">
              <span v-for="item in currentDatasetTitlePills" :key="item.label" class="pill page-card__pill">
                {{ item.label }} {{ item.value }}
              </span>
            </span>
          </span>
        </template>
        <div v-if="currentSummary" class="detail-grid">
          <div class="detail-grid__item">
            <span class="detail-grid__label">时间跨度</span>
            <div class="detail-grid__value">{{ formatDate(currentSummary.start_date) }} ~ {{ formatDate(currentSummary.end_date) }}</div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">最新收盘价</span>
            <div class="detail-grid__value">{{ formatNumberish(currentSummary.latest_close, 2) }}</div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">平均成交量</span>
            <div class="detail-grid__value">{{ formatCompact(currentSummary.average_volume, 2) }}</div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">平均振幅</span>
            <div class="detail-grid__value">{{ formatNumberish(currentSummary.average_amplitude, 4) }}</div>
          </div>
        </div>
        <EmptyState
          v-else
          title="暂无数据集摘要"
          description="请先导入数据，或者在数据集管理页选择一个有效批次。"
        />
      </PanelCard>
    </section>

    <PanelCard title="最近导入批次">
      <template #title>
        <span class="page-card__title">
          <span>最近导入批次</span>
          <span class="page-card__stats">
            <span v-for="item in recentImportTitlePills" :key="item.label" class="pill page-card__pill">
              {{ item.label }} {{ item.value }}
            </span>
          </span>
        </span>
      </template>
      <template #actions>
        <n-button quaternary size="small" @click="goToDatasets">查看全部</n-button>
      </template>
      <div v-if="importRuns.length" class="data-table-wrap workbench-recent-runs-table">
        <n-table class="data-table" striped size="small" :single-line="false">
          <thead>
            <tr>
              <th>批次</th>
              <th>数据集</th>
              <th>来源</th>
              <th>状态</th>
              <th>记录</th>
              <th>完成时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in recentImportRuns" :key="item.id" :class="{ 'data-table__row--active': item.id === currentRunId }">
              <td>#{{ item.display_id }}</td>
              <td>{{ item.dataset_name }}</td>
              <td>{{ item.original_file_name || item.source_name }}</td>
              <td>
                <n-tag :type="toStatusTagType(item.status)" round size="small">
                  {{ formatStatusText(item.status) }}
                </n-tag>
              </td>
              <td>{{ formatCompact(item.record_count ?? null, 2) }}</td>
              <td>{{ formatDateTime(item.completed_at || item.started_at) }}</td>
            </tr>
          </tbody>
        </n-table>
      </div>
      <EmptyState
        v-else
        title="暂无导入批次"
        description="上传交易文件并导入成功后，这里会显示最近的数据集批次。"
      />
    </PanelCard>
  </div>
</template>

<style scoped>
.page-card__title {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.page-card__stats {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.page-card__pill {
  padding: 5px 10px;
  font-size: 12px;
}

.trend-segmented {
  display: inline-flex;
  align-items: center;
  padding: 4px;
  border-radius: 999px;
  background: rgba(47, 111, 237, 0.08);
}

.trend-segmented__button {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  padding: 7px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.trend-segmented__button--active {
  background: #fff;
  color: var(--accent-blue);
  box-shadow: 0 8px 20px rgba(47, 111, 237, 0.12);
}

.workbench-recent-runs-table {
  min-height: 0;
  max-height: none;
  overflow-y: visible;
  overflow-x: auto;
  resize: none;
}
</style>
