<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import type { EChartsOption } from "echarts";

import {
  fetchTradingAnomalies,
  fetchTradingCorrelation,
  fetchTradingCrossSection,
  fetchTradingIndicators,
  fetchTradingJointAnomalyRanking,
  fetchTradingQuality,
  fetchTradingRisk,
  fetchTradingScopeComparison,
  fetchTradingSummary,
} from "@/api/analysis";
import { fetchImportRuns } from "@/api/imports";
import { fetchTradingInstruments } from "@/api/trading";
import type {
  ImportRunRead,
  TradingAnomalyReportRead,
  TradingComparisonScopeRead,
  TradingCorrelationMatrixRead,
  TradingCrossSectionRead,
  TradingIndicatorPointRead,
  TradingIndicatorSeriesRead,
  TradingInstrumentRead,
  TradingJointAnomalyRankingRead,
  TradingQualityReportRead,
  TradingRiskMetricsRead,
  TradingScopeComparisonRead,
  TradingSummaryRead,
} from "@/api/types";
import EChartPanel from "@/components/EChartPanel.vue";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import StatCard from "@/components/StatCard.vue";
import { useRuntimeStore } from "@/stores/runtime";
import {
  formatCompact,
  formatDate,
  formatNumberish,
  formatPercent,
  getErrorMessage,
  isDataInsufficientMessage,
  toNumber,
  toStatusTagType,
} from "@/utils/format";


interface PanelState {
  loading: boolean;
  notice: string;
}

interface AnalysisFilters {
  importRunId: number | undefined;
  instrumentCode: string;
  startDate: string;
  endDate: string;
  crossMetric: string;
  topNInput: string;
  compareRunId: number | undefined;
  compareInstrumentCode: string;
  compareStartDate: string;
  compareEndDate: string;
  correlationInstrumentCodes: string[];
}

function createPanelState(): PanelState {
  return {
    loading: false,
    notice: "",
  };
}

function createDefaultFilters(): AnalysisFilters {
  return {
    importRunId: undefined,
    instrumentCode: "",
    startDate: "",
    endDate: "",
    crossMetric: "total_return",
    topNInput: "10",
    compareRunId: undefined,
    compareInstrumentCode: "",
    compareStartDate: "",
    compareEndDate: "",
    correlationInstrumentCodes: [],
  };
}

const runtime = useRuntimeStore();
const loadingRuns = ref(false);
const loadingAnalysis = ref(false);
const error = ref("");
const importRuns = ref<ImportRunRead[]>([]);
const instruments = ref<TradingInstrumentRead[]>([]);
const compareInstruments = ref<TradingInstrumentRead[]>([]);

const summary = ref<TradingSummaryRead | null>(null);
const quality = ref<TradingQualityReportRead | null>(null);
const indicators = ref<TradingIndicatorSeriesRead | null>(null);
const risk = ref<TradingRiskMetricsRead | null>(null);
const anomalies = ref<TradingAnomalyReportRead | null>(null);
const jointAnomalies = ref<TradingJointAnomalyRankingRead | null>(null);
const crossSection = ref<TradingCrossSectionRead | null>(null);
const correlation = ref<TradingCorrelationMatrixRead | null>(null);
const comparison = ref<TradingScopeComparisonRead | null>(null);
const appliedFilters = ref<AnalysisFilters | null>(null);
const draftForm = reactive(createDefaultFilters());
const importRunDisplayIdMap = computed(() => new Map(importRuns.value.map((item) => [item.id, item.display_id])));

const panelStates = reactive({
  summary: createPanelState(),
  quality: createPanelState(),
  indicators: createPanelState(),
  risk: createPanelState(),
  anomalies: createPanelState(),
  crossSection: createPanelState(),
  correlation: createPanelState(),
  comparison: createPanelState(),
  jointAnomalies: createPanelState(),
});

const compareRunOptions = computed(() => importRuns.value);
const correlationHint = "仅从当前批次中选取，基于重叠日期收益率计算，不是跨批次公共标的。";
const comparisonHint = "支持与当前相同批次做基线校验；对比标的留空时表示对比范围内全部标的。";

const crossMetricOptions = [
  { label: "区间收益率", value: "total_return" },
  { label: "波动率", value: "volatility" },
  { label: "成交量", value: "total_volume" },
  { label: "成交额", value: "total_amount" },
  { label: "平均振幅", value: "average_amplitude" },
];

const analysisCards = computed(() => [
  {
    label: "Latest Close",
    value: summary.value ? formatNumberish(summary.value.latest_close, 2) : "--",
    hint: summary.value ? `${formatDate(summary.value.end_date)} 收盘价` : panelHint(panelStates.summary, "等待分析结果"),
    tone: "teal" as const,
  },
  {
    label: "Interval Return",
    value: risk.value ? formatPercent(risk.value.interval_return, 2) : "--",
    hint: risk.value ? `${risk.value.record_count} 条记录` : panelHint(panelStates.risk, "等待分析结果"),
    tone: "orange" as const,
  },
  {
    label: "Max Drawdown",
    value: risk.value ? formatPercent(risk.value.max_drawdown, 2) : "--",
    hint: risk.value ? `持续 ${risk.value.max_drawdown_duration} 天` : panelHint(panelStates.risk, "等待分析结果"),
    tone: "berry" as const,
  },
  {
    label: "范围对比差异",
    value: comparison.value ? String(comparison.value.mismatch_summary.mismatched_record_count) : "--",
    hint: comparison.value
      ? `${comparison.value.record_overlap.shared_record_count} 条共同记录`
      : panelHint(panelStates.comparison, "等待范围对比"),
    tone: "neutral" as const,
  },
]);

