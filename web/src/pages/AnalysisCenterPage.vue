<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import type { EChartsOption } from "echarts";
import { NAlert, NButton, NForm, NFormItem, NInput, NPagination, NSelect, NTable, NTag } from "naive-ui";
import { useRoute } from "vue-router";

import {
  fetchTradingAnomalies,
  fetchTradingCorrelation,
  fetchTradingCrossSection,
  fetchTradingIndicators,
  fetchTradingQuality,
  fetchTradingRisk,
  fetchTradingSnapshot,
  fetchTradingScopeComparison,
  fetchTradingSummary,
} from "@/api/analysis";
import { fetchImportRuns, fetchImportStats } from "@/api/imports";
import { fetchTradingStocks } from "@/api/trading";
import type {
  ImportRunRead,
  TradingAnomalyReportRead,
  TradingCorrelationMatrixRead,
  TradingCrossSectionRead,
  TradingDataContractRead,
  TradingIndicatorSeriesRead,
  TradingQualityReportRead,
  TradingRiskMetricsRead,
  TradingSnapshotRead,
  TradingScopeComparisonRead,
  TradingStockRead,
  TradingSummaryRead,
} from "@/api/types";
import DateInputField from "@/components/DateInputField.vue";
import EChartPanel from "@/components/EChartPanel.vue";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import StatCard from "@/components/StatCard.vue";
import { useTablePager } from "@/composables/useTablePager";
import { useDatasetContextStore } from "@/stores/datasetContext";
import { useRuntimeStore } from "@/stores/runtime";
import { formatCompact, formatDate, formatNumberish, formatPercent, getErrorMessage, toNumber, toStatusTagType } from "@/utils/format";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";
import { formatSeverityText, TECHNICAL_TEXT } from "@/utils/displayText";


const ANALYSIS_SECTION_TABS = [
  {
    key: "market",
    label: "金融分析",
  },
  {
    key: "governance",
    label: "数据治理与快照",
  },
] as const;

const runtime = useRuntimeStore();
const datasetContext = useDatasetContextStore();
const route = useRoute();
const loadingRuns = ref(false);
const loadingAnalysis = ref(false);
const error = ref("");
usePageErrorNotification(error, "分析中心加载失败");

const importRuns = ref<ImportRunRead[]>([]);
const stocks = ref<TradingStockRead[]>([]);
const compareStocks = ref<TradingStockRead[]>([]);

const filters = reactive({
  importRunId: undefined as number | undefined,
  stockCode: "",
  startDate: "",
  endDate: "",
  crossMetric: "total_return",
  topNInput: "10",
  compareRunId: undefined as number | undefined,
  compareStockCode: "",
  compareStartDate: "",
  compareEndDate: "",
  correlationStockCodes: [] as string[],
});

const summary = ref<TradingSummaryRead | null>(null);
const quality = ref<TradingQualityReportRead | null>(null);
const indicators = ref<TradingIndicatorSeriesRead | null>(null);
const risk = ref<TradingRiskMetricsRead | null>(null);
const snapshot = ref<TradingSnapshotRead | null>(null);
const anomalies = ref<TradingAnomalyReportRead | null>(null);
const crossSection = ref<TradingCrossSectionRead | null>(null);
const correlation = ref<TradingCorrelationMatrixRead | null>(null);
const comparison = ref<TradingScopeComparisonRead | null>(null);
const panelNotices = reactive({
  summary: "",
  quality: "",
  indicators: "",
  risk: "",
  snapshot: "",
  anomalies: "",
  crossSection: "",
  correlation: "",
  comparison: "",
});

const crossMetricOptions = [
  { label: "区间收益", value: "total_return" },
  { label: "波动", value: "volatility" },
  { label: "成交量", value: "total_volume" },
  { label: "成交额", value: "total_amount" },
  { label: "平均振幅", value: "average_amplitude" },
];

const importRunOptions = computed(() =>
  importRuns.value.map((item) => ({ label: `#${item.display_id} · ${item.dataset_name}`, value: item.id }))
);
const currentImportRun = computed(() => importRuns.value.find((item) => item.id === filters.importRunId) ?? null);
const stockOptions = computed(() =>
  stocks.value.map((item) => ({ label: `${item.stock_code}${item.stock_name ? ` · ${item.stock_name}` : ""}`, value: item.stock_code }))
);
const compareStockOptions = computed(() =>
  compareStocks.value.map((item) => ({ label: `${item.stock_code}${item.stock_name ? ` · ${item.stock_name}` : ""}`, value: item.stock_code }))
);
const currentSection = computed<(typeof ANALYSIS_SECTION_TABS)[number]["key"]>(() =>
  route.path.startsWith("/analysis/governance") ? "governance" : "market"
);
const isMarketSection = computed(() => currentSection.value === "market");

