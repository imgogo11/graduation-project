<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import type { EChartsOption } from "echarts";

import { fetchTradingJointAnomalyRanking, fetchTradingSummary } from "@/api/analysis";
import { fetchImportRuns } from "@/api/imports";
import {
  fetchAlgoIndexStatus,
  fetchRiskRadarCalendar,
  fetchRiskRadarEventContext,
  fetchRiskRadarEvents,
  fetchRiskRadarStocks,
  fetchRiskRadarOverview,
  rebuildAlgoIndex,
} from "@/api/riskRadar";
import { fetchTradingStocks, fetchTradingRangeKthVolume, fetchTradingRangeMaxAmount } from "@/api/trading";
import type {
  AlgoIndexStatusRead,
  ImportRunRead,
  TradingStockRead,
  TradingJointAnomalyRankingRead,
  TradingRangeKthVolumeRead,
  TradingRangeMaxAmountRead,
  TradingRiskRadarCalendarDayRead,
  TradingRiskRadarEventContextRead,
  TradingRiskRadarEventRead,
  TradingRiskRadarOverviewRead,
  TradingSummaryRead,
  TradingStockRiskProfileRead,
} from "@/api/types";
import EChartPanel from "@/components/EChartPanel.vue";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import StatCard from "@/components/StatCard.vue";
import { useAuthStore } from "@/stores/auth";
import { useDatasetContextStore } from "@/stores/datasetContext";
import { useRuntimeStore } from "@/stores/runtime";
import {
  formatCompact,
  formatDate,
  formatDateTime,
  formatNumberish,
  formatPercent,
  getErrorMessage,
  isDataInsufficientMessage,
  toNumber,
  toStatusTagType,
} from "@/utils/format";


const runtime = useRuntimeStore();
const auth = useAuthStore();
const datasetContext = useDatasetContextStore();
const loadingRuns = ref(false);
const loadingAlgo = ref(false);
const loadingRadar = ref(false);
const rebuilding = ref(false);
const error = ref("");
const importRuns = ref<ImportRunRead[]>([]);
const stocks = ref<TradingStockRead[]>([]);
const algoSummary = ref<TradingSummaryRead | null>(null);
const algoResult = ref<TradingRangeMaxAmountRead | null>(null);
const algoKthResult = ref<TradingRangeKthVolumeRead | null>(null);
const jointAnomalies = ref<TradingJointAnomalyRankingRead | null>(null);
const algoNotice = ref("");
const algoKthNotice = ref("");
const jointNotice = ref("");
const indexStatus = ref<AlgoIndexStatusRead | null>(null);
const overview = ref<TradingRiskRadarOverviewRead | null>(null);
const events = ref<TradingRiskRadarEventRead[]>([]);
const stockProfiles = ref<TradingStockRiskProfileRead[]>([]);
const calendarRows = ref<TradingRiskRadarCalendarDayRead[]>([]);
const eventContext = ref<TradingRiskRadarEventContextRead | null>(null);
const selectedEventKey = ref("");

const filters = reactive({
  importRunId: undefined as number | undefined,
  stockCode: "",
  startDate: "",
  endDate: "",
  kInput: "1",
  kthMethod: "persistent_segment_tree" as "persistent_segment_tree" | "t_digest",
  jointTopNInput: "20",
  severity: "",
  topNInput: "50",
});

const kthMethodOptions = [
  { label: "精确结果", value: "persistent_segment_tree" as const },
  { label: "近似结果", value: "t_digest" as const },
];

const severityOptions = [
  { label: "全部严重度", value: "" },
  { label: "medium", value: "medium" },
  { label: "high", value: "high" },
  { label: "critical", value: "critical" },
];

const importRunDisplayIdMap = computed(() => new Map(importRuns.value.map((item) => [item.id, item.display_id])));
const jointAnomalyRows = computed(() => jointAnomalies.value?.rows ?? []);
const contextPills = computed(() => [
  `当前批次：${formatImportRunDisplayLabel(filters.importRunId)}`,
  `当前股票：${filters.stockCode || "--"}`,
  `日期范围：${filters.startDate || "起始不限"} ~ ${filters.endDate || "结束不限"}`,
]);
const algoCards = computed(() => [
  {
    label: "当前范围记录数",
    value: String(algoSummary.value?.record_count ?? 0),
    hint: algoSummary.value ? `${algoSummary.value.start_date} ~ ${algoSummary.value.end_date}` : "等待区间分析范围",
    tone: "teal" as const,
  },
  {
    label: "区间最大成交额",
    value: algoResult.value ? formatCompact(algoResult.value.max_amount, 2) : "--",
    hint: algoResult.value ? `命中 ${algoResult.value.matches.length} 个交易日` : algoNotice.value || "等待区间算法结果",
    tone: "orange" as const,
  },
  {
    label: "区间第 K 大成交量",
    value: algoKthResult.value ? formatCompact(algoKthResult.value.value, 2) : "--",
    hint: algoKthResult.value ? `${algoKthResult.value.method} / K=${algoKthResult.value.k}` : algoKthNotice.value || "等待第 K 大查询",
    tone: "berry" as const,
  },
  {
    label: "联合异常条数",
    value: String(jointAnomalyRows.value.length),
    hint: jointAnomalyRows.value.length ? "按联合百分位排序" : jointNotice.value || "等待联合异常结果",
    tone: "neutral" as const,
  },
]);