const indicatorChartOption = computed<EChartsOption | null>(() => {
  if (!indicators.value?.points.length) {
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
      left: 48,
      right: 48,
      top: 56,
      bottom: 34,
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: indicators.value.points.map((item) => item.trade_date),
      axisLabel: { color: "#59676b" },
      axisLine: {
        lineStyle: { color: "rgba(89, 103, 107, 0.22)" },
      },
    },
    yAxis: [
      {
        type: "value",
        name: "Price",
        axisLabel: { color: "#59676b" },
        splitLine: {
          lineStyle: { color: "rgba(89, 103, 107, 0.10)" },
        },
      },
      {
        type: "value",
        name: "Volume",
        axisLabel: { color: "#59676b" },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        type: "line",
        name: "Close",
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 3, color: "#0b8f8c" },
        data: indicators.value.points.map((item) => toNumber(item.close)),
      },
      {
        type: "line",
        name: "MA5",
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: "#f28c28" },
        data: indicators.value.points.map((item) => toNumber(item.ma5)),
      },
      {
        type: "line",
        name: "MA20",
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: "#b9524f" },
        data: indicators.value.points.map((item) => toNumber(item.ma20)),
      },
      {
        type: "line",
        name: "Boll Upper",
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1.5, color: "#59676b", type: "dashed" },
        data: indicators.value.points.map((item) => toNumber(item.bollinger_upper)),
      },
      {
        type: "line",
        name: "Boll Lower",
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1.5, color: "#7c878a", type: "dashed" },
        data: indicators.value.points.map((item) => toNumber(item.bollinger_lower)),
      },
      {
        type: "bar",
        name: "Volume",
        yAxisIndex: 1,
        barMaxWidth: 14,
        itemStyle: {
          color: "rgba(11, 143, 140, 0.26)",
          borderRadius: [4, 4, 0, 0],
        },
        data: indicators.value.points.map((item) => toNumber(item.volume)),
      },
    ],
  };
});

const latestIndicatorPoint = computed<TradingIndicatorPointRead | null>(() => {
  const points = indicators.value?.points;
  return points?.length ? points[points.length - 1] : null;
});

const correlationTableRows = computed(() => {
  if (!correlation.value) {
    return [];
  }

  return correlation.value.instrument_codes.map((instrumentCode, rowIndex) => {
    const row: Record<string, string | number | null> = { instrument_code: instrumentCode };
    correlation.value?.instrument_codes.forEach((code, columnIndex) => {
      row[code] = correlation.value?.matrix[rowIndex]?.[columnIndex] ?? null;
    });
    return row;
  });
});

const comparisonMismatchRows = computed(() => {
  if (!comparison.value) {
    return [];
  }

  return [
    { label: "开盘价", count: comparison.value.mismatch_summary.open_mismatch_count },
    { label: "最高价", count: comparison.value.mismatch_summary.high_mismatch_count },
    { label: "最低价", count: comparison.value.mismatch_summary.low_mismatch_count },
    { label: "收盘价", count: comparison.value.mismatch_summary.close_mismatch_count },
    { label: "成交量", count: comparison.value.mismatch_summary.volume_mismatch_count },
    { label: "成交额", count: comparison.value.mismatch_summary.amount_mismatch_count },
  ];
});

const jointAnomalyRows = computed(() => jointAnomalies.value?.rows ?? []);
const hasUnappliedChanges = computed(() => serializeFilters(snapshotFilters()) !== serializeFilters(appliedFilters.value));

function panelHint(state: PanelState, idleText: string) {
  if (state.loading) {
    return "分析中";
  }
  return state.notice || idleText;
}

function emptyStateTitle(state: PanelState, emptyTitle: string, loadingTitle: string) {
  if (state.loading) {
    return loadingTitle;
  }
  if (state.notice) {
    return isDataInsufficientMessage(state.notice) ? "数据不足分析" : "加载失败";
  }
  return emptyTitle;
}

function emptyStateDescription(state: PanelState, emptyDescription: string, loadingDescription = "正在请求最新分析结果。") {
  if (state.loading) {
    return loadingDescription;
  }
  return state.notice || emptyDescription;
}

function resetPanelStates() {
  Object.values(panelStates).forEach((state) => {
    state.loading = false;
    state.notice = "";
  });
}

function parseTopN(rawInput: string) {
  const normalized = rawInput.trim();
  if (!normalized) {
    return undefined;
  }

  const parsed = Number(normalized);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error("Top N 必须是正整数，留空则返回全部结果。");
  }
  return parsed;
}

function snapshotFilters(source: AnalysisFilters = draftForm): AnalysisFilters {
  return {
    importRunId: source.importRunId,
    instrumentCode: source.instrumentCode,
    startDate: source.startDate,
    endDate: source.endDate,
    crossMetric: source.crossMetric,
    topNInput: source.topNInput,
    compareRunId: source.compareRunId,
    compareInstrumentCode: source.compareInstrumentCode,
    compareStartDate: source.compareStartDate,
    compareEndDate: source.compareEndDate,
    correlationInstrumentCodes: [...source.correlationInstrumentCodes],
  };
}

function serializeFilters(source: AnalysisFilters | null) {
  return JSON.stringify(source);
}

function buildScopeParams(filters: AnalysisFilters) {
  if (!filters.importRunId || !filters.instrumentCode) {
    throw new Error("请先选择主分析范围的批次和标的。");
  }

  return {
    import_run_id: filters.importRunId,
    instrument_code: filters.instrumentCode,
    start_date: filters.startDate || undefined,
    end_date: filters.endDate || undefined,
  };
}

