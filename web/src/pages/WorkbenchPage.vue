<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import type { EChartsOption } from "echarts";
import { NButton, NTable, NTag } from "naive-ui";

import { fetchTradingSummary } from "@/api/analysis";
import { fetchHealth } from "@/api/health";
import { fetchImportRuns, fetchImportStats } from "@/api/imports";
import type { HealthResponse, ImportRunRead, ImportStatsRead, TradingSummaryRead } from "@/api/types";
import EChartPanel from "@/components/EChartPanel.vue";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import StatCard from "@/components/StatCard.vue";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";
import { useAuthStore } from "@/stores/auth";
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

const runtime = useRuntimeStore();
const auth = useAuthStore();
const datasetContext = useDatasetContextStore();

const loading = ref(false);
const error = ref("");
usePageErrorNotification(error, "Workbench Error");

const health = ref<HealthResponse | null>(null);
const stats = ref<ImportStatsRead | null>(null);
const importRuns = ref<ImportRunRead[]>([]);
const currentSummary = ref<TradingSummaryRead | null>(null);

const isAdmin = auth.isAdmin;

const currentRunId = computed(() => datasetContext.state.importRunId ?? importRuns.value[0]?.id);
const currentRun = computed(() => importRuns.value.find((item) => item.id === currentRunId.value) ?? null);
const currentRunDisplayId = computed(() => currentRun.value?.display_id ?? currentRunId.value ?? null);

const currentRunName = computed(() => {
  if (currentRun.value) {
    return currentRun.value.dataset_name;
  }
  return currentRunId.value ? "当前上下文批次（不在最近列表）" : "";
});

const currentScopeLabel = computed(
  () => `${datasetContext.state.startDate || "起始不限"} ~ ${datasetContext.state.endDate || "结束不限"}`
);

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

const summaryCards = computed(() => [
  {
    label: isAdmin.value ? "当前可见批次" : "我的导入批次",
    value: String(stats.value?.total_runs ?? 0),
    hint: isAdmin.value ? "管理员可切换查看不同用户的数据集" : "当前账号可见范围内的全部批次",
    tone: "teal" as const,
  },
  {
    label: "成功批次",
    value: String(stats.value?.completed_runs ?? 0),
    hint: "已完成解析并写入数据库的导入批次数量",
    tone: "orange" as const,
  },
  {
    label: "累计记录",
    value: formatCompact(stats.value?.total_records ?? null, 2),
    hint: "当前可见范围内保留的交易记录总量",
    tone: "berry" as const,
  },
  {
    label: "可用数据集",
    value: String(stats.value?.available_datasets ?? 0),
    hint: "去重后的成功数据集数量",
    tone: "neutral" as const,
  },
  {
    label: "当前范围记录",
    value: String(currentSummary.value?.record_count ?? 0),
    hint: currentRun.value ? `当前批次 #${currentRun.value.display_id}` : "先选择一个数据集",
    tone: "teal" as const,
  },
  {
    label: "当前范围股票",
    value: String(currentSummary.value?.stock_count ?? 0),
    hint: datasetContext.state.stockCode || "当前数据集全部股票",
    tone: "orange" as const,
  },
]);

const monthlyChartOption = computed<EChartsOption | null>(() => {
  if (!stats.value?.monthly_imports.length) {
    return null;
  }

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
      left: 44,
      right: 24,
      top: 54,
      bottom: 28,
    },
    xAxis: {
      type: "category",
      data: stats.value.monthly_imports.map((item) => item.month),
      axisLabel: { color: "#526072" },
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
        data: stats.value.monthly_imports.map((item) => item.runs),
      },
      {
        type: "bar",
        name: "导入记录",
        yAxisIndex: 1,
        barMaxWidth: 22,
        itemStyle: {
          color: "#f05a28",
          borderRadius: [6, 6, 0, 0],
        },
        data: stats.value.monthly_imports.map((item) => item.records),
      },
    ],
  };
});