const statusCards = computed(() => [
  {
    label: "索引状态",
    value: indexStatus.value?.status ?? "--",
    hint: indexStatus.value?.build_completed_at ? `完成于 ${formatDateTime(indexStatus.value.build_completed_at)}` : "等待选择批次",
    tone: "teal" as const,
  },
  {
    label: "异常事件数",
    value: String(overview.value?.total_events ?? 0),
    hint: `事件窗口 ${overview.value?.lookback_window ?? 20} 日`,
    tone: "orange" as const,
  },
  {
    label: "受影响股票数",
    value: String(overview.value?.impacted_stock_count ?? 0),
    hint: indexStatus.value?.stock_count ? `${indexStatus.value.stock_count} 个已建索引股票` : "等待索引完成",
    tone: "berry" as const,
  },
  {
    label: "Critical 事件",
    value: String(overview.value?.critical_count ?? 0),
    hint: overview.value ? `${overview.value.high_count} 个 high / ${overview.value.medium_count} 个 medium` : "等待雷达结果",
    tone: "neutral" as const,
  },
]);

const radarScatterOption = computed<EChartsOption | null>(() => {
  if (!events.value.length) {
    return null;
  }

  const severityGroups = {
    medium: events.value.filter((item) => item.severity === "medium"),
    high: events.value.filter((item) => item.severity === "high"),
    critical: events.value.filter((item) => item.severity === "critical"),
  };

  const buildSeries = (rows: TradingRiskRadarEventRead[], name: string, color: string) => ({
    type: "scatter" as const,
    name,
    itemStyle: { color },
    data: rows.map((item) => ({
      value: [
        toNumber(item.return_z20),
        toNumber(item.volume_ratio20),
        toNumber(item.amplitude_ratio20),
        item.stock_code,
        item.trade_date,
      ],
      symbolSize: 10 + Math.min(toNumber(item.amplitude_ratio20) * 6, 26),
    })),
  });

  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(24, 50, 47, 0.9)",
      borderWidth: 0,
      textStyle: { color: "#fffdf7" },
      formatter: (params) => {
        const point = Array.isArray((params as { value?: unknown }).value)
          ? ((params as { value: Array<string | number> }).value ?? [])
          : [];
        const [returnZ, volumeRatio, amplitudeRatio, stockCode, tradeDate] = point;
        return [
          `${stockCode} · ${tradeDate}`,
          `Return Z20: ${Number(returnZ).toFixed(2)}`,
          `Volume Ratio20: ${Number(volumeRatio).toFixed(2)}`,
          `Amplitude Ratio20: ${Number(amplitudeRatio).toFixed(2)}`,
        ].join("<br/>");
      },
    },
    legend: {
      top: 0,
      textStyle: { color: "#59676b" },
    },
    grid: {
      left: 72,
      right: 40,
      top: 56,
      bottom: 68,
      containLabel: true,
    },
    xAxis: {
      type: "value",
      name: "Return Z20",
      nameLocation: "middle",
      nameGap: 36,
      axisLabel: { color: "#59676b" },
      splitLine: {
        lineStyle: { color: "rgba(89, 103, 107, 0.10)" },
      },
    },
    yAxis: {
      type: "value",
      name: "Volume Ratio20",
      nameLocation: "middle",
      nameGap: 56,
      axisLabel: { color: "#59676b" },
      splitLine: {
        lineStyle: { color: "rgba(89, 103, 107, 0.10)" },
      },
    },
    series: [
      buildSeries(severityGroups.medium, "medium", "#f2b233"),
      buildSeries(severityGroups.high, "high", "#f28c28"),
      buildSeries(severityGroups.critical, "critical", "#b9524f"),
    ],
  };
});

const calendarChartOption = computed<EChartsOption | null>(() => {
  if (!calendarRows.value.length) {
    return null;
  }

  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(24, 50, 47, 0.9)",
      borderWidth: 0,
      textStyle: { color: "#fffdf7" },
    },
    legend: {
      top: 0,
      textStyle: { color: "#59676b" },
    },
    grid: {
      left: 60,
      right: 52,
      top: 56,
      bottom: 72,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: calendarRows.value.map((item) => item.trade_date),
      axisLabel: { color: "#59676b", rotate: 35, margin: 14, hideOverlap: false },
    },
    yAxis: [
      {
        type: "value",
        name: "事件数",
        axisLabel: { color: "#59676b" },
        splitLine: {
          lineStyle: { color: "rgba(89, 103, 107, 0.10)" },
        },
      },
      {
        type: "value",
        name: "最大百分位",
        axisLabel: { color: "#59676b" },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        type: "bar",
        name: "事件数",
        barMaxWidth: 18,
        itemStyle: {
          color: "#0b8f8c",
          borderRadius: [6, 6, 0, 0],
        },
        data: calendarRows.value.map((item) => item.event_count),
      },
      {
        type: "line",
        name: "最大百分位",
        yAxisIndex: 1,
        smooth: true,
        showSymbol: false,
        lineStyle: {
          width: 3,
          color: "#b9524f",
        },
        data: calendarRows.value.map((item) => toNumber(item.max_joint_percentile)),
      },
    ],
  };
});