function defaultCorrelationCodes(rows: TradingInstrumentRead[], preferredCode: string) {
  const selectedCodes: string[] = [];
  if (preferredCode && rows.some((item) => item.instrument_code === preferredCode)) {
    selectedCodes.push(preferredCode);
  }

  rows.forEach((item) => {
    if (selectedCodes.length >= 6 || selectedCodes.includes(item.instrument_code)) {
      return;
    }
    selectedCodes.push(item.instrument_code);
  });
  return selectedCodes;
}

function formatImportRunDisplayLabel(runId: number | null | undefined) {
  if (!runId) {
    return "--";
  }
  const displayId = importRunDisplayIdMap.value.get(runId);
  return `#${displayId ?? runId}`;
}

function formatScopeInstrumentLabel(scope: TradingComparisonScopeRead) {
  if (!scope.instrument_code) {
    return "全部标的";
  }
  return `${scope.instrument_code}${scope.instrument_name ? ` · ${scope.instrument_name}` : ""}`;
}

function formatScopeRequestedRange(scope: TradingComparisonScopeRead) {
  return `${scope.requested_start_date ?? "起始不限"} ~ ${scope.requested_end_date ?? "结束不限"}`;
}

function formatScopeActualRange(scope: TradingComparisonScopeRead) {
  return `${scope.actual_start_date} ~ ${scope.actual_end_date}`;
}

function syncCompareRunSelection() {
  const candidateIds = compareRunOptions.value.map((item) => item.id);
  if (!candidateIds.length) {
    draftForm.compareRunId = undefined;
    return;
  }

  if (draftForm.compareRunId && candidateIds.includes(draftForm.compareRunId)) {
    return;
  }

  const defaultRunId = candidateIds.find((item) => item !== draftForm.importRunId) ?? draftForm.importRunId;
  draftForm.compareRunId = defaultRunId;
}

function syncCorrelationSelection(rows: TradingInstrumentRead[], preferDefault = false) {
  if (!rows.length) {
    draftForm.correlationInstrumentCodes = [];
    return;
  }

  const validCurrentCodes = draftForm.correlationInstrumentCodes.filter((code) =>
    rows.some((item) => item.instrument_code === code)
  );
  if (!validCurrentCodes.length || preferDefault) {
    draftForm.correlationInstrumentCodes = defaultCorrelationCodes(rows, draftForm.instrumentCode);
    return;
  }

  const mergedCodes = [
    draftForm.instrumentCode,
    ...validCurrentCodes.filter((code) => code !== draftForm.instrumentCode),
  ].filter(Boolean);

  rows.forEach((item) => {
    if (mergedCodes.length >= 6 || mergedCodes.includes(item.instrument_code)) {
      return;
    }
    mergedCodes.push(item.instrument_code);
  });

  draftForm.correlationInstrumentCodes = mergedCodes.slice(0, Math.min(6, rows.length));
}

async function loadRuns(preferredRunId?: number) {
  loadingRuns.value = true;
  error.value = "";
  try {
    const rows = await fetchImportRuns({ limit: 50 });
    importRuns.value = rows;
    if (!rows.length) {
      Object.assign(draftForm, createDefaultFilters());
      appliedFilters.value = null;
      instruments.value = [];
      compareInstruments.value = [];
      clearAnalysisResults();
      return;
    }

    const fallbackRunId = preferredRunId && rows.some((row) => row.id === preferredRunId) ? preferredRunId : rows[0].id;
    draftForm.importRunId = fallbackRunId;
    syncCompareRunSelection();
    await loadInstruments(true);
    if (draftForm.instrumentCode) {
      await applyFilters();
    }
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loadingRuns.value = false;
  }
}

async function loadInstruments(preferDefaults = false) {
  if (!draftForm.importRunId) {
    instruments.value = [];
    draftForm.instrumentCode = "";
    draftForm.correlationInstrumentCodes = [];
    compareInstruments.value = [];
    draftForm.compareInstrumentCode = "";
    return;
  }

  try {
    const rows = await fetchTradingInstruments(draftForm.importRunId);
    instruments.value = rows;
    if (!rows.length) {
      draftForm.instrumentCode = "";
      draftForm.correlationInstrumentCodes = [];
      compareInstruments.value = [];
      draftForm.compareInstrumentCode = "";
      appliedFilters.value = null;
      clearAnalysisResults();
      return;
    }

    if (!rows.some((row) => row.instrument_code === draftForm.instrumentCode)) {
      draftForm.instrumentCode = rows[0].instrument_code;
    }

    syncCompareRunSelection();
    syncCorrelationSelection(rows, preferDefaults);
    await loadCompareInstruments(preferDefaults);
  } catch (err) {
    error.value = getErrorMessage(err);
  }
}

async function loadCompareInstruments(preferDefaults = false) {
  if (!draftForm.compareRunId) {
    compareInstruments.value = [];
    draftForm.compareInstrumentCode = "";
    return;
  }

  try {
    const rows =
      draftForm.compareRunId === draftForm.importRunId ? instruments.value : await fetchTradingInstruments(draftForm.compareRunId);
    compareInstruments.value = rows;
    if (!rows.length) {
      draftForm.compareInstrumentCode = "";
      return;
    }

    if (!draftForm.compareInstrumentCode) {
      if (preferDefaults && rows.some((item) => item.instrument_code === draftForm.instrumentCode)) {
        draftForm.compareInstrumentCode = draftForm.instrumentCode;
      }
      return;
    }

    if (!rows.some((item) => item.instrument_code === draftForm.compareInstrumentCode)) {
      draftForm.compareInstrumentCode = rows.some((item) => item.instrument_code === draftForm.instrumentCode)
        ? draftForm.instrumentCode
        : "";
    }
  } catch (err) {
    error.value = getErrorMessage(err);
  }
}