const cards = computed(() => {
  if (isMarketSection.value) {
    return [
      {
        label: "最新收盘价",
        value: summary.value ? formatNumberish(summary.value.latest_close, 2) : "--",
        hint: summary.value ? `${formatDate(summary.value.end_date)} 收盘价` : "等待金融分析",
        tone: "teal" as const,
      },
      {
        label: "区间收益",
        value: risk.value ? formatPercent(risk.value.interval_return, 2) : "--",
        hint: risk.value ? `${risk.value.record_count} 条记录` : "等待金融分析",
        tone: "orange" as const,
      },
      {
        label: "最大回撤",
        value: risk.value ? formatPercent(risk.value.max_drawdown, 2) : "--",
        hint: risk.value ? `持续 ${risk.value.max_drawdown_duration} 天` : "等待金融分析",
        tone: "berry" as const,
      },
      {
        label: "Beta60",
        value: risk.value?.beta60 === null || risk.value?.beta60 === undefined ? "--" : formatNumberish(risk.value.beta60, 4),
        hint: risk.value?.missing_fields.includes("benchmark_close") ? "缺少 benchmark_close" : "系统性风险指标",
        tone: "neutral" as const,
      },
    ];
  }

  return [
    {
      label: "覆盖率",
      value: quality.value ? formatPercent(quality.value.coverage_ratio, 2) : "--",
      hint: quality.value ? `${quality.value.record_count} 条记录` : "等待治理分析",
      tone: "teal" as const,
    },
    {
      label: "缺失交易日",
      value: quality.value ? String(quality.value.missing_trade_date_count) : "--",
      hint: quality.value ? "基于同批次交易日历" : "等待治理分析",
      tone: "orange" as const,
    },
    {
      label: "差异记录",
      value: comparison.value ? String(comparison.value.mismatch_summary.mismatched_record_count) : "--",
      hint: comparison.value ? `${comparison.value.record_overlap.shared_record_count} 条共同记录` : "等待范围对比",
      tone: "berry" as const,
    },
    {
      label: "快照状态",
      value: snapshot.value ? (snapshotHasValues.value ? "可用" : "缺字段") : "--",
      hint: snapshot.value?.missing_fields.length ? `缺少 ${snapshot.value.missing_fields.join("、")}` : "等待快照分析",
      tone: "neutral" as const,
    },
  ];
});

const importRunDisplayMap = computed(() => new Map(importRuns.value.map((item) => [item.id, item.display_id])));

const indicatorChartOption = computed<EChartsOption | null>(() => {
  if (!indicators.value?.points.length) {
    return null;
  }

  return {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" },
    legend: { top: 0 },
    grid: { left: 48, right: 32, top: 56, bottom: 28 },
    xAxis: { type: "category", boundaryGap: false, data: indicators.value.points.map((item) => item.trade_date) },
    yAxis: [{ type: "value", name: TECHNICAL_TEXT.price }, { type: "value", name: TECHNICAL_TEXT.volume }],
    series: [
      { type: "line", name: TECHNICAL_TEXT.close, smooth: true, showSymbol: false, data: indicators.value.points.map((item) => toNumber(item.close)) },
      { type: "line", name: TECHNICAL_TEXT.ma5, smooth: true, showSymbol: false, data: indicators.value.points.map((item) => toNumber(item.ma5)) },
      { type: "line", name: TECHNICAL_TEXT.ma20, smooth: true, showSymbol: false, data: indicators.value.points.map((item) => toNumber(item.ma20)) },
      { type: "line", name: "MA60", smooth: true, showSymbol: false, data: indicators.value.points.map((item) => toNumber(item.ma60)) },
      { type: "bar", name: TECHNICAL_TEXT.volume, yAxisIndex: 1, barMaxWidth: 14, data: indicators.value.points.map((item) => toNumber(item.volume)) },
    ],
  };
});

const latestIndicatorPoint = computed(() => indicators.value?.points.at(-1) ?? null);
const snapshotHasValues = computed(() =>
  Boolean(
    snapshot.value &&
      [snapshot.value.pe_ttm, snapshot.value.pb, snapshot.value.roe, snapshot.value.asset_liability_ratio, snapshot.value.revenue_yoy, snapshot.value.net_profit_yoy].some(
        (item) => item !== null && item !== undefined
      )
  )
);
const correlationRows = computed(() => {
  if (!correlation.value) {
    return [];
  }
  return correlation.value.stock_codes.map((code, rowIndex) => ({
    stock_code: code,
    values: correlation.value!.stock_codes.map((item, columnIndex) => ({
      key: `${code}-${item}`,
      value: correlation.value!.matrix[rowIndex]?.[columnIndex] ?? null,
    })),
  }));
});
const comparisonMismatchRows = computed(() =>
  comparison.value
    ? [
        ["开盘价", comparison.value.mismatch_summary.open_mismatch_count],
        ["最高价", comparison.value.mismatch_summary.high_mismatch_count],
        ["最低价", comparison.value.mismatch_summary.low_mismatch_count],
        ["收盘价", comparison.value.mismatch_summary.close_mismatch_count],
        ["成交量", comparison.value.mismatch_summary.volume_mismatch_count],
        ["成交额", comparison.value.mismatch_summary.amount_mismatch_count],
      ]
    : []
);
const anomalyRows = computed(() => anomalies.value?.anomalies ?? []);
const crossSectionRows = computed(() => crossSection.value?.rows ?? []);
const mismatchSampleRows = computed(() => comparison.value?.mismatch_samples ?? []);
const analysisScopeKey = computed(
  () =>
    [
      filters.importRunId ?? "",
      filters.stockCode,
      filters.startDate,
      filters.endDate,
      filters.crossMetric,
      filters.topNInput,
      filters.compareRunId ?? "",
      filters.compareStockCode,
      filters.compareStartDate,
      filters.compareEndDate,
      filters.correlationStockCodes.join(","),
      currentSection.value,
    ].join("|")
);
const anomalyPager = useTablePager(anomalyRows, {
  initialPageSize: 20,
  pageSizes: [10, 20, 50, 100],
  resetTriggers: [analysisScopeKey],
});
const crossSectionPager = useTablePager(crossSectionRows, {
  initialPageSize: 20,
  pageSizes: [10, 20, 50, 100],
  resetTriggers: [analysisScopeKey],
});
const mismatchSamplePager = useTablePager(mismatchSampleRows, {
  initialPageSize: 20,
  pageSizes: [10, 20, 50, 100],
  resetTriggers: [analysisScopeKey],
});