function applySharedScope() {
  datasetContext.applyScope({
    importRunId: filters.importRunId,
    stockCode: filters.stockCode,
    startDate: filters.startDate,
    endDate: filters.endDate,
  });
}

function formatImportRunDisplayLabel(runId: number | null | undefined) {
  if (!runId) {
    return "--";
  }

  const displayId = importRunDisplayIdMap.value.get(runId);
  return `#${displayId ?? runId}`;
}

function parseKInput() {
  const normalized = filters.kInput.trim();
  if (!normalized) {
    throw new Error("K 值必须是正整数。");
  }

  const parsed = Number(normalized);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error("K 值必须是正整数。");
  }
  return parsed;
}

function parseJointTopN() {
  const normalized = filters.jointTopNInput.trim();
  if (!normalized) {
    return undefined;
  }

  const parsed = Number(normalized);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error("联合异常 Top N 必须是正整数，留空则返回全部结果。");
  }
  return parsed;
}

function parseTopN() {
  const normalized = filters.topNInput.trim();
  if (!normalized) {
    return undefined;
  }
  const parsed = Number(normalized);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error("Top N 必须是正整数，留空则表示不限制。");
  }
  return parsed;
}

function clearAlgoData() {
  algoSummary.value = null;
  algoResult.value = null;
  algoKthResult.value = null;
  jointAnomalies.value = null;
  algoNotice.value = "";
  algoKthNotice.value = "";
  jointNotice.value = "";
}

function clearRadarData() {
  overview.value = null;
  events.value = [];
  stockProfiles.value = [];
  calendarRows.value = [];
  eventContext.value = null;
  selectedEventKey.value = "";
}

async function loadRuns(preferredRunId?: number) {
  loadingRuns.value = true;
  error.value = "";
  try {
    const rows = await fetchImportRuns({ limit: 50 });
    importRuns.value = rows;
    if (!rows.length) {
      filters.importRunId = undefined;
      filters.stockCode = "";
      stocks.value = [];
      indexStatus.value = null;
      clearAlgoData();
      clearRadarData();
      datasetContext.resetScope();
      return;
    }

    const nextRunId =
      preferredRunId && rows.some((item) => item.id === preferredRunId)
        ? preferredRunId
        : filters.importRunId && rows.some((item) => item.id === filters.importRunId)
          ? filters.importRunId
          : rows[0].id;
    filters.importRunId = nextRunId;
    await loadStocks(false);
    applySharedScope();
    await Promise.all([loadAlgoPanels(), loadRadar()]);
    runtime.markSynced();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loadingRuns.value = false;
  }
}

async function loadStocks(updateSharedScope = true) {
  if (!filters.importRunId) {
    stocks.value = [];
    filters.stockCode = "";
    clearAlgoData();
    if (updateSharedScope) {
      applySharedScope();
    }
    return;
  }

  try {
    const rows = await fetchTradingStocks(filters.importRunId);
    stocks.value = rows;

    if (!rows.length) {
      filters.stockCode = "";
      clearAlgoData();
      if (updateSharedScope) {
        applySharedScope();
      }
      return;
    }

    if (!rows.some((item) => item.stock_code === filters.stockCode)) {
      filters.stockCode = rows[0].stock_code;
    }

    if (updateSharedScope) {
      applySharedScope();
    }
  } catch (err) {
    error.value = getErrorMessage(err);
  }
}

async function loadAlgoPanels() {
  if (!filters.importRunId || !filters.stockCode) {
    clearAlgoData();
    return;
  }

  loadingAlgo.value = true;
  error.value = "";
  clearAlgoData();

  try {
    const summaryPayload = await fetchTradingSummary({
      import_run_id: filters.importRunId,
      stock_code: filters.stockCode,
      start_date: filters.startDate || undefined,
      end_date: filters.endDate || undefined,
    });
    algoSummary.value = summaryPayload;

    const startDate = filters.startDate || summaryPayload.start_date;
    const endDate = filters.endDate || summaryPayload.end_date;
    const k = parseKInput();
    const jointTopN = parseJointTopN();

    const [maxResult, kthResult, jointResult] = await Promise.allSettled([
      fetchTradingRangeMaxAmount({
        import_run_id: filters.importRunId,
        stock_code: filters.stockCode,
        start_date: startDate,
        end_date: endDate,
      }),
      fetchTradingRangeKthVolume({
        import_run_id: filters.importRunId,
        stock_code: filters.stockCode,
        start_date: startDate,
        end_date: endDate,
        k,
        method: filters.kthMethod,
      }),
      fetchTradingJointAnomalyRanking({
        import_run_id: filters.importRunId,
        start_date: filters.startDate || undefined,
        end_date: filters.endDate || undefined,
        top_n: jointTopN,
      }),
    ]);

    if (maxResult.status === "fulfilled") {
      algoResult.value = maxResult.value;
    } else {
      algoNotice.value = getErrorMessage(maxResult.reason);
    }

    if (kthResult.status === "fulfilled") {
      algoKthResult.value = kthResult.value;
    } else {
      algoKthNotice.value = getErrorMessage(kthResult.reason);
    }

    if (jointResult.status === "fulfilled") {
      jointAnomalies.value = jointResult.value;
    } else {
      jointNotice.value = getErrorMessage(jointResult.reason);
    }

    applySharedScope();
    runtime.markSynced();
  } catch (err) {
    error.value = getErrorMessage(err);
    clearAlgoData();
  } finally {
    loadingAlgo.value = false;
  }
}