async function handleBaseRunChange() {
  await loadInstruments(true);
}

async function handleBaseInstrumentChange() {
  syncCorrelationSelection(instruments.value, true);
  await loadCompareInstruments(true);
}

async function handleCompareRunChange() {
  await loadCompareInstruments(false);
}

function clearAnalysisResults() {
  summary.value = null;
  quality.value = null;
  indicators.value = null;
  risk.value = null;
  anomalies.value = null;
  jointAnomalies.value = null;
  crossSection.value = null;
  correlation.value = null;
  comparison.value = null;
  resetPanelStates();
}

async function loadPanel<T>(
  state: PanelState,
  loader: () => Promise<T>,
  assign: (value: T | null) => void,
) {
  assign(null);
  state.loading = true;
  state.notice = "";

  try {
    const payload = await loader();
    assign(payload);
    return true;
  } catch (err) {
    const message = getErrorMessage(err);
    assign(null);
    state.notice = message;
    if (!isDataInsufficientMessage(message) && !error.value) {
      error.value = message;
    }
    return false;
  } finally {
    state.loading = false;
  }
}

async function loadAnalysis(filters: AnalysisFilters) {
  if (!filters.importRunId || !filters.instrumentCode) {
    clearAnalysisResults();
    return;
  }

  loadingAnalysis.value = true;
  error.value = "";
  clearAnalysisResults();

  try {
    const scopeParams = buildScopeParams(filters);
    const topN = parseTopN(filters.topNInput);
    const correlationCodes = filters.correlationInstrumentCodes.length
      ? filters.correlationInstrumentCodes.join(",")
      : undefined;

    const results = await Promise.all([
      loadPanel(panelStates.summary, () => fetchTradingSummary(scopeParams), (value) => {
        summary.value = value;
      }),
      loadPanel(panelStates.quality, () => fetchTradingQuality(scopeParams), (value) => {
        quality.value = value;
      }),
      loadPanel(panelStates.indicators, () => fetchTradingIndicators(scopeParams), (value) => {
        indicators.value = value;
      }),
      loadPanel(panelStates.risk, () => fetchTradingRisk(scopeParams), (value) => {
        risk.value = value;
      }),
      loadPanel(panelStates.anomalies, () => fetchTradingAnomalies(scopeParams), (value) => {
        anomalies.value = value;
      }),
      loadPanel(
        panelStates.jointAnomalies,
        () =>
          fetchTradingJointAnomalyRanking({
            import_run_id: filters.importRunId!,
            start_date: filters.startDate || undefined,
            end_date: filters.endDate || undefined,
            top_n: topN,
          }),
        (value) => {
          jointAnomalies.value = value;
        }
      ),
      loadPanel(
        panelStates.crossSection,
        () =>
          fetchTradingCrossSection({
            import_run_id: filters.importRunId!,
            start_date: filters.startDate || undefined,
            end_date: filters.endDate || undefined,
            metric: filters.crossMetric,
            top_n: topN,
          }),
        (value) => {
          crossSection.value = value;
        }
      ),
      loadPanel(
        panelStates.correlation,
        () =>
          fetchTradingCorrelation({
            import_run_id: filters.importRunId!,
            start_date: filters.startDate || undefined,
            end_date: filters.endDate || undefined,
            instrument_codes: correlationCodes,
          }),
        (value) => {
          correlation.value = value;
        }
      ),
      loadPanel(
        panelStates.comparison,
        () =>
          fetchTradingScopeComparison({
            base_run_id: filters.importRunId!,
            base_instrument_code: filters.instrumentCode,
            base_start_date: filters.startDate || undefined,
            base_end_date: filters.endDate || undefined,
            target_run_id: filters.compareRunId ?? filters.importRunId!,
            target_instrument_code: filters.compareInstrumentCode || undefined,
            target_start_date: filters.compareStartDate || undefined,
            target_end_date: filters.compareEndDate || undefined,
          }),
        (value) => {
          comparison.value = value;
        }
      ),
    ]);

    if (results.some(Boolean)) {
      runtime.markSynced();
    }
  } catch (err) {
    error.value = getErrorMessage(err);
    clearAnalysisResults();
  } finally {
    loadingAnalysis.value = false;
  }
}

async function applyFilters() {
  const nextFilters = snapshotFilters();
  parseTopN(nextFilters.topNInput);
  appliedFilters.value = nextFilters;
  await loadAnalysis(nextFilters);
}

onMounted(async () => {
  await loadRuns();
});
</script>

