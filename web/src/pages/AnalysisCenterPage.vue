<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";

import type { EChartsOption } from "echarts";
import { NAlert, NButton, NDatePicker, NForm, NFormItemGi, NGrid, NInput, NPagination, NSelect, NTable, NTag, useMessage } from "naive-ui";
import { useRoute } from "vue-router";

import {
  fetchTradingAnomalies,
  fetchTradingCorrelation,
  fetchTradingCrossSection,
  fetchTradingIndicators,
  fetchTradingQuality,
  fetchTradingRisk,
  fetchTradingSnapshot,
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
  TradingStockRead,
  TradingSummaryRead,
} from "@/api/types";
import EChartPanel from "@/components/EChartPanel.vue";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import { useTablePager } from "@/composables/useTablePager";
import { useDatasetContextStore } from "@/stores/datasetContext";
import { useRuntimeStore } from "@/stores/runtime";
import { formatCompact, formatDate, formatNumberish, formatPercent, getErrorMessage, toNumber, toStatusTagType } from "@/utils/format";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";
import { formatAnomalyDescriptionText, formatAnomalyTypeText, formatSeverityText, TECHNICAL_TEXT } from "@/utils/displayText";


const ANALYSIS_SECTION_TABS = [
  {
    key: "market",
    label: "金融分析",
  },
  {
    key: "governance",
    label: "快照与相关性",
  },
] as const;

const runtime = useRuntimeStore();
const datasetContext = useDatasetContextStore();
const route = useRoute();
const message = useMessage();
const loadingRuns = ref(false);
const loadingAnalysis = ref(false);
const error = ref("");
usePageErrorNotification(error, "分析中心加载失败");

const importRuns = ref<ImportRunRead[]>([]);
const stocks = ref<TradingStockRead[]>([]);

const filters = reactive({
  importRunId: undefined as number | undefined,
  stockCode: "",
  startDate: "",
  endDate: "",
  crossMetric: "total_return",
  topNInput: "10",
  correlationStockCodes: [] as string[],
});