function formatModuleSummary(contract: TradingDataContractRead | null | undefined) {
  if (!contract) {
    return "";
  }
  const parts = [`频率：${contract.data_frequency}`, `字段：${contract.required_fields.join("、") || "--"}`];
  if (contract.missing_fields.length) {
    parts.push(`缺字段：${contract.missing_fields.join("、")}`);
  }
  return parts.join(" · ");
}

function parseTopN() {
  const raw = filters.topNInput.trim();
  if (!raw) {
    return undefined;
  }
  const value = Number(raw);
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error("前N(Top N)必须是正整数");
  }
  return value;
}

type AnalysisPanelNoticeKey = keyof typeof panelNotices;

function clearPanelNotices() {
  (Object.keys(panelNotices) as AnalysisPanelNoticeKey[]).forEach((key) => {
    panelNotices[key] = "";
  });
}

function pickVisibleRunId(runRows: ImportRunRead[], candidates: Array<number | undefined>) {
  return candidates.find((candidate) => candidate !== undefined && runRows.some((item) => item.id === candidate)) ?? runRows[0]?.id;
}

function formatRunLabel(runId?: number | null) {
  if (!runId) {
    return "--";
  }

  return `#${importRunDisplayMap.value.get(runId) ?? runId}`;
}

function resolveAnalysisPanelResult<T>(result: PromiseSettledResult<T>, key: AnalysisPanelNoticeKey, label: string) {
  if (result.status === "fulfilled") {
    return result.value;
  }

  panelNotices[key] = `${label}加载失败：${getErrorMessage(result.reason)}`;
  return null;
}

function syncContext() {
  datasetContext.applyScope({
    importRunId: filters.importRunId,
    importRunDisplayId: currentImportRun.value?.display_id,
    stockCode: filters.stockCode,
    startDate: filters.startDate,
    endDate: filters.endDate,
  });
}

async function loadCompareStocks() {
  if (!filters.compareRunId) {
    compareStocks.value = [];
    filters.compareStockCode = "";
    return;
  }

  try {
    const rows = filters.compareRunId === filters.importRunId ? stocks.value : await fetchTradingStocks(filters.compareRunId);
    compareStocks.value = rows;

    if (filters.compareStockCode && !rows.some((item) => item.stock_code === filters.compareStockCode)) {
      filters.compareStockCode = "";
    }
  } catch (err) {
    error.value = getErrorMessage(err);
    compareStocks.value = [];
    filters.compareStockCode = "";
  }
}

async function loadStocks() {
  if (!filters.importRunId) {
    stocks.value = [];
    compareStocks.value = [];
    filters.stockCode = "";
    return;
  }

  try {
    const rows = await fetchTradingStocks(filters.importRunId);
    stocks.value = rows;
    if (!rows.some((item) => item.stock_code === filters.stockCode)) {
      filters.stockCode = rows[0]?.stock_code || "";
    }
    if (!filters.correlationStockCodes.length) {
      filters.correlationStockCodes = rows.slice(0, 6).map((item) => item.stock_code);
    } else {
      filters.correlationStockCodes = filters.correlationStockCodes.filter((code) => rows.some((item) => item.stock_code === code));
    }
    filters.compareRunId = pickVisibleRunId(importRuns.value, [filters.compareRunId, filters.importRunId]);
    await loadCompareStocks();
  } catch (err) {
    error.value = getErrorMessage(err);
    stocks.value = [];
    compareStocks.value = [];
    filters.stockCode = "";
    filters.compareStockCode = "";
  }
}

async function loadRuns(preferredRunId?: number) {
  loadingRuns.value = true;
  error.value = "";
  try {
    const statsResponse = await fetchImportStats();
    importRuns.value = await fetchImportRuns({ limit: Math.max(statsResponse.total_runs, 1) });
    filters.importRunId = pickVisibleRunId(importRuns.value, [preferredRunId, filters.importRunId, datasetContext.state.importRunId]);
    filters.compareRunId = pickVisibleRunId(importRuns.value, [filters.compareRunId, filters.importRunId]);
    await loadStocks();
    if (filters.importRunId && filters.stockCode) {
      await applyFilters();
    }
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loadingRuns.value = false;
  }
}