async function loadRadar() {
  if (!filters.importRunId) {
    indexStatus.value = null;
    clearRadarData();
    return;
  }

  loadingRadar.value = true;
  error.value = "";
  try {
    indexStatus.value = await fetchAlgoIndexStatus({ import_run_id: filters.importRunId });
    if (!indexStatus.value.is_ready) {
      clearRadarData();
      return;
    }

    const topN = parseTopN();
    const [overviewPayload, eventPayload, stockPayload, calendarPayload] = await Promise.all([
      fetchRiskRadarOverview({ import_run_id: filters.importRunId }),
      fetchRiskRadarEvents({
        import_run_id: filters.importRunId,
        start_date: filters.startDate || undefined,
        end_date: filters.endDate || undefined,
        severity: filters.severity || undefined,
        top_n: topN,
      }),
      fetchRiskRadarStocks({
        import_run_id: filters.importRunId,
        severity: filters.severity || undefined,
        top_n: 20,
      }),
      fetchRiskRadarCalendar({
        import_run_id: filters.importRunId,
        start_date: filters.startDate || undefined,
        end_date: filters.endDate || undefined,
      }),
    ]);

    overview.value = overviewPayload;
    events.value = eventPayload.rows;
    stockProfiles.value = stockPayload.rows;
    calendarRows.value = calendarPayload.rows;

    if (events.value.length) {
      await loadEventContext(events.value[0]);
    } else {
      eventContext.value = null;
      selectedEventKey.value = "";
    }
    runtime.markSynced();
  } catch (err) {
    clearRadarData();
    error.value = getErrorMessage(err);
  } finally {
    loadingRadar.value = false;
  }
}

async function loadEventContext(event: TradingRiskRadarEventRead) {
  if (!filters.importRunId) {
    return;
  }

  try {
    eventContext.value = await fetchRiskRadarEventContext({
      import_run_id: filters.importRunId,
      stock_code: event.stock_code,
      trade_date: event.trade_date,
    });
    selectedEventKey.value = `${event.stock_code}:${event.trade_date}`;
  } catch (err) {
    error.value = getErrorMessage(err);
  }
}

function radarEventRowClassName(payload: { row: TradingRiskRadarEventRead }) {
  return selectedEventKey.value === `${payload.row.stock_code}:${payload.row.trade_date}` ? "is-current" : "";
}

async function applyAlgoScope() {
  applySharedScope();
  await Promise.all([loadAlgoPanels(), loadRadar()]);
}

async function handleRunChange() {
  await loadStocks(true);
  await Promise.all([loadAlgoPanels(), loadRadar()]);
}

async function handleStockChange() {
  applySharedScope();
  await loadAlgoPanels();
}

async function handleRebuild() {
  if (!filters.importRunId) {
    return;
  }

  rebuilding.value = true;
  error.value = "";
  try {
    indexStatus.value = await rebuildAlgoIndex(filters.importRunId);
    await loadRadar();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    rebuilding.value = false;
  }
}

onMounted(() => {
  filters.importRunId = datasetContext.state.importRunId;
  filters.stockCode = datasetContext.state.stockCode;
  filters.startDate = datasetContext.state.startDate;
  filters.endDate = datasetContext.state.endDate;
  void loadRuns(filters.importRunId);
});
</script>