const startDatePickerValue = computed({
  get: () => filters.startDate || undefined,
  set: (value: string | null | undefined) => {
    filters.startDate = value ?? "";
  },
});
const endDatePickerValue = computed({
  get: () => filters.endDate || undefined,
  set: (value: string | null | undefined) => {
    filters.endDate = value ?? "";
  },
});
const summary = ref<TradingSummaryRead | null>(null);
const quality = ref<TradingQualityReportRead | null>(null);
const indicators = ref<TradingIndicatorSeriesRead | null>(null);
const risk = ref<TradingRiskMetricsRead | null>(null);
const snapshot = ref<TradingSnapshotRead | null>(null);
const anomalies = ref<TradingAnomalyReportRead | null>(null);
const crossSection = ref<TradingCrossSectionRead | null>(null);
const correlation = ref<TradingCorrelationMatrixRead | null>(null);
const panelNotices = reactive({
  summary: "",
  quality: "",
  indicators: "",
  risk: "",
  snapshot: "",
  anomalies: "",
  crossSection: "",
  correlation: "",
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
const currentSection = computed<(typeof ANALYSIS_SECTION_TABS)[number]["key"]>(() =>
  route.path.startsWith("/analysis/governance") ? "governance" : "market"
);
const isMarketSection = computed(() => currentSection.value === "market");

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
const anomalyRows = computed(() => anomalies.value?.anomalies ?? []);
const crossSectionRows = computed(() => crossSection.value?.rows ?? []);
const analysisScopeKey = computed(
  () =>
    [
      filters.importRunId ?? "",
      filters.stockCode,
      filters.startDate,
      filters.endDate,
      filters.crossMetric,
      filters.topNInput,
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
    crossMetric: filters.crossMetric,
    topNInput: filters.topNInput,
    correlationStockCodes: filters.correlationStockCodes,
  });
}

function syncFiltersFromContext() {
  filters.importRunId = datasetContext.state.importRunId;
  filters.stockCode = datasetContext.state.stockCode;
  filters.startDate = datasetContext.state.startDate;
  filters.endDate = datasetContext.state.endDate;
  filters.crossMetric = datasetContext.state.crossMetric;
  filters.topNInput = datasetContext.state.topNInput;
  filters.correlationStockCodes = [...datasetContext.state.correlationStockCodes];
}

async function loadStocks() {
  if (!filters.importRunId) {
    stocks.value = [];
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
  } catch (err) {
    error.value = getErrorMessage(err);
    stocks.value = [];
    filters.stockCode = "";
  }
}

async function loadRuns(preferredRunId?: number) {
  loadingRuns.value = true;
  error.value = "";
  try {
    const statsResponse = await fetchImportStats();
    importRuns.value = await fetchImportRuns({ limit: Math.max(statsResponse.total_runs, 1) });
    filters.importRunId = pickVisibleRunId(importRuns.value, [preferredRunId, filters.importRunId, datasetContext.state.importRunId]);
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

async function applyFilters(options: { notify?: boolean } = {}) {
  if (!filters.importRunId || !filters.stockCode) {
    if (options.notify) {
      message.warning("请先选择批次和股票");
    }
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
    ]);

    summary.value = resolveAnalysisPanelResult(results[0], "summary", "基础摘要");
    quality.value = resolveAnalysisPanelResult(results[1], "quality", "数据质量");
    indicators.value = resolveAnalysisPanelResult(results[2], "indicators", "价格走势与技术信号");
    risk.value = resolveAnalysisPanelResult(results[3], "risk", "风险指标");
    snapshot.value = resolveAnalysisPanelResult(results[4], "snapshot", "估值与基本面快照");
    anomalies.value = resolveAnalysisPanelResult(results[5], "anomalies", "异常检测");
    crossSection.value = resolveAnalysisPanelResult(results[6], "crossSection", "横截面对比");
    correlation.value = resolveAnalysisPanelResult(results[7], "correlation", "相关性矩阵");

    if (results.some((item) => item.status === "rejected")) {
      error.value = "部分分析面板加载失败，请查看对应卡片中的提示";
      if (options.notify) {
        message.warning("部分分析面板加载失败，请查看卡片提示");
      }
    } else if (options.notify) {
      message.success("分析已完成");
    }

    runtime.markSynced();
  } catch (err) {
    error.value = getErrorMessage(err);
    if (options.notify) {
      message.error(error.value);
    }
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
}

onMounted(() => {
  syncFiltersFromContext();
  void loadRuns(filters.importRunId);
});

watch(
  () => datasetContext.state.appliedRevision,
  () => {
    syncFiltersFromContext();
    void loadRuns(filters.importRunId);
  }
);
</script>

<template>
  <div class="page">
    <section v-if="isMarketSection" class="page__grid">
      <PanelCard title="基础摘要">
        <n-alert v-if="panelNotices.summary" type="warning" :show-icon="true">{{ panelNotices.summary }}</n-alert>
        <div v-else-if="summary" class="detail-grid">
          <div class="detail-grid__item"><span class="detail-grid__label">股票</span><div class="detail-grid__value">{{ summary.stock_code }}{{ summary.stock_name ? ` · ${summary.stock_name}` : "" }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">时间范围</span><div class="detail-grid__value">{{ formatDate(summary.start_date) }} ~ {{ formatDate(summary.end_date) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">记录</span><div class="detail-grid__value">{{ summary.record_count }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">最新收盘</span><div class="detail-grid__value">{{ formatNumberish(summary.latest_close, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">平均收盘</span><div class="detail-grid__value">{{ formatNumberish(summary.average_close, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">总成交额</span><div class="detail-grid__value">{{ formatCompact(summary.total_amount, 2) }}</div></div>
        </div>
        <div v-if="summary" class="inline-hint" style="margin-top: 8px;">{{ formatModuleSummary(summary) }}</div>
        <EmptyState v-else title="暂无基础摘要" description="执行分析后，这里会展示当前主范围的基础统计" />
      </PanelCard>
    </section>

    <section v-if="isMarketSection" class="page__grid page__grid--double">
      <PanelCard title="价格走势与技术信号">
        <n-alert v-if="panelNotices.indicators" type="warning" :show-icon="true">{{ panelNotices.indicators }}</n-alert>
        <n-alert v-else-if="indicators?.notices?.length" type="warning" :show-icon="true" style="margin-bottom: 12px;">
          {{ indicators.notices.join(" ") }}
        </n-alert>
        <EChartPanel v-else-if="indicatorChartOption" :option="indicatorChartOption" :loading="loadingAnalysis" />
        <EmptyState v-else title="暂无走势结果" description="选择主股票并执行分析后，这里会展示价格走势和技术信号" />
        <div v-if="latestIndicatorPoint" class="detail-grid" style="margin-top: 16px;">
          <div class="detail-grid__item"><span class="detail-grid__label">最新日期</span><div class="detail-grid__value">{{ formatDate(latestIndicatorPoint.trade_date) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">{{ TECHNICAL_TEXT.macd }}</span><div class="detail-grid__value">{{ formatNumberish(latestIndicatorPoint.macd, 4) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">{{ TECHNICAL_TEXT.rsi14 }}</span><div class="detail-grid__value">{{ formatNumberish(latestIndicatorPoint.rsi14, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">{{ TECHNICAL_TEXT.atr14 }}</span><div class="detail-grid__value">{{ formatNumberish(latestIndicatorPoint.atr14, 4) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">Bias20</span><div class="detail-grid__value">{{ formatPercent(latestIndicatorPoint.bias20, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">ROC20</span><div class="detail-grid__value">{{ formatPercent(latestIndicatorPoint.roc20, 2) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">NATR14</span><div class="detail-grid__value">{{ formatPercent(latestIndicatorPoint.natr14, 2) }}</div></div>
        </div>
        <div v-if="indicators" class="inline-hint" style="margin-top: 8px;">{{ formatModuleSummary(indicators) }}</div>
      </PanelCard>

      <PanelCard title="风险指标">
        <n-alert v-if="panelNotices.risk" type="warning" :show-icon="true">{{ panelNotices.risk }}</n-alert>
        <n-alert v-if="risk?.notices?.length" type="warning" :show-icon="true" style="margin-bottom: 12px;">
          {{ risk.notices.join(" ") }}
        </n-alert>
        <div v-if="risk" class="detail-grid">
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

    <section v-if="isMarketSection">
      <PanelCard title="异常检测">
        <n-alert v-if="panelNotices.anomalies" type="warning" :show-icon="true">{{ panelNotices.anomalies }}</n-alert>
      <div v-else-if="anomalyPager.total.value" class="data-table-wrap analysis-pair-table-wrap anomaly-table-wrap">
          <n-table class="data-table anomaly-table" striped size="small" :single-line="false">
            <colgroup>
              <col class="anomaly-table__date" />
              <col class="anomaly-table__type" />
              <col class="anomaly-table__severity" />
              <col class="anomaly-table__number" />
              <col class="anomaly-table__number" />
              <col class="anomaly-table__number" />
              <col class="anomaly-table__description" />
            </colgroup>
            <thead><tr><th>日期</th><th>类型</th><th>严重</th><th>指标</th><th>基线</th><th>阈值</th><th>说明</th></tr></thead>
            <tbody>
              <tr v-for="item in anomalyPager.pagedRows.value" :key="`${item.trade_date}-${item.anomaly_type}`">
                <td>{{ formatDate(item.trade_date) }}</td>
                <td>{{ formatAnomalyTypeText(item.anomaly_type) }}</td>
                <td><n-tag :type="toStatusTagType(item.severity)" round size="small">{{ formatSeverityText(item.severity) }}</n-tag></td>
                <td>{{ formatNumberish(item.metric_value, 4) }}</td>
                <td>{{ formatNumberish(item.baseline_value, 4) }}</td>
                <td>{{ formatNumberish(item.threshold_value, 4) }}</td>
                <td class="anomaly-table__description-cell">{{ formatAnomalyDescriptionText(item.description) }}</td>
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
    </section>

    <section v-if="isMarketSection">
      <PanelCard title="横截面对比">
        <n-alert v-if="panelNotices.crossSection" type="warning" :show-icon="true">{{ panelNotices.crossSection }}</n-alert>
      <div v-else-if="crossSectionPager.total.value" class="data-table-wrap analysis-pair-table-wrap">
          <n-table class="data-table cross-section-table" striped size="small" :single-line="false">
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
        <n-alert v-if="snapshot?.missing_fields.length" type="warning" :show-icon="true" style="margin-bottom: 12px;">
          当前批次缺少快照有效数据：{{ snapshot.missing_fields.join("、") }}
        </n-alert>
        <div v-if="snapshotHasValues" class="detail-grid">
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

  </div>
</template>

<style scoped>
.analysis-pair-table-wrap {
  height: min(48vh, 420px);
  min-height: 360px;
  max-height: 420px;
}

.anomaly-table,
.cross-section-table {
  min-width: 860px;
  table-layout: fixed;
}

.anomaly-table :deep(th),
.anomaly-table :deep(td),
.cross-section-table :deep(th),
.cross-section-table :deep(td) {
  padding: 10px 14px;
  vertical-align: middle;
}

.anomaly-table__date {
  width: 110px;
}

.anomaly-table__type {
  width: 150px;
}

.anomaly-table__severity {
  width: 88px;
}

.anomaly-table__number {
  width: 118px;
}

.anomaly-table__description {
  width: 260px;
}

.anomaly-table__description-cell {
  line-height: 1.5;
  word-break: normal;
  overflow-wrap: break-word;
}
</style>