async function applyFilters() {
  if (!filters.importRunId || !filters.stockCode) {
    return;
  }

  loadingAnalysis.value = true;
  error.value = "";
  clearPanelNotices();
  summary.value = null;
  quality.value = null;
  indicators.value = null;
  risk.value = null;
  snapshot.value = null;
  anomalies.value = null;
  crossSection.value = null;
  correlation.value = null;
  comparison.value = null;
  syncContext();

  try {
    const topN = parseTopN();
    const baseScope = {
      import_run_id: filters.importRunId,
      stock_code: filters.stockCode,
      start_date: filters.startDate || undefined,
      end_date: filters.endDate || undefined,
    };

    const results = await Promise.allSettled([
      fetchTradingSummary(baseScope),
      fetchTradingQuality(baseScope),
      fetchTradingIndicators(baseScope),
      fetchTradingRisk(baseScope),
      fetchTradingSnapshot(baseScope),
      fetchTradingAnomalies(baseScope),
      fetchTradingCrossSection({
        import_run_id: filters.importRunId,
        start_date: filters.startDate || undefined,
        end_date: filters.endDate || undefined,
        metric: filters.crossMetric,
        top_n: topN,
      }),
      fetchTradingCorrelation({
        import_run_id: filters.importRunId,
        start_date: filters.startDate || undefined,
        end_date: filters.endDate || undefined,
        stock_codes: filters.correlationStockCodes.join(",") || undefined,
      }),
      fetchTradingScopeComparison({
        base_run_id: filters.importRunId,
        base_stock_code: filters.stockCode,
        base_start_date: filters.startDate || undefined,
        base_end_date: filters.endDate || undefined,
        target_run_id: filters.compareRunId ?? filters.importRunId,
        target_stock_code: filters.compareStockCode || undefined,
        target_start_date: filters.compareStartDate || undefined,
        target_end_date: filters.compareEndDate || undefined,
      }),
    ]);

    summary.value = resolveAnalysisPanelResult(results[0], "summary", "基础摘要");
    quality.value = resolveAnalysisPanelResult(results[1], "quality", "数据质量");
    indicators.value = resolveAnalysisPanelResult(results[2], "indicators", "指标序列");
    risk.value = resolveAnalysisPanelResult(results[3], "risk", "风险指标");
    snapshot.value = resolveAnalysisPanelResult(results[4], "snapshot", "估值与基本面快照");
    anomalies.value = resolveAnalysisPanelResult(results[5], "anomalies", "异常检测");
    crossSection.value = resolveAnalysisPanelResult(results[6], "crossSection", "横截面对比");
    correlation.value = resolveAnalysisPanelResult(results[7], "correlation", "相关性矩阵");
    comparison.value = resolveAnalysisPanelResult(results[8], "comparison", "范围对比");

    if (results.some((item) => item.status === "rejected")) {
      error.value = "部分分析面板加载失败，请查看对应卡片中的提示";
    }

    runtime.markSynced();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loadingAnalysis.value = false;
  }
}

async function handleBaseRunChange() {
  await loadStocks();
}

async function handleBaseStockChange() {
  if (!filters.correlationStockCodes.includes(filters.stockCode) && filters.stockCode) {
    filters.correlationStockCodes = [filters.stockCode, ...filters.correlationStockCodes].slice(0, 6);
  }
  await loadCompareStocks();
}