async function loadWorkbench() {
  loading.value = true;
  error.value = "";

  try {
    const [healthResponse, statsResponse] = await Promise.all([fetchHealth(), fetchImportStats()]);
    const runsResponse = await fetchImportRuns({
      limit: Math.max(statsResponse.total_runs, 1),
    });

    health.value = healthResponse;
    stats.value = statsResponse;
    importRuns.value = runsResponse;

    const selectedRunId =
      datasetContext.state.importRunId && runsResponse.some((item) => item.id === datasetContext.state.importRunId)
        ? datasetContext.state.importRunId
        : runsResponse[0]?.id;

    if (selectedRunId !== datasetContext.state.importRunId) {
      datasetContext.applyScope({
        importRunId: selectedRunId,
        stockCode: "",
        startDate: "",
        endDate: "",
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

onMounted(() => {
  void loadWorkbench();
});
</script>

<template>
  <div class="page">
    <section class="page__header">
      <div>
        <div class="page__eyebrow">Workbench / 工作台</div>
        <h2 class="page__title">后台工作台集中展示系统状态、导入趋势与当前数据集摘要</h2>
        <p class="page__subtitle">
          这里作为新的后台首页，用来快速确认服务是否可用、最近导入是否正常，以及当前共享分析范围是否设置正确。
        </p>
      </div>
      <div class="page__actions">
        <n-button type="primary" :loading="loading" @click="loadWorkbench">刷新工作台</n-button>
      </div>
    </section>

    <section class="page__grid page__grid--stats">
      <StatCard
        v-for="item in summaryCards"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :tone="item.tone"
      />
    </section>

    <section class="page__grid page__grid--double">
      <PanelCard
        :title="isAdmin ? '系统健康状态' : '系统可用状态'"
        :description="
          isAdmin
            ? '管理员可以查看完整的服务与数据库状态。'
            : '普通用户可快速确认当前系统是否可正常使用。'
        "
      >
        <div v-if="health" class="detail-grid">
          <div class="detail-grid__item">
            <span class="detail-grid__label">状态</span>
            <div class="detail-grid__value">
              <n-tag :type="toStatusTagType(health.status)" round>{{ health.status }}</n-tag>
            </div>
          </div>
          <div v-if="isAdmin" class="detail-grid__item">
            <span class="detail-grid__label">环境</span>
            <div class="detail-grid__value">{{ health.environment }}</div>
          </div>
          <div v-if="isAdmin" class="detail-grid__item">
            <span class="detail-grid__label">数据库</span>
            <div class="detail-grid__value">{{ health.database_ok ? "连接正常" : "连接失败" }}</div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">详情</span>
            <div class="detail-grid__value">
              {{
                isAdmin
                  ? health.detail
                  : health.status === "ok"
                    ? "当前系统服务可正常使用"
                    : "当前系统存在异常，请稍后重试。"
              }}
            </div>
          </div>
        </div>
        <EmptyState
          v-else
          title="暂无健康状态"
          description="点击刷新工作台后，这里会显示当前后端服务和数据库的连通情况。"
        />
      </PanelCard>

      <PanelCard title="当前分析上下文" description="共享数据集范围会在工作台、分析中心和算法雷达之间同步。">
        <div v-if="currentRunId" class="detail-grid">
          <div class="detail-grid__item">
            <span class="detail-grid__label">批次</span>
            <div class="detail-grid__value">#{{ currentRunDisplayId }} · {{ currentRunName }}</div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">股票</span>
            <div class="detail-grid__value">{{ datasetContext.state.stockCode || "全部股票" }}</div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">日期范围</span>
            <div class="detail-grid__value">{{ currentScopeLabel }}</div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">当前摘要</span>
            <div class="detail-grid__value">
              {{
                currentSummary
                  ? `收盘均价 ${formatNumberish(currentSummary.average_close, 2)}，成交额 ${formatCompact(currentSummary.total_amount, 2)}`
                  : "尚未选择可分析的数据范围。"
              }}
            </div>
          </div>
        </div>
        <EmptyState
          v-else
          title="暂无共享数据"
          description="导入成功后，工作台会自动以最近批次作为默认分析范围。"
        />
      </PanelCard>
    </section>

    <section class="page__grid page__grid--double">
      <PanelCard title="月度导入趋势" description="展示最近各月份导入批次和记录量的变化。">
        <EChartPanel v-if="monthlyChartOption" :option="monthlyChartOption" :loading="loading" height="320px" />
        <EmptyState
          v-else
          title="暂无导入趋势数据"
          description="完成一次或多次数据导入后，这里会显示月度导入统计趋势。"
        />
      </PanelCard>

      <PanelCard title="当前数据集摘要" description="工作台优先展示当前共享范围下的核心交易概览。">
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

    <PanelCard title="最近导入批次" description="这里保留最近几个批次的状态和规模，方便快速回看。">
      <div v-if="importRuns.length" class="data-table-wrap">
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
                <n-tag :type="toStatusTagType(item.status)" round size="small">{{ item.status }}</n-tag>
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