<template>
  <div class="page">
    <section class="page__header">
      <div>
        <div class="page__eyebrow">Analysis</div>
        <h2 class="page__title">交易分析中心</h2>
        <p class="page__subtitle">
          页面按“单标的分析、批次内多标的分析、范围对比”三种作用域拆分，筛选编辑后统一点击按钮应用。
        </p>
      </div>
      <div class="page__actions">
        <el-button type="primary" :loading="loadingAnalysis" @click="applyFilters">应用筛选并分析</el-button>
        <div v-if="hasUnappliedChanges" class="analysis-filters__hint">存在未应用的筛选修改。</div>
      </div>
    </section>

    <el-alert
      v-if="error"
      title="分析请求失败"
      type="error"
      :description="error"
      show-icon
      :closable="false"
    />

    <PanelCard title="分析筛选器" description="三类分析范围独立编辑，但统一点击上方按钮后生效。">
      <div class="analysis-stack">
        <div>
          <div class="analysis-subtitle">主分析范围</div>
          <el-form class="analysis-filters" label-position="top">
            <el-form-item label="当前批次">
              <el-select
                v-model="draftForm.importRunId"
                placeholder="选择批次"
                filterable
                class="analysis-filters__control"
                @change="handleBaseRunChange"
              >
                <el-option
                  v-for="item in importRuns"
                  :key="item.id"
                  :label="`#${item.display_id} - ${item.dataset_name}`"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="分析标的">
              <el-select
                v-model="draftForm.instrumentCode"
                placeholder="选择标的"
                filterable
                class="analysis-filters__control"
                @change="handleBaseInstrumentChange"
              >
                <el-option
                  v-for="item in instruments"
                  :key="item.instrument_code"
                  :label="`${item.instrument_code}${item.instrument_name ? ` · ${item.instrument_name}` : ''}`"
                  :value="item.instrument_code"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="开始日期">
              <el-date-picker
                v-model="draftForm.startDate"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="开始日期"
                class="analysis-filters__control"
              />
            </el-form-item>

            <el-form-item label="结束日期">
              <el-date-picker
                v-model="draftForm.endDate"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="结束日期"
                class="analysis-filters__control"
              />
            </el-form-item>
          </el-form>
        </div>

        <div>
          <div class="analysis-subtitle">批次内多标的分析</div>
          <el-form class="analysis-filters" label-position="top">
            <el-form-item label="横截面指标">
              <el-select v-model="draftForm.crossMetric" placeholder="横截面指标" class="analysis-filters__control">
                <el-option
                  v-for="item in crossMetricOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="Top N">
              <el-input v-model="draftForm.topNInput" placeholder="Top N" class="analysis-filters__control" />
            </el-form-item>

            <el-form-item label="相关性分析标的" class="analysis-filters__item analysis-filters__item--wide">
              <el-select
                v-model="draftForm.correlationInstrumentCodes"
                multiple
                collapse-tags
                collapse-tags-tooltip
                placeholder="相关性分析标的"
                class="analysis-filters__control"
              >
                <el-option
                  v-for="item in instruments"
                  :key="`corr-${item.instrument_code}`"
                  :label="`${item.instrument_code}${item.instrument_name ? ` · ${item.instrument_name}` : ''}`"
                  :value="item.instrument_code"
                />
              </el-select>
              <div class="analysis-filters__hint">{{ correlationHint }}</div>
            </el-form-item>
          </el-form>
        </div>

        <div>
          <div class="analysis-subtitle">范围对比</div>
          <el-form class="analysis-filters" label-position="top">
            <el-form-item label="对比批次">
              <el-select
                v-model="draftForm.compareRunId"
                placeholder="选择对比批次"
                filterable
                class="analysis-filters__control"
                @change="handleCompareRunChange"
              >
                <el-option
                  v-for="item in compareRunOptions"
                  :key="`compare-${item.id}`"
                  :label="`#${item.display_id} - ${item.dataset_name}`"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="对比标的">
              <el-select
                v-model="draftForm.compareInstrumentCode"
                placeholder="留空表示全部标的"
                clearable
                filterable
                class="analysis-filters__control"
              >
                <el-option
                  v-for="item in compareInstruments"
                  :key="`compare-instrument-${item.instrument_code}`"
                  :label="`${item.instrument_code}${item.instrument_name ? ` · ${item.instrument_name}` : ''}`"
                  :value="item.instrument_code"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="对比开始日期">
              <el-date-picker
                v-model="draftForm.compareStartDate"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="对比开始日期"
                class="analysis-filters__control"
              />
            </el-form-item>

            <el-form-item label="对比结束日期">
              <el-date-picker
                v-model="draftForm.compareEndDate"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="对比结束日期"
                class="analysis-filters__control"
              />
            </el-form-item>
          </el-form>
          <div class="analysis-filters__hint">{{ comparisonHint }}</div>
        </div>
      </div>
    </PanelCard>

    <section class="page__grid page__grid--stats">
      <StatCard
        v-for="item in analysisCards"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :tone="item.tone"
      />
    </section>

    <PanelCard title="摘要" description="展示当前标的在筛选区间内的核心成交与价格摘要。">
      <div v-if="summary" class="analysis-summary">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="标的">
            {{ summary.instrument_code }}{{ summary.instrument_name ? ` · ${summary.instrument_name}` : "" }}
          </el-descriptions-item>
          <el-descriptions-item label="区间">{{ summary.start_date }} ~ {{ summary.end_date }}</el-descriptions-item>
          <el-descriptions-item label="记录数">{{ summary.record_count }}</el-descriptions-item>
          <el-descriptions-item label="最高价">{{ formatNumberish(summary.high_price, 2) }}</el-descriptions-item>
          <el-descriptions-item label="最低价">{{ formatNumberish(summary.low_price, 2) }}</el-descriptions-item>
          <el-descriptions-item label="平均收盘价">{{ formatNumberish(summary.average_close, 2) }}</el-descriptions-item>
          <el-descriptions-item label="总成交量">{{ formatCompact(summary.total_volume, 2) }}</el-descriptions-item>
          <el-descriptions-item label="总成交额">{{ formatCompact(summary.total_amount, 2) }}</el-descriptions-item>
          <el-descriptions-item label="平均成交量">{{ formatCompact(summary.average_volume, 2) }}</el-descriptions-item>
          <el-descriptions-item label="平均振幅">{{ formatPercent(summary.average_amplitude, 2) }}</el-descriptions-item>
        </el-descriptions>
      </div>
      <EmptyState
        v-else
        :title="emptyStateTitle(panelStates.summary, '暂无摘要', '正在加载摘要')"
        :description="emptyStateDescription(panelStates.summary, '选择一个有数据的批次和标的后，这里会展示区间摘要。')"
      />
    </PanelCard>

    <PanelCard title="指标" description="含收益率、均线、EMA、MACD、RSI、Bollinger、ATR。">
      <template #actions>
        <span v-if="latestIndicatorPoint" class="pill">最新点 {{ latestIndicatorPoint.trade_date }}</span>
      </template>

      <div v-if="indicators?.points.length" class="analysis-stack">
        <EChartPanel :option="indicatorChartOption" :loading="panelStates.indicators.loading" height="360px" />

        <el-descriptions v-if="latestIndicatorPoint" :column="3" border>
          <el-descriptions-item label="日收益率">
            {{ formatPercent(latestIndicatorPoint.daily_return, 2) }}
          </el-descriptions-item>
          <el-descriptions-item label="累计收益率">
            {{ formatPercent(latestIndicatorPoint.cumulative_return, 2) }}
          </el-descriptions-item>
          <el-descriptions-item label="RSI14">
            {{ formatNumberish(latestIndicatorPoint.rsi14, 2) }}
          </el-descriptions-item>
          <el-descriptions-item label="EMA12">
            {{ formatNumberish(latestIndicatorPoint.ema12, 2) }}
          </el-descriptions-item>
          <el-descriptions-item label="EMA26">
            {{ formatNumberish(latestIndicatorPoint.ema26, 2) }}
          </el-descriptions-item>
          <el-descriptions-item label="MACD">
            {{ formatNumberish(latestIndicatorPoint.macd, 4) }}
          </el-descriptions-item>
          <el-descriptions-item label="MACD Signal">
            {{ formatNumberish(latestIndicatorPoint.macd_signal, 4) }}
          </el-descriptions-item>
          <el-descriptions-item label="MACD Histogram">
            {{ formatNumberish(latestIndicatorPoint.macd_histogram, 4) }}
          </el-descriptions-item>
          <el-descriptions-item label="ATR14">
            {{ formatNumberish(latestIndicatorPoint.atr14, 4) }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <EmptyState
        v-else
        :title="emptyStateTitle(panelStates.indicators, '暂无指标数据', '正在加载指标')"
        :description="emptyStateDescription(panelStates.indicators, '当筛选区间内存在行情记录时，这里会展示指标走势与最新值。')"
      />
    </PanelCard>

    <PanelCard title="风险" description="展示收益、波动、回撤和涨跌分布等风险画像。">
      <div v-if="risk" class="page__grid page__grid--stats">
        <StatCard label="区间收益率" :value="formatPercent(risk.interval_return, 2)" hint="首尾收盘价计算" tone="teal" />
        <StatCard label="波动率" :value="formatPercent(risk.volatility, 2)" hint="基于日收益率" tone="orange" />
        <StatCard label="最大回撤" :value="formatPercent(risk.max_drawdown, 2)" :hint="`持续 ${risk.max_drawdown_duration} 天`" tone="berry" />
        <StatCard label="上涨日占比" :value="formatPercent(risk.up_day_ratio, 2)" hint="日收益率 > 0" tone="neutral" />
        <StatCard label="平均振幅" :value="formatPercent(risk.average_amplitude, 2)" hint="(high-low)/open" tone="teal" />
        <StatCard label="最大单日上涨" :value="formatPercent(risk.max_daily_gain, 2)" hint="区间内最大正收益日" tone="orange" />
        <StatCard label="最大单日下跌" :value="formatPercent(risk.max_daily_loss, 2)" hint="区间内最大负收益日" tone="berry" />
      </div>
      <EmptyState
        v-else
        :title="emptyStateTitle(panelStates.risk, '暂无风险结果', '正在加载风险画像')"
        :description="emptyStateDescription(panelStates.risk, '完成分析后，这里会展示波动率、最大回撤、上涨日占比等指标。')"
      />
    </PanelCard>

    <PanelCard title="异常" description="全部采用可解释规则：放量、收益率异动、振幅异动、突破前高/前低。">
      <el-table v-if="anomalies?.anomalies.length" :data="anomalies.anomalies" stripe class="data-table" max-height="420">
        <el-table-column prop="trade_date" label="Trade Date" width="120" />
        <el-table-column prop="anomaly_type" label="Type" min-width="160" />
        <el-table-column label="Severity" width="120">
          <template #default="{ row }">
            <el-tag :type="toStatusTagType(row.severity)" effect="plain">{{ row.severity }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Metric" min-width="120">
          <template #default="{ row }">
            {{ formatNumberish(row.metric_value, 4) }}
          </template>
        </el-table-column>
        <el-table-column label="Threshold" min-width="120">
          <template #default="{ row }">
            {{ formatNumberish(row.threshold_value, 4) }}
          </template>
        </el-table-column>
        <el-table-column prop="description" label="Description" min-width="280" />
      </el-table>
      <EmptyState
        v-else
        :title="emptyStateTitle(panelStates.anomalies, '未检测到异常', '正在加载异常检测')"
        :description="emptyStateDescription(panelStates.anomalies, '如果没有满足规则阈值的记录，这里会保持空状态。')"
      />
    </PanelCard>

    <PanelCard title="横截面 / 相关性" description="仅在当前批次与当前日期范围内执行多标的排序和收益率相关性矩阵分析。">
      <div class="analysis-stack">
        <div>
          <div class="analysis-subtitle">横截面排序</div>
          <el-table v-if="crossSection?.rows.length" :data="crossSection.rows" stripe class="data-table" max-height="420">
            <el-table-column prop="instrument_code" label="Code" min-width="130" />
            <el-table-column prop="instrument_name" label="Name" min-width="180" />
            <el-table-column label="Return" min-width="120">
              <template #default="{ row }">
                {{ formatPercent(row.total_return, 2) }}
              </template>
            </el-table-column>
            <el-table-column label="Volatility" min-width="120">
              <template #default="{ row }">
                {{ formatPercent(row.volatility, 2) }}
              </template>
            </el-table-column>
            <el-table-column label="Amount" min-width="140">
              <template #default="{ row }">
                {{ formatCompact(row.total_amount, 2) }}
              </template>
            </el-table-column>
            <el-table-column label="Amplitude" min-width="120">
              <template #default="{ row }">
                {{ formatPercent(row.average_amplitude, 2) }}
              </template>
            </el-table-column>
          </el-table>
          <EmptyState
            v-else
            :title="emptyStateTitle(panelStates.crossSection, '暂无横截面结果', '正在加载横截面分析')"
            :description="emptyStateDescription(panelStates.crossSection, '这里会展示同一批次内多标的的区间排序结果。')"
          />
        </div>

        <div>
          <div class="analysis-subtitle">相关性矩阵</div>
          <el-table v-if="correlationTableRows.length" :data="correlationTableRows" stripe class="data-table" max-height="420">
            <el-table-column prop="instrument_code" label="Code" width="120" fixed />
            <el-table-column
              v-for="code in correlation?.instrument_codes || []"
              :key="`corr-col-${code}`"
              :prop="code"
              :label="code"
              min-width="110"
            >
              <template #default="{ row }">
                {{ row[code] === null ? "--" : formatNumberish(Number(row[code]), 2) }}
              </template>
            </el-table-column>
          </el-table>
          <EmptyState
            v-else
            :title="emptyStateTitle(panelStates.correlation, '暂无相关性结果', '正在加载相关性矩阵')"
            :description="emptyStateDescription(panelStates.correlation, '相关性需要至少两个标的且存在重叠收益率样本。')"
          />
        </div>
      </div>
    </PanelCard>

    <PanelCard title="数据质量 / 范围对比" description="数据质量仍围绕主分析范围；范围对比用于校验两个分析范围的差异与一致性。">
      <div class="analysis-stack">
        <div>
          <div class="analysis-subtitle">数据质量</div>
          <el-descriptions v-if="quality" :column="2" border>
            <el-descriptions-item label="覆盖率">
              {{ formatPercent(quality.coverage_ratio, 2) }}
            </el-descriptions-item>
            <el-descriptions-item label="缺失交易日">
              {{ quality.missing_trade_date_count }}
            </el-descriptions-item>
            <el-descriptions-item label="OHLC 非法行">
              {{ quality.invalid_ohlc_count }}
            </el-descriptions-item>
            <el-descriptions-item label="非正价格行">
              {{ quality.non_positive_price_count }}
            </el-descriptions-item>
            <el-descriptions-item label="非正成交量行">
              {{ quality.non_positive_volume_count }}
            </el-descriptions-item>
            <el-descriptions-item label="非正成交额行">
              {{ quality.non_positive_amount_count ?? "--" }}
            </el-descriptions-item>
            <el-descriptions-item label="平盘天数">
              {{ quality.flat_days_count }}
            </el-descriptions-item>
            <el-descriptions-item label="参考日期数">
              {{ quality.reference_date_count }}
            </el-descriptions-item>
          </el-descriptions>

          <div v-if="quality?.missing_trade_dates.length" class="analysis-tags">
            <span v-for="item in quality.missing_trade_dates" :key="item" class="pill">{{ item }}</span>
          </div>
          <EmptyState
            v-else-if="!quality"
            :title="emptyStateTitle(panelStates.quality, '暂无数据质量结果', '正在加载数据质量')"
            :description="emptyStateDescription(panelStates.quality, '这里会展示覆盖率、缺失交易日和异常值统计。')"
          />
        </div>

        <div>
          <div class="analysis-subtitle">范围对比</div>
          <div v-if="comparison" class="analysis-compare">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="当前范围批次">
                {{ formatImportRunDisplayLabel(comparison.base_scope.import_run_id) }}
              </el-descriptions-item>
              <el-descriptions-item label="对比范围批次">
                {{ formatImportRunDisplayLabel(comparison.target_scope.import_run_id) }}
              </el-descriptions-item>
              <el-descriptions-item label="当前范围标的">
                {{ formatScopeInstrumentLabel(comparison.base_scope) }}
              </el-descriptions-item>
              <el-descriptions-item label="对比范围标的">
                {{ formatScopeInstrumentLabel(comparison.target_scope) }}
              </el-descriptions-item>
              <el-descriptions-item label="当前筛选区间">
                {{ formatScopeRequestedRange(comparison.base_scope) }}
              </el-descriptions-item>
              <el-descriptions-item label="对比筛选区间">
                {{ formatScopeRequestedRange(comparison.target_scope) }}
              </el-descriptions-item>
              <el-descriptions-item label="当前有效数据区间">
                {{ formatScopeActualRange(comparison.base_scope) }}
              </el-descriptions-item>
              <el-descriptions-item label="对比有效数据区间">
                {{ formatScopeActualRange(comparison.target_scope) }}
              </el-descriptions-item>
              <el-descriptions-item label="当前范围记录数">{{ comparison.base_scope.record_count }}</el-descriptions-item>
              <el-descriptions-item label="对比范围记录数">{{ comparison.target_scope.record_count }}</el-descriptions-item>
              <el-descriptions-item label="当前范围标的数">{{ comparison.base_scope.instrument_count }}</el-descriptions-item>
              <el-descriptions-item label="对比范围标的数">{{ comparison.target_scope.instrument_count }}</el-descriptions-item>
              <el-descriptions-item label="当前范围成交额">
                {{ formatCompact(comparison.base_scope.total_amount, 2) }}
              </el-descriptions-item>
              <el-descriptions-item label="对比范围成交额">
                {{ formatCompact(comparison.target_scope.total_amount, 2) }}
              </el-descriptions-item>
            </el-descriptions>

            <section class="page__grid page__grid--stats">
              <StatCard
                label="共同交易记录"
                :value="String(comparison.record_overlap.shared_record_count)"
                :hint="`${comparison.record_overlap.shared_trade_date_count} 个共同交易日`"
                tone="teal"
              />
              <StatCard
                label="一致记录"
                :value="String(comparison.mismatch_summary.matching_record_count)"
                hint="共同记录中完全一致的条数"
                tone="orange"
              />
              <StatCard
                label="不一致记录"
                :value="String(comparison.mismatch_summary.mismatched_record_count)"
                hint="共同记录中至少一个字段不一致"
                tone="berry"
              />
              <StatCard
                label="范围独有记录"
                :value="String(comparison.record_overlap.base_only_record_count + comparison.record_overlap.target_only_record_count)"
                hint="两边无法按标的+日期配对的记录"
                tone="neutral"
              />
            </section>

            <div>
              <div class="analysis-compare__label">共同标的</div>
              <div class="analysis-tags">
                <span
                  v-for="item in comparison.instrument_overlap.shared_instruments"
                  :key="`shared-${item}`"
                  class="pill"
                >
                  {{ item }}
                </span>
              </div>
            </div>

            <div>
              <div class="analysis-compare__label">当前范围独有标的</div>
              <div class="analysis-tags">
                <span
                  v-for="item in comparison.instrument_overlap.base_only_instruments"
                  :key="`base-only-${item}`"
                  class="pill"
                >
                  {{ item }}
                </span>
              </div>
            </div>

            <div>
              <div class="analysis-compare__label">对比范围独有标的</div>
              <div class="analysis-tags">
                <span
                  v-for="item in comparison.instrument_overlap.target_only_instruments"
                  :key="`target-only-${item}`"
                  class="pill"
                >
                  {{ item }}
                </span>
              </div>
            </div>

            <div>
              <div class="analysis-compare__label">字段不一致分布</div>
              <el-table :data="comparisonMismatchRows" stripe class="data-table" max-height="420">
                <el-table-column prop="label" label="字段" min-width="140" />
                <el-table-column prop="count" label="不一致条数" min-width="140" />
              </el-table>
            </div>

            <div v-if="comparison.mismatch_samples.length">
              <div class="analysis-compare__label">不一致样例</div>
              <el-table :data="comparison.mismatch_samples" stripe class="data-table" max-height="420">
                <el-table-column prop="instrument_code" label="标的" min-width="120" />
                <el-table-column prop="trade_date" label="交易日" min-width="120" />
                <el-table-column label="不一致字段" min-width="180">
                  <template #default="{ row }">
                    {{ row.mismatched_fields.join(" / ") }}
                  </template>
                </el-table-column>
                <el-table-column label="当前范围值" min-width="260">
                  <template #default="{ row }">
                    close {{ formatNumberish(row.base_values.close, 2) }},
                    volume {{ formatNumberish(row.base_values.volume, 2) }},
                    amount {{ formatCompact(row.base_values.amount, 2) }}
                  </template>
                </el-table-column>
                <el-table-column label="对比范围值" min-width="260">
                  <template #default="{ row }">
                    close {{ formatNumberish(row.target_values.close, 2) }},
                    volume {{ formatNumberish(row.target_values.volume, 2) }},
                    amount {{ formatCompact(row.target_values.amount, 2) }}
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <el-alert
              v-else-if="comparison.record_overlap.shared_record_count > 0"
              title="共同记录全部一致"
              type="success"
              :closable="false"
              description="两个范围在可对齐的共同记录上没有发现字段差异，可作为基线校验结果。"
            />

            <el-alert
              v-else
              title="没有共同交易记录"
              type="info"
              :closable="false"
              description="当前只展示两边范围的摘要和标的差异，因为没有可按标的+日期配对的共同记录。"
            />
          </div>
          <EmptyState
            v-else
            :title="emptyStateTitle(panelStates.comparison, '暂无范围对比结果', '正在加载范围对比')"
            :description="emptyStateDescription(panelStates.comparison, '这里会展示两个分析范围的摘要差异、重叠记录和一致性校验结果。')"
          />
        </div>
      </div>
    </PanelCard>
    <PanelCard title="CDQ Joint Anomalies" description="Across all instruments, rank days by joint return shock and volume expansion using historical CDQ dominance counts.">
      <el-table v-if="jointAnomalyRows.length" :data="jointAnomalyRows" stripe class="data-table" max-height="420">
        <el-table-column prop="trade_date" label="Trade Date" width="120" />
        <el-table-column prop="instrument_code" label="Code" min-width="120" />
        <el-table-column prop="instrument_name" label="Name" min-width="180" />
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
        :title="emptyStateTitle(panelStates.jointAnomalies, '暂无联合异常结果', '正在加载联合异常')"
        :description="emptyStateDescription(panelStates.jointAnomalies, '该排名需要足够的 20 日历史样本，且事件达到中等级以上阈值后才会出现。')"
      />
    </PanelCard>
  </div>
</template>

<style scoped>
.analysis-filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 14px;
}

.analysis-filters :deep(.el-form-item) {
  margin-bottom: 0;
}

.analysis-filters__control {
  width: 100%;
}

.analysis-filters__item--wide {
  grid-column: 1 / -1;
}

.analysis-filters__hint {
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.analysis-stack {
  display: grid;
  gap: 18px;
}

.analysis-summary,
.analysis-compare {
  display: grid;
  gap: 16px;
}

.analysis-subtitle {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.analysis-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.analysis-compare__label {
  margin-bottom: 10px;
  color: var(--text-secondary);
  font-weight: 700;
}
</style>