async function handleCompareRunChange() {
  await loadCompareStocks();
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
    <PanelCard title="分析筛选器">
      <template #actions>
        <n-button type="primary" :loading="loadingAnalysis" @click="applyFilters">执行分析</n-button>
      </template>
      <n-form class="form-grid" label-placement="top">
        <n-form-item label="主批次">
          <n-select v-model:value="filters.importRunId" :options="importRunOptions" @update:value="handleBaseRunChange" />
        </n-form-item>
        <n-form-item label="主股票">
          <n-select v-model:value="filters.stockCode" :options="stockOptions" @update:value="handleBaseStockChange" />
        </n-form-item>
        <n-form-item label="开始日期">
          <DateInputField v-model="filters.startDate" clearable />
        </n-form-item>
        <n-form-item label="结束日期">
          <DateInputField v-model="filters.endDate" clearable />
        </n-form-item>
        <n-form-item label="横截面指标">
          <n-select v-model:value="filters.crossMetric" :options="crossMetricOptions" />
        </n-form-item>
        <n-form-item label="横截面前N(Top N)">
          <n-input v-model:value="filters.topNInput" placeholder="留空表示返回全部结果" />
        </n-form-item>
        <n-form-item label="对比批次">
          <n-select v-model:value="filters.compareRunId" :options="importRunOptions" clearable @update:value="handleCompareRunChange" />
        </n-form-item>
        <n-form-item label="对比股票">
          <n-select v-model:value="filters.compareStockCode" :options="compareStockOptions" clearable />
        </n-form-item>
        <n-form-item label="对比开始日期">
          <DateInputField v-model="filters.compareStartDate" clearable />
        </n-form-item>
        <n-form-item label="对比结束日期">
          <DateInputField v-model="filters.compareEndDate" clearable />
        </n-form-item>
        <n-form-item label="相关性股票" class="form-grid--wide">
          <n-select v-model:value="filters.correlationStockCodes" :options="stockOptions" multiple clearable placeholder="建议不超过 6 只股票" />
        </n-form-item>
      </n-form>
      <div class="toolbar-row" style="margin-top: 8px;">
        <span class="inline-hint">相关性仅在当前批次内计算</span>
        <span class="inline-hint">范围对比留空股票时表示对比全部股票</span>
      </div>
    </PanelCard>

    <section class="page__grid page__grid--stats">
      <StatCard v-for="item in cards" :key="item.label" :label="item.label" :value="item.value" :hint="item.hint" :tone="item.tone" />
    </section>

    <section v-if="isMarketSection" class="page__grid page__grid--double">
      <PanelCard title="基础摘要">
        <n-alert v-if="panelNotices.summary" type="warning" :show-icon="true">{{ panelNotices.summary }}</n-alert>
        <div v-else-if="summary" class="detail-grid">
          <div class="detail-grid__item"><span class="detail-grid__label">股票</span><div class="detail-grid__value">{{ summary.stock_code }}{{ summary.stock_name ? ` · ${summary.stock_name}` : "" }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">时间范围</span><div class="detail-grid__value">{{ formatDate(summary.start_date) }} ~ {{ formatDate(summary.end_date) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">记录</span><div class="detail-grid__value">{{ summary.record_count }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">股票数</span><div class="detail-grid__value">{{ summary.stock_count }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">平均收盘</span><div class="detail-grid__value">{{ formatNumberish(summary.average_close, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">总成交额</span><div class="detail-grid__value">{{ formatCompact(summary.total_amount, 2) }}</div></div>
        </div>
        <div v-if="summary" class="inline-hint" style="margin-top: 8px;">{{ formatModuleSummary(summary) }}</div>
        <EmptyState v-else title="暂无基础摘要" description="执行分析后，这里会展示当前主范围的基础统计" />
      </PanelCard>

      <PanelCard title="数据质量">
        <n-alert v-if="panelNotices.quality" type="warning" :show-icon="true">{{ panelNotices.quality }}</n-alert>
        <div v-else-if="quality" class="detail-grid">
          <div class="detail-grid__item"><span class="detail-grid__label">覆盖</span><div class="detail-grid__value">{{ formatPercent(quality.coverage_ratio, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">缺失交易</span><div class="detail-grid__value">{{ quality.missing_trade_date_count }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">无效 OHLC</span><div class="detail-grid__value">{{ quality.invalid_ohlc_count }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">非正价格</span><div class="detail-grid__value">{{ quality.non_positive_price_count }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">非正成交</span><div class="detail-grid__value">{{ quality.non_positive_volume_count }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">平盘日数</span><div class="detail-grid__value">{{ quality.flat_days_count }}</div></div>
        </div>
        <div v-if="quality?.missing_trade_dates.length" class="inline-hint" style="margin-top: 12px;">缺失交易日：{{ quality.missing_trade_dates.join("、") }}</div>
        <EmptyState v-else-if="!quality" title="暂无质量报告" description="执行分析后，这里会返回当前范围的数据质量诊断" />
      </PanelCard>
    </section>

    <section v-if="isMarketSection" class="page__grid page__grid--double">
      <PanelCard title="指标序列">
        <n-alert v-if="panelNotices.indicators" type="warning" :show-icon="true">{{ panelNotices.indicators }}</n-alert>
        <n-alert v-else-if="indicators?.notices?.length" type="warning" :show-icon="true" style="margin-bottom: 12px;">
          {{ indicators.notices.join(" ") }}
        </n-alert>
        <EChartPanel v-else-if="indicatorChartOption" :option="indicatorChartOption" :loading="loadingAnalysis" />
        <EmptyState v-else title="暂无指标图表" description="选择主股票并执行分析后，这里会展示指标序列" />
        <div v-if="latestIndicatorPoint" class="detail-grid" style="margin-top: 16px;">
          <div class="detail-grid__item"><span class="detail-grid__label">最新日期</span><div class="detail-grid__value">{{ formatDate(latestIndicatorPoint.trade_date) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">{{ TECHNICAL_TEXT.macd }}</span><div class="detail-grid__value">{{ formatNumberish(latestIndicatorPoint.macd, 4) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">{{ TECHNICAL_TEXT.rsi14 }}</span><div class="detail-grid__value">{{ formatNumberish(latestIndicatorPoint.rsi14, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">{{ TECHNICAL_TEXT.atr14 }}</span><div class="detail-grid__value">{{ formatNumberish(latestIndicatorPoint.atr14, 4) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">Bias20</span><div class="detail-grid__value">{{ formatPercent(latestIndicatorPoint.bias20, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">ROC20</span><div class="detail-grid__value">{{ formatPercent(latestIndicatorPoint.roc20, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">NATR14</span><div class="detail-grid__value">{{ formatPercent(latestIndicatorPoint.natr14, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">HV20</span><div class="detail-grid__value">{{ formatPercent(latestIndicatorPoint.hv20, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">RVOL20</span><div class="detail-grid__value">{{ formatNumberish(latestIndicatorPoint.rvol20, 4) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">换手率 Z20</span><div class="detail-grid__value">{{ formatNumberish(latestIndicatorPoint.turnover_z20, 4) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">ILLIQ20</span><div class="detail-grid__value">{{ formatNumberish(latestIndicatorPoint.illiq20, 8) }}</div></div>
        </div>
        <div v-if="indicators" class="inline-hint" style="margin-top: 8px;">{{ formatModuleSummary(indicators) }}</div>
      </PanelCard>

      <PanelCard title="风险指标">
        <n-alert v-if="panelNotices.risk" type="warning" :show-icon="true">{{ panelNotices.risk }}</n-alert>
        <n-alert v-else-if="risk?.notices?.length" type="warning" :show-icon="true" style="margin-bottom: 12px;">
          {{ risk.notices.join(" ") }}
        </n-alert>
        <div v-else-if="risk" class="detail-grid">
          <div class="detail-grid__item"><span class="detail-grid__label">区间收益</span><div class="detail-grid__value">{{ formatPercent(risk.interval_return, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">年化波动</span><div class="detail-grid__value">{{ formatPercent(risk.volatility, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">最大回撤</span><div class="detail-grid__value">{{ formatPercent(risk.max_drawdown, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">回撤持续天数</span><div class="detail-grid__value">{{ risk.max_drawdown_duration }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">Beta60</span><div class="detail-grid__value">{{ formatNumberish(risk.beta60, 4) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">下行波动</span><div class="detail-grid__value">{{ formatPercent(risk.downside_volatility, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">HV20</span><div class="detail-grid__value">{{ formatPercent(risk.hv20, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">RVOL20</span><div class="detail-grid__value">{{ formatNumberish(risk.rvol20, 4) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">换手率 Z20</span><div class="detail-grid__value">{{ formatNumberish(risk.turnover_z20, 4) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">ILLIQ20</span><div class="detail-grid__value">{{ formatNumberish(risk.illiq20, 8) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">上涨日占比</span><div class="detail-grid__value">{{ formatPercent(risk.up_day_ratio, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">平均振幅</span><div class="detail-grid__value">{{ formatNumberish(risk.average_amplitude, 4) }}</div></div>
        </div>
        <div v-if="risk" class="inline-hint" style="margin-top: 8px;">{{ formatModuleSummary(risk) }}</div>
        <EmptyState v-else title="暂无风险画像" description="执行分析后，这里会展示主股票的风险画像" />
      </PanelCard>
    </section>

    <section v-if="isMarketSection" class="page__grid page__grid--double">
      <PanelCard title="异常检测">
        <n-alert v-if="panelNotices.anomalies" type="warning" :show-icon="true">{{ panelNotices.anomalies }}</n-alert>
      <div v-else-if="anomalyPager.total.value" class="data-table-wrap">
          <n-table class="data-table" striped size="small" :single-line="false">
            <thead><tr><th>日期</th><th>类型</th><th>严重</th><th>指标</th><th>基线</th><th>阈值</th><th>说明</th></tr></thead>
            <tbody>
              <tr v-for="item in anomalyPager.pagedRows.value" :key="`${item.trade_date}-${item.anomaly_type}`">
                <td>{{ formatDate(item.trade_date) }}</td>
                <td>{{ item.anomaly_type }}</td>
                <td><n-tag :type="toStatusTagType(item.severity)" round size="small">{{ formatSeverityText(item.severity) }}</n-tag></td>
                <td>{{ formatNumberish(item.metric_value, 4) }}</td>
                <td>{{ formatNumberish(item.baseline_value, 4) }}</td>
                <td>{{ formatNumberish(item.threshold_value, 4) }}</td>
                <td>{{ item.description }}</td>
              </tr>
            </tbody>
          </n-table>
          <div class="table-pagination">
            <n-pagination
              :page="anomalyPager.page.value"
              :page-size="anomalyPager.pageSize.value"
              :item-count="anomalyPager.total.value"
              :page-sizes="anomalyPager.pageSizes"
              show-size-picker
              @update:page="anomalyPager.setPage"
              @update:page-size="anomalyPager.setPageSize"
            />
          </div>
        </div>
        <div v-if="anomalies" class="inline-hint" style="margin-top: 8px;">{{ formatModuleSummary(anomalies) }}</div>
        <EmptyState v-else title="暂无异常结果" description="执行分析后，这里会展示主股票的异常检测结果" />
      </PanelCard>

      <PanelCard title="横截面对比">
        <n-alert v-if="panelNotices.crossSection" type="warning" :show-icon="true">{{ panelNotices.crossSection }}</n-alert>
      <div v-else-if="crossSectionPager.total.value" class="data-table-wrap">
          <n-table class="data-table" striped size="small" :single-line="false">
            <thead><tr><th>股票</th><th>收益</th><th>波动</th><th>成交量</th><th>成交额</th><th>平均振幅</th><th>最新收盘价</th></tr></thead>
            <tbody>
              <tr v-for="item in crossSectionPager.pagedRows.value" :key="item.stock_code">
                <td>{{ item.stock_code }}{{ item.stock_name ? ` · ${item.stock_name}` : "" }}</td>
                <td>{{ formatPercent(item.total_return, 2) }}</td>
                <td>{{ formatPercent(item.volatility, 2) }}</td>
                <td>{{ formatCompact(item.total_volume, 2) }}</td>
                <td>{{ formatCompact(item.total_amount, 2) }}</td>
                <td>{{ formatNumberish(item.average_amplitude, 4) }}</td>
                <td>{{ formatNumberish(item.latest_close, 2) }}</td>
              </tr>
            </tbody>
          </n-table>
          <div class="table-pagination">
            <n-pagination
              :page="crossSectionPager.page.value"
              :page-size="crossSectionPager.pageSize.value"
              :item-count="crossSectionPager.total.value"
              :page-sizes="crossSectionPager.pageSizes"
              show-size-picker
              @update:page="crossSectionPager.setPage"
              @update:page-size="crossSectionPager.setPageSize"
            />
          </div>
        </div>
        <EmptyState v-else title="暂无横截面对比结果" description="执行分析后，这里会展示当前批次内的横截面排序" />
      </PanelCard>
    </section>

    <section v-if="!isMarketSection" class="page__grid page__grid--double">
      <PanelCard title="数据质量">
        <n-alert v-if="panelNotices.quality" type="warning" :show-icon="true">{{ panelNotices.quality }}</n-alert>
        <div v-else-if="quality" class="detail-grid">
          <div class="detail-grid__item"><span class="detail-grid__label">覆盖</span><div class="detail-grid__value">{{ formatPercent(quality.coverage_ratio, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">缺失交易</span><div class="detail-grid__value">{{ quality.missing_trade_date_count }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">无效 OHLC</span><div class="detail-grid__value">{{ quality.invalid_ohlc_count }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">非正价格</span><div class="detail-grid__value">{{ quality.non_positive_price_count }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">非正成交</span><div class="detail-grid__value">{{ quality.non_positive_volume_count }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">平盘日数</span><div class="detail-grid__value">{{ quality.flat_days_count }}</div></div>
        </div>
        <div v-if="quality?.missing_trade_dates.length" class="inline-hint" style="margin-top: 12px;">缺失交易日：{{ quality.missing_trade_dates.join("、") }}</div>
        <div v-if="quality" class="inline-hint" style="margin-top: 8px;">{{ formatModuleSummary(quality) }}</div>
        <EmptyState v-else title="暂无质量报告" description="执行分析后，这里会返回当前范围的数据质量诊断" />
      </PanelCard>

      <PanelCard title="估值与基本面快照">
        <n-alert v-if="panelNotices.snapshot" type="warning" :show-icon="true">{{ panelNotices.snapshot }}</n-alert>
        <n-alert v-else-if="snapshot?.missing_fields.length" type="warning" :show-icon="true" style="margin-bottom: 12px;">
          当前批次缺少快照字段：{{ snapshot.missing_fields.join("、") }}
        </n-alert>
        <div v-else-if="snapshotHasValues" class="detail-grid">
          <div class="detail-grid__item"><span class="detail-grid__label">PE(TTM)</span><div class="detail-grid__value">{{ formatNumberish(snapshot?.pe_ttm ?? null, 4) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">PB</span><div class="detail-grid__value">{{ formatNumberish(snapshot?.pb ?? null, 4) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">ROE</span><div class="detail-grid__value">{{ formatPercent(snapshot?.roe ?? null, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">资产负债率</span><div class="detail-grid__value">{{ formatPercent(snapshot?.asset_liability_ratio ?? null, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">营收同比</span><div class="detail-grid__value">{{ formatPercent(snapshot?.revenue_yoy ?? null, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">净利同比</span><div class="detail-grid__value">{{ formatPercent(snapshot?.net_profit_yoy ?? null, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">估值时间</span><div class="detail-grid__value">{{ snapshot?.valuation_as_of || "--" }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">报告期</span><div class="detail-grid__value">{{ snapshot?.fundamental_report_date || "--" }}</div></div>
        </div>
        <div v-if="snapshot" class="inline-hint" style="margin-top: 8px;">{{ formatModuleSummary(snapshot) }}</div>
        <EmptyState v-else title="暂无快照结果" description="当前上传链路未提供快照字段时，这里会明确提示缺少哪些数据" />
      </PanelCard>
    </section>

    <section v-if="!isMarketSection" class="page__grid page__grid--double">
      <PanelCard title="横截面对比">
        <n-alert v-if="panelNotices.crossSection" type="warning" :show-icon="true">{{ panelNotices.crossSection }}</n-alert>
      <div v-else-if="crossSectionPager.total.value" class="data-table-wrap">
          <n-table class="data-table" striped size="small" :single-line="false">
            <thead><tr><th>股票</th><th>收益</th><th>波动</th><th>成交量</th><th>成交额</th><th>平均振幅</th><th>最新收盘价</th></tr></thead>
            <tbody>
              <tr v-for="item in crossSectionPager.pagedRows.value" :key="item.stock_code">
                <td>{{ item.stock_code }}{{ item.stock_name ? ` · ${item.stock_name}` : "" }}</td>
                <td>{{ formatPercent(item.total_return, 2) }}</td>
                <td>{{ formatPercent(item.volatility, 2) }}</td>
                <td>{{ formatCompact(item.total_volume, 2) }}</td>
                <td>{{ formatCompact(item.total_amount, 2) }}</td>
                <td>{{ formatNumberish(item.average_amplitude, 4) }}</td>
                <td>{{ formatNumberish(item.latest_close, 2) }}</td>
              </tr>
            </tbody>
          </n-table>
          <div class="table-pagination">
            <n-pagination
              :page="crossSectionPager.page.value"
              :page-size="crossSectionPager.pageSize.value"
              :item-count="crossSectionPager.total.value"
              :page-sizes="crossSectionPager.pageSizes"
              show-size-picker
              @update:page="crossSectionPager.setPage"
              @update:page-size="crossSectionPager.setPageSize"
            />
          </div>
        </div>
        <div v-if="crossSection" class="inline-hint" style="margin-top: 8px;">{{ formatModuleSummary(crossSection) }}</div>
        <EmptyState v-else title="暂无横截面对比结果" description="执行分析后，这里会展示当前批次内的横截面排序" />
      </PanelCard>

      <PanelCard title="相关性矩阵">
        <n-alert v-if="panelNotices.correlation" type="warning" :show-icon="true">{{ panelNotices.correlation }}</n-alert>
        <div v-else-if="correlationRows.length" class="data-table-wrap">
          <n-table class="data-table" striped size="small" :single-line="false">
          <thead><tr><th>股票</th><th v-for="code in correlation?.stock_codes" :key="code">{{ code }}</th></tr></thead>
          <tbody>
            <tr v-for="row in correlationRows" :key="row.stock_code">
              <td>{{ row.stock_code }}</td>
              <td v-for="cell in row.values" :key="cell.key">{{ cell.value === null ? "--" : formatNumberish(Number(cell.value), 4) }}</td>
            </tr>
          </tbody>
        </n-table>
      </div>
        <div v-if="correlation" class="inline-hint" style="margin-top: 8px;">{{ formatModuleSummary(correlation) }}</div>
        <EmptyState v-else title="暂无相关性结果" description="执行分析后，这里会展示当前所选股票的收益率相关性矩阵" />
      </PanelCard>
    </section>

    <PanelCard v-if="!isMarketSection" title="范围对比">
      <n-alert v-if="panelNotices.comparison" type="warning" :show-icon="true">{{ panelNotices.comparison }}</n-alert>
      <div v-else-if="comparison" class="page__grid page__grid--double">
        <div>
          <div class="section-label">基线范围</div>
          <div class="detail-grid">
            <div class="detail-grid__item"><span class="detail-grid__label">批次</span><div class="detail-grid__value">{{ formatRunLabel(comparison.base_scope.import_run_id) }}</div></div>
            <div class="detail-grid__item"><span class="detail-grid__label">股票</span><div class="detail-grid__value">{{ comparison.base_scope.stock_code || "全部股票" }}</div></div>
            <div class="detail-grid__item"><span class="detail-grid__label">请求范围</span><div class="detail-grid__value">{{ comparison.base_scope.requested_start_date || "起始不限" }} ~ {{ comparison.base_scope.requested_end_date || "结束不限" }}</div></div>
            <div class="detail-grid__item"><span class="detail-grid__label">实际范围</span><div class="detail-grid__value">{{ comparison.base_scope.actual_start_date }} ~ {{ comparison.base_scope.actual_end_date }}</div></div>
          </div>
        </div>
        <div>
          <div class="section-label">对比范围</div>
          <div class="detail-grid">
            <div class="detail-grid__item"><span class="detail-grid__label">批次</span><div class="detail-grid__value">{{ formatRunLabel(comparison.target_scope.import_run_id) }}</div></div>
            <div class="detail-grid__item"><span class="detail-grid__label">股票</span><div class="detail-grid__value">{{ comparison.target_scope.stock_code || "全部股票" }}</div></div>
            <div class="detail-grid__item"><span class="detail-grid__label">请求范围</span><div class="detail-grid__value">{{ comparison.target_scope.requested_start_date || "起始不限" }} ~ {{ comparison.target_scope.requested_end_date || "结束不限" }}</div></div>
            <div class="detail-grid__item"><span class="detail-grid__label">实际范围</span><div class="detail-grid__value">{{ comparison.target_scope.actual_start_date }} ~ {{ comparison.target_scope.actual_end_date }}</div></div>
          </div>
        </div>
      </div>

      <div v-if="comparison" style="margin-top: 18px;" class="page__grid page__grid--double">
        <div class="data-table-wrap">
          <n-table class="data-table" striped size="small" :single-line="false">
            <thead><tr><th>字段</th><th>差异条数</th></tr></thead>
            <tbody><tr v-for="item in comparisonMismatchRows" :key="item[0]"><td>{{ item[0] }}</td><td>{{ item[1] }}</td></tr></tbody>
          </n-table>
        </div>
        <div class="detail-grid">
          <div class="detail-grid__item"><span class="detail-grid__label">共同股票</span><div class="detail-grid__value">{{ comparison.stock_overlap.shared_stocks.length }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">共同交易日数</span><div class="detail-grid__value">{{ comparison.record_overlap.shared_trade_date_count }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">共同记录</span><div class="detail-grid__value">{{ comparison.record_overlap.shared_record_count }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">差异记录</span><div class="detail-grid__value">{{ comparison.mismatch_summary.mismatched_record_count }}</div></div>
        </div>
      </div>

      <div v-if="mismatchSamplePager.total.value" style="margin-top: 18px;" class="data-table-wrap">
        <n-table class="data-table" striped size="small" :single-line="false">
          <thead><tr><th>股票</th><th>日期</th><th>差异字段</th><th>基线</th><th>对比</th></tr></thead>
          <tbody>
            <tr v-for="item in mismatchSamplePager.pagedRows.value" :key="`${item.stock_code}-${item.trade_date}`">
              <td>{{ item.stock_code }}</td>
              <td>{{ formatDate(item.trade_date) }}</td>
              <td>{{ item.mismatched_fields.join("、") }}</td>
              <td class="mono">开(O) {{ formatNumberish(item.base_values.open, 2) }} / 高(H) {{ formatNumberish(item.base_values.high, 2) }} / 收(C) {{ formatNumberish(item.base_values.close, 2) }}</td>
              <td class="mono">开(O) {{ formatNumberish(item.target_values.open, 2) }} / 高(H) {{ formatNumberish(item.target_values.high, 2) }} / 收(C) {{ formatNumberish(item.target_values.close, 2) }}</td>
            </tr>
          </tbody>
        </n-table>
        <div class="table-pagination">
          <n-pagination
            :page="mismatchSamplePager.page.value"
            :page-size="mismatchSamplePager.pageSize.value"
            :item-count="mismatchSamplePager.total.value"
            :page-sizes="mismatchSamplePager.pageSizes"
            show-size-picker
            @update:page="mismatchSamplePager.setPage"
            @update:page-size="mismatchSamplePager.setPageSize"
          />
        </div>
      </div>
      <EmptyState v-else-if="!comparison" title="暂无范围对比结果" description="执行分析后，这里会展示基线范围和对比范围的差异" />
    </PanelCard>
  </div>
</template>