<template>
  <div class="page">
    <section class="page__header">
      <div>
        <div class="page__eyebrow">Algo Radar / 算法雷达</div>
        <h2 class="page__title">区间算法、联合异常与风险雷达统一收拢到同一页</h2>
        <p class="page__subtitle">
          这里承接所有算法增强能力：既能对当前股票执行区间查询，也能查看跨股票联合异常排名和三维风险雷达结果。
        </p>
      </div>
      <div class="page__actions">
        <el-button :loading="loadingRuns || loadingAlgo || loadingRadar" @click="loadRuns(filters.importRunId)">刷新算法页</el-button>
        <el-button v-if="auth.isAdmin.value" type="primary" plain :loading="rebuilding" @click="handleRebuild">重建索引</el-button>
      </div>
    </section>

    <el-alert
      v-if="error"
      title="算法雷达加载失败"
      type="error"
      :description="error"
      show-icon
      :closable="false"
    />

    <PanelCard title="共享数据集上下文" description="当前上下文继承自 Overview，也可以在本页继续微调。">
      <div class="radar-tags">
        <span v-for="item in contextPills" :key="item" class="pill">{{ item }}</span>
      </div>
    </PanelCard>

    <PanelCard title="算法筛选器" description="区间算法、联合异常和风险雷达共享同一批次与日期范围。">
      <el-form class="radar-filters" label-position="top">
        <el-form-item label="导入批次">
          <el-select v-model="filters.importRunId" placeholder="选择批次" class="radar-filters__control" @change="handleRunChange">
            <el-option
              v-for="item in importRuns"
              :key="item.id"
              :label="`#${item.display_id} · ${item.dataset_name}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="当前股票">
          <el-select v-model="filters.stockCode" placeholder="选择股票" class="radar-filters__control" filterable @change="handleStockChange">
            <el-option
              v-for="item in stocks"
              :key="item.stock_code"
              :label="`${item.stock_code}${item.stock_name ? ` · ${item.stock_name}` : ''}`"
              :value="item.stock_code"
            />
          </el-select>
        </el-form-item>
        <div class="date-range-group">
          <el-form-item label="开始日期">
            <el-date-picker v-model="filters.startDate" type="date" value-format="YYYY-MM-DD" class="radar-filters__control" />
          </el-form-item>
          <el-form-item label="结束日期">
            <el-date-picker v-model="filters.endDate" type="date" value-format="YYYY-MM-DD" class="radar-filters__control" />
          </el-form-item>
        </div>
        <el-form-item label="K 值">
          <el-input v-model="filters.kInput" placeholder="正整数，例如 1" class="radar-filters__control" />
        </el-form-item>
        <el-form-item label="第 K 大算法方式">
          <el-select v-model="filters.kthMethod" class="radar-filters__control">
            <el-option v-for="item in kthMethodOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="联合异常 Top N">
          <el-input v-model="filters.jointTopNInput" placeholder="默认 20" class="radar-filters__control" />
        </el-form-item>
        <el-form-item label="严重度">
          <el-select v-model="filters.severity" class="radar-filters__control">
            <el-option v-for="item in severityOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="Top N">
          <el-input v-model="filters.topNInput" placeholder="默认 50" class="radar-filters__control" />
        </el-form-item>
      </el-form>
      <div class="radar-filters__actions">
        <el-button type="primary" :loading="loadingAlgo || loadingRadar" @click="applyAlgoScope">应用算法上下文</el-button>
      </div>
    </PanelCard>

    <section class="page__grid page__grid--stats">
      <StatCard
        v-for="item in algoCards"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :tone="item.tone"
      />
    </section>

    <section class="page__grid page__grid--double">
      <PanelCard title="区间最大成交额" description="来自系统算法接口 `/api/algo/trading/range-max-amount`。">
        <div v-if="algoResult" class="algo-result">
          <div class="algo-result__hero">
            <div class="algo-result__value">{{ formatNumberish(algoResult.max_amount, 4) }}</div>
            <div class="algo-result__meta">
              <span>批次 {{ formatImportRunDisplayLabel(algoResult.import_run_id) }}</span>
              <span>{{ algoResult.stock_code }}</span>
              <span>{{ algoResult.start_date }} ~ {{ algoResult.end_date }}</span>
            </div>
          </div>

          <div class="algo-result__matches">
            <div v-for="match in algoResult.matches" :key="`${match.trade_date}-${match.series_index}`" class="algo-result__match">
              <span class="mono">idx {{ match.series_index }}</span>
              <strong>{{ match.trade_date }}</strong>
            </div>
          </div>
        </div>

        <EmptyState
          v-else
          :title="algoNotice ? (isDataInsufficientMessage(algoNotice) ? '数据不足分析' : '算法结果提示') : '等待算法结果'"
          :description="algoNotice || '选择当前批次和股票后，这里会展示区间最大成交额和命中的交易日。'"
        />
      </PanelCard>

      <PanelCard title="区间第 K 大成交量" description="来自系统算法接口 `/api/algo/trading/range-kth-volume`。">
        <div v-if="algoKthResult" class="algo-result">
          <div class="algo-result__hero algo-result__hero--teal">
            <div class="algo-result__value">{{ formatNumberish(algoKthResult.value, 4) }}</div>
            <div class="algo-result__meta">
              <span>批次 {{ formatImportRunDisplayLabel(algoKthResult.import_run_id) }}</span>
              <span>{{ algoKthResult.stock_code }}</span>
              <span>K = {{ algoKthResult.k }}</span>
              <span>{{ algoKthResult.start_date }} ~ {{ algoKthResult.end_date }}</span>
            </div>
          </div>

          <div class="radar-tags">
            <span class="pill">{{ algoKthResult.is_approx ? "近似结果" : "精确结果" }}</span>
            <span class="pill">method: {{ algoKthResult.method }}</span>
          </div>

          <div v-if="algoKthResult.approximation_note" class="algo-result__note">
            {{ algoKthResult.approximation_note }}
          </div>

          <div v-if="algoKthResult.matches.length" class="algo-result__matches">
            <div
              v-for="match in algoKthResult.matches"
              :key="`kth-${match.trade_date}-${match.series_index}`"
              class="algo-result__match"
            >
              <span class="mono">idx {{ match.series_index }}</span>
              <strong>{{ match.trade_date }}</strong>
            </div>
          </div>
        </div>

        <EmptyState
          v-else
          :title="algoKthNotice ? (isDataInsufficientMessage(algoKthNotice) ? '数据不足分析' : '算法结果提示') : '等待算法结果'"
          :description="algoKthNotice || '输入 K 值并选择算法方式后，这里会展示区间第 K 大成交量。'"
        />
      </PanelCard>
    </section>

    <PanelCard title="联合异常排序" description="基于历史 CDQ 支配计数，对跨股票的收益冲击和成交量放大事件进行联合排序。">
      <el-table v-if="jointAnomalyRows.length" :data="jointAnomalyRows" stripe class="data-table" max-height="420">
        <el-table-column prop="trade_date" label="Trade Date" width="120" />
        <el-table-column prop="stock_code" label="Code" min-width="120" />
        <el-table-column prop="stock_name" label="Name" min-width="180" />
        <el-table-column label="Severity" width="110">
          <template #default="{ row }">
            <el-tag :type="toStatusTagType(row.severity)" effect="plain">{{ row.severity }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Daily Return" min-width="120">
          <template #default="{ row }">
            {{ formatPercent(row.daily_return, 2) }}
          </template>
        </el-table-column>
        <el-table-column label="Return Z20" min-width="120">
          <template #default="{ row }">
            {{ formatNumberish(row.return_z20, 2) }}
          </template>
        </el-table-column>
        <el-table-column label="Volume Ratio20" min-width="130">
          <template #default="{ row }">
            {{ formatNumberish(row.volume_ratio20, 2) }}
          </template>
        </el-table-column>
        <el-table-column label="Joint Percentile" min-width="140">
          <template #default="{ row }">
            {{ formatPercent(row.joint_percentile, 2) }}
          </template>
        </el-table-column>
        <el-table-column label="Dominated / History" min-width="150">
          <template #default="{ row }">
            {{ row.historical_dominated_count }} / {{ row.historical_sample_count }}
          </template>
        </el-table-column>
      </el-table>
      <EmptyState
        v-else
        :title="jointNotice ? (isDataInsufficientMessage(jointNotice) ? '数据不足分析' : '算法结果提示') : '等待联合异常排序'"
        :description="jointNotice || '这里会展示跨股票的联合异常排序结果。'"
      />
    </PanelCard>

    <section class="page__grid page__grid--stats">
      <StatCard
        v-for="item in statusCards"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :tone="item.tone"
      />
    </section>

    <PanelCard
      :title="auth.isAdmin.value ? '索引状态' : '索引可用状态'"
      :description="auth.isAdmin.value ? '管理员可查看完整索引构建状态与错误详情。' : '普通用户仅查看当前索引是否可用。'"
    >
      <el-descriptions v-if="indexStatus && auth.isAdmin.value" :column="2" border>
        <el-descriptions-item label="状态">
          <el-tag :type="toStatusTagType(indexStatus.status)" effect="plain">{{ indexStatus.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="复用次数">
          {{ indexStatus.reuse_count }}
        </el-descriptions-item>
        <el-descriptions-item label="开始时间">
          {{ formatDateTime(indexStatus.build_started_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="完成时间">
          {{ formatDateTime(indexStatus.build_completed_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="构建耗时">
          {{ indexStatus.build_duration_ms === null ? "--" : `${indexStatus.build_duration_ms} ms` }}
        </el-descriptions-item>
        <el-descriptions-item label="事件数量">
          {{ indexStatus.event_count ?? "--" }}
        </el-descriptions-item>
      </el-descriptions>
      <el-alert
        v-else-if="indexStatus"
        :title="indexStatus.is_ready ? '风险雷达已可用' : '风险雷达尚未就绪'"
        :type="indexStatus.is_ready ? 'success' : 'info'"
        :closable="false"
        :description="indexStatus.is_ready ? '当前数据集可以正常查看风险雷达结果。' : `当前索引状态为 ${indexStatus.status}，请稍后刷新。`"
      />
      <el-alert
        v-if="auth.isAdmin.value && indexStatus?.last_error"
        title="最近一次构建失败"
        type="error"
        :closable="false"
        :description="indexStatus.last_error"
      />
      <EmptyState
        v-if="!indexStatus"
        title="等待选择批次"
        description="先选择一个导入批次，然后这里会展示索引构建状态。"
      />
    </PanelCard>

    <template v-if="indexStatus?.is_ready">
      <section class="page__grid page__grid--double">
        <PanelCard title="异常分布散点" description="横轴为价格冲击，纵轴为成交量放大，点大小映射振幅异常。">
          <EChartPanel v-if="radarScatterOption" :option="radarScatterOption" :loading="loadingRadar" height="380px" />
          <EmptyState v-else title="暂无异常事件" description="当前筛选范围内还没有满足阈值的雷达事件。" />
        </PanelCard>

        <PanelCard title="系统性冲击时间带" description="按日期聚合异常事件数，并叠加当日最大联合百分位。">
          <EChartPanel v-if="calendarChartOption" :option="calendarChartOption" :loading="loadingRadar" height="380px" />
          <EmptyState v-else title="暂无日期聚合结果" description="索引 ready 后，这里会显示按日期汇总的异常分布。" />
        </PanelCard>
      </section>

      <section class="page__grid page__grid--double">
        <PanelCard title="批次总览" description="优先展示最异常的股票和最密集的异常日期。">
          <div v-if="overview" class="radar-stack">
            <div>
              <div class="radar-subtitle">最异常股票</div>
              <div class="radar-tags">
                <span v-for="item in overview.top_stocks" :key="`top-inst-${item.stock_code}`" class="pill">
                  {{ item.stock_code }} · {{ item.event_count }} 次
                </span>
              </div>
            </div>
            <div>
              <div class="radar-subtitle">最密集日期</div>
              <div class="radar-tags">
                <span v-for="item in overview.busiest_dates" :key="`busy-day-${item.trade_date}`" class="pill">
                  {{ item.trade_date }} · {{ item.event_count }} 条
                </span>
              </div>
            </div>
          </div>
          <EmptyState v-else title="暂无批次总览" description="索引 ready 后，这里会展示该批次的整体风险画像。" />
        </PanelCard>

        <PanelCard title="事件钻取" description="点击异常榜单中的某一行后，这里会解释该事件在不同窗口中的位置。">
          <div v-if="eventContext" class="radar-stack">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="股票">{{ eventContext.event.stock_code }}</el-descriptions-item>
              <el-descriptions-item label="日期">{{ eventContext.event.trade_date }}</el-descriptions-item>
              <el-descriptions-item label="严重度">
                <el-tag :type="toStatusTagType(eventContext.event.severity)" effect="plain">{{ eventContext.event.severity }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="主因">{{ eventContext.event.cause_label }}</el-descriptions-item>
            </el-descriptions>

            <div>
              <div class="radar-subtitle">成交量窗口分位</div>
              <el-table :data="eventContext.volume_windows" stripe class="data-table" max-height="420">
                <el-table-column prop="window_days" label="窗口天数" width="100" />
                <el-table-column label="当前值" min-width="110">
                  <template #default="{ row }">{{ formatCompact(row.current_value, 2) }}</template>
                </el-table-column>
                <el-table-column label="精确百分位" min-width="120">
                  <template #default="{ row }">{{ formatPercent(row.exact_percentile, 2) }}</template>
                </el-table-column>
                <el-table-column label="P50 / P90 / P95" min-width="220">
                  <template #default="{ row }">
                    {{ formatCompact(row.p50, 2) }} / {{ formatCompact(row.p90, 2) }} / {{ formatCompact(row.p95, 2) }}
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <div>
              <div class="radar-subtitle">振幅窗口分位</div>
              <el-table :data="eventContext.amplitude_windows" stripe class="data-table" max-height="420">
                <el-table-column prop="window_days" label="窗口天数" width="100" />
                <el-table-column label="当前值" min-width="110">
                  <template #default="{ row }">{{ formatNumberish(row.current_value, 4) }}</template>
                </el-table-column>
                <el-table-column label="精确百分位" min-width="120">
                  <template #default="{ row }">{{ formatPercent(row.exact_percentile, 2) }}</template>
                </el-table-column>
                <el-table-column label="P50 / P90 / P95" min-width="220">
                  <template #default="{ row }">
                    {{ formatNumberish(row.p50, 4) }} / {{ formatNumberish(row.p90, 4) }} / {{ formatNumberish(row.p95, 4) }}
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <div>
              <div class="radar-subtitle">前后窗口分布变化</div>
              <el-table :data="eventContext.distribution_changes" stripe class="data-table" max-height="420">
                <el-table-column prop="metric" label="指标" width="120" />
                <el-table-column label="Before" min-width="220">
                  <template #default="{ row }">
                    {{ formatNumberish(row.before_median, 4) }} / {{ formatNumberish(row.before_p90, 4) }} / {{ formatNumberish(row.before_p95, 4) }}
                  </template>
                </el-table-column>
                <el-table-column label="After" min-width="220">
                  <template #default="{ row }">
                    {{ formatNumberish(row.after_median, 4) }} / {{ formatNumberish(row.after_p90, 4) }} / {{ formatNumberish(row.after_p95, 4) }}
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <div v-if="eventContext.local_amount_peak">
              <div class="radar-subtitle">事件附近成交额峰值</div>
              <el-alert
                type="info"
                :closable="false"
                :title="`峰值成交额 ${formatCompact(eventContext.local_amount_peak.peak_amount, 2)}`"
                :description="`${eventContext.local_amount_peak.start_date} ~ ${eventContext.local_amount_peak.end_date}`"
              />
              <div class="radar-tags">
                <span v-for="item in eventContext.local_amount_peak.peak_dates" :key="`peak-date-${item.trade_date}`" class="pill">
                  {{ item.trade_date }}
                </span>
              </div>
            </div>
          </div>
          <EmptyState
            v-else
            title="等待选择异常事件"
            description="点击左侧异常榜单中的某一行后，这里会展示窗口分位、分布变化和成交额峰值解释。"
          />
        </PanelCard>
      </section>

      <section class="page__grid page__grid--double">
        <PanelCard title="异常事件榜单" description="按联合百分位倒序排列，点击某一行可查看事件上下文。">
          <el-table
            v-if="events.length"
            :data="events"
            stripe
            class="data-table"
            max-height="420"
            highlight-current-row
            :row-class-name="radarEventRowClassName"
            @row-click="loadEventContext"
          >
            <el-table-column prop="trade_date" label="Date" width="120" />
            <el-table-column prop="stock_code" label="Code" min-width="120" />
            <el-table-column prop="cause_label" label="Cause" min-width="160" />
            <el-table-column label="Severity" width="110">
              <template #default="{ row }">
                <el-tag :type="toStatusTagType(row.severity)" effect="plain">{{ row.severity }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Joint Percentile" min-width="130">
              <template #default="{ row }">{{ formatPercent(row.joint_percentile, 2) }}</template>
            </el-table-column>
            <el-table-column label="Return Z20" min-width="110">
              <template #default="{ row }">{{ formatNumberish(row.return_z20, 2) }}</template>
            </el-table-column>
            <el-table-column label="Volume Ratio20" min-width="130">
              <template #default="{ row }">{{ formatNumberish(row.volume_ratio20, 2) }}</template>
            </el-table-column>
            <el-table-column label="Amplitude Ratio20" min-width="140">
              <template #default="{ row }">{{ formatNumberish(row.amplitude_ratio20, 2) }}</template>
            </el-table-column>
          </el-table>
          <EmptyState v-else title="暂无异常榜单" description="调整日期或严重度后，如果仍无结果，说明当前范围内没有命中事件。" />
        </PanelCard>

        <PanelCard title="股票风险画像" description="用于识别哪几只股票在当前批次中最容易反复触发异常。">
          <el-table v-if="stockProfiles.length" :data="stockProfiles" stripe class="data-table" max-height="420">
            <el-table-column prop="stock_code" label="Code" min-width="120" />
            <el-table-column prop="event_count" label="事件数" width="90" />
            <el-table-column label="最高百分位" min-width="120">
              <template #default="{ row }">{{ formatPercent(row.max_joint_percentile, 2) }}</template>
            </el-table-column>
            <el-table-column label="平均百分位" min-width="120">
              <template #default="{ row }">{{ formatPercent(row.avg_joint_percentile, 2) }}</template>
            </el-table-column>
            <el-table-column prop="latest_event_date" label="最近异常" min-width="120" />
            <el-table-column prop="top_event_severity" label="最高级别" min-width="110" />
          </el-table>
          <EmptyState v-else title="暂无股票画像" description="风险雷达构建完成后，这里会按股票聚合异常频次和严重度。" />
        </PanelCard>
      </section>

      <PanelCard title="日期聚合表" description="识别市场级冲击日，看某一天有多少只股票一起异常。">
        <el-table v-if="calendarRows.length" :data="calendarRows" stripe class="data-table" max-height="420">
          <el-table-column prop="trade_date" label="Date" min-width="120" />
          <el-table-column prop="event_count" label="事件数" width="100" />
          <el-table-column prop="impacted_stock_count" label="股票数" width="100" />
          <el-table-column prop="critical_count" label="Critical" width="100" />
          <el-table-column prop="high_count" label="High" width="90" />
          <el-table-column prop="medium_count" label="Medium" width="100" />
          <el-table-column label="最大百分位" min-width="120">
            <template #default="{ row }">{{ formatPercent(row.max_joint_percentile, 2) }}</template>
          </el-table-column>
        </el-table>
        <EmptyState v-else title="暂无日期聚合结果" description="索引 ready 后，这里会展示系统性冲击日的聚合结果。" />
      </PanelCard>
    </template>

    <EmptyState
      v-else-if="filters.importRunId"
      title="索引尚未就绪"
      :description="indexStatus?.last_error || `当前索引状态为 ${indexStatus?.status ?? 'pending'}，可以稍后刷新，或手动点击“重建索引”。`"
    />
  </div>
</template>

<style scoped>
.radar-filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
}

.radar-filters :deep(.el-form-item) {
  margin-bottom: 0;
}

.radar-filters__control {
  width: 100%;
}

.radar-filters__actions {
  margin-top: 14px;
}

.date-range-group {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 10px;
  grid-column: 1 / -1;
}

.radar-stack {
  display: grid;
  gap: 18px;
}

.radar-subtitle {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.radar-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.algo-result {
  display: grid;
  gap: 18px;
}

.algo-result__hero {
  display: grid;
  gap: 12px;
  min-width: 0;
  padding: 20px;
  border-radius: 22px;
  background: linear-gradient(135deg, rgba(185, 82, 79, 0.12), rgba(242, 140, 40, 0.12));
}

.algo-result__hero--teal {
  background: linear-gradient(135deg, rgba(11, 143, 140, 0.14), rgba(216, 176, 115, 0.18));
}

.algo-result__value {
  max-width: 100%;
  font-size: clamp(24px, 4.2vw, 48px);
  font-weight: 700;
  line-height: 1.08;
  letter-spacing: -0.03em;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.algo-result__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: var(--text-secondary);
}

.algo-result__note {
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid rgba(11, 143, 140, 0.16);
  background: rgba(11, 143, 140, 0.08);
  color: #275c5b;
  line-height: 1.5;
}

.algo-result__matches {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  max-height: 240px;
  overflow: auto;
  padding-right: 4px;
}

.algo-result__match {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 132px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(185, 82, 79, 0.16);
  background: rgba(255, 255, 255, 0.72);
}

@media (max-width: 768px) {
  .date-range-group {
    grid-template-columns: 1fr;
  }
}
</style>




