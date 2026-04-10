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
  fetchTradingRunComparison,
  fetchTradingSummary,
} from "@/api/analysis";
import { fetchImportRuns } from "@/api/imports";
import { fetchTradingInstruments } from "@/api/trading";
import type {
  ImportRunRead,
  TradingAnomalyReportRead,
  TradingCorrelationMatrixRead,
  TradingCrossSectionRead,
  TradingIndicatorPointRead,
  TradingIndicatorSeriesRead,
  TradingInstrumentRead,
  TradingJointAnomalyRankingRead,
  TradingQualityReportRead,
  TradingRiskMetricsRead,
  TradingRunComparisonRead,
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
  toNumber,
  toStatusTagType,
} from "@/utils/format";


const runtime = useRuntimeStore();
const loadingRuns = ref(false);
const loadingAnalysis = ref(false);
const error = ref("");
const importRuns = ref<ImportRunRead[]>([]);
const instruments = ref<TradingInstrumentRead[]>([]);

const summary = ref<TradingSummaryRead | null>(null);
const quality = ref<TradingQualityReportRead | null>(null);
const indicators = ref<TradingIndicatorSeriesRead | null>(null);
const risk = ref<TradingRiskMetricsRead | null>(null);
const anomalies = ref<TradingAnomalyReportRead | null>(null);
const jointAnomalies = ref<TradingJointAnomalyRankingRead | null>(null);
const crossSection = ref<TradingCrossSectionRead | null>(null);
const correlation = ref<TradingCorrelationMatrixRead | null>(null);
const comparison = ref<TradingRunComparisonRead | null>(null);
const importRunDisplayIdMap = computed(() => new Map(importRuns.value.map((item) => [item.id, item.display_id])));

const queryForm = reactive({
  importRunId: undefined as number | undefined,
  instrumentCode: "",
  startDate: "",
  endDate: "",
  crossMetric: "total_return",
  topNInput: "10",
  compareRunId: undefined as number | undefined,
  correlationInstrumentCodes: [] as string[],
});

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
    hint: summary.value ? `${formatDate(summary.value.end_date)} 收盘价` : "等待分析结果",
    tone: "teal" as const,
  },
  {
    label: "Interval Return",
    value: risk.value ? formatPercent(risk.value.interval_return, 2) : "--",
    hint: risk.value ? `${risk.value.record_count} 条记录` : "等待分析结果",
    tone: "orange" as const,
  },
  {
    label: "Max Drawdown",
    value: risk.value ? formatPercent(risk.value.max_drawdown, 2) : "--",
    hint: risk.value ? `持续 ${risk.value.max_drawdown_duration} 天` : "等待分析结果",
    tone: "berry" as const,
  },
  {
    label: "Anomalies",
    value: String(anomalies.value?.anomalies.length ?? 0),
    hint: quality.value ? `覆盖率 ${formatPercent(quality.value.coverage_ratio, 2)}` : "等待分析结果",
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

const jointAnomalyRows = computed(() => jointAnomalies.value?.rows ?? []);

function parseTopN() {
  const normalized = queryForm.topNInput.trim();
  if (!normalized) {
    return undefined;
  }

  const parsed = Number(normalized);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error("Top N 必须是正整数，留空则返回全部结果。");
  }
  return parsed;
}

function buildScopeParams() {
  if (!queryForm.importRunId || !queryForm.instrumentCode) {
    throw new Error("请先选择批次和标的。");
  }

  return {
    import_run_id: queryForm.importRunId,
    instrument_code: queryForm.instrumentCode,
    start_date: queryForm.startDate || undefined,
    end_date: queryForm.endDate || undefined,
  };
}

function defaultCorrelationCodes(rows: TradingInstrumentRead[]) {
  return rows.slice(0, 6).map((item) => item.instrument_code);
}

function formatImportRunDisplayLabel(runId: number | null | undefined) {
  if (!runId) {
    return "--";
  }
  const displayId = importRunDisplayIdMap.value.get(runId);
  return `#${displayId ?? runId}`;
}

async function loadRuns(preferredRunId?: number) {
  loadingRuns.value = true;
  error.value = "";
  try {
    const rows = await fetchImportRuns({ limit: 50 });
    importRuns.value = rows;
    if (!rows.length) {
      queryForm.importRunId = undefined;
      queryForm.compareRunId = undefined;
      instruments.value = [];
      clearAnalysisResults();
      return;
    }

    const fallbackRunId = preferredRunId && rows.some((row) => row.id === preferredRunId) ? preferredRunId : rows[0].id;
    queryForm.importRunId = fallbackRunId;

    const compareCandidate = rows.find((row) => row.id !== fallbackRunId)?.id ?? fallbackRunId;
    queryForm.compareRunId = compareCandidate;
    await loadInstruments();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loadingRuns.value = false;
  }
}

async function loadInstruments() {
  if (!queryForm.importRunId) {
    instruments.value = [];
    queryForm.instrumentCode = "";
    clearAnalysisResults();
    return;
  }

  try {
    const rows = await fetchTradingInstruments(queryForm.importRunId);
    instruments.value = rows;
    if (!rows.length) {
      queryForm.instrumentCode = "";
      queryForm.correlationInstrumentCodes = [];
      clearAnalysisResults();
      return;
    }

    if (!rows.some((row) => row.instrument_code === queryForm.instrumentCode)) {
      queryForm.instrumentCode = rows[0].instrument_code;
    }

    const validCorrelationCodes = queryForm.correlationInstrumentCodes.filter((code) =>
      rows.some((item) => item.instrument_code === code)
    );
    queryForm.correlationInstrumentCodes = validCorrelationCodes.length
      ? validCorrelationCodes
      : defaultCorrelationCodes(rows);
    await loadAnalysis();
  } catch (err) {
    error.value = getErrorMessage(err);
  }
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
}

async function loadAnalysis() {
  if (!queryForm.importRunId || !queryForm.instrumentCode) {
    clearAnalysisResults();
    return;
  }

  loadingAnalysis.value = true;
  error.value = "";
  try {
    const scopeParams = buildScopeParams();
    const topN = parseTopN();
    const correlationCodes = queryForm.correlationInstrumentCodes.length
      ? queryForm.correlationInstrumentCodes.join(",")
      : undefined;

    const [summaryResponse, qualityResponse, indicatorResponse, riskResponse, anomalyResponse, jointAnomalyResponse, crossSectionResponse, correlationResponse, comparisonResponse] =
      await Promise.all([
        fetchTradingSummary(scopeParams),
        fetchTradingQuality(scopeParams),
        fetchTradingIndicators(scopeParams),
        fetchTradingRisk(scopeParams),
        fetchTradingAnomalies(scopeParams),
        fetchTradingJointAnomalyRanking({
          import_run_id: queryForm.importRunId,
          start_date: queryForm.startDate || undefined,
          end_date: queryForm.endDate || undefined,
          top_n: topN,
        }),
        fetchTradingCrossSection({
          import_run_id: queryForm.importRunId,
          start_date: queryForm.startDate || undefined,
          end_date: queryForm.endDate || undefined,
          metric: queryForm.crossMetric,
          top_n: topN,
        }),
        fetchTradingCorrelation({
          import_run_id: queryForm.importRunId,
          start_date: queryForm.startDate || undefined,
          end_date: queryForm.endDate || undefined,
          instrument_codes: correlationCodes,
        }),
        fetchTradingRunComparison({
          base_run_id: queryForm.importRunId,
          target_run_id: queryForm.compareRunId || queryForm.importRunId,
        }),
      ]);

    summary.value = summaryResponse;
    quality.value = qualityResponse;
    indicators.value = indicatorResponse;
    risk.value = riskResponse;
    anomalies.value = anomalyResponse;
    jointAnomalies.value = jointAnomalyResponse;
    crossSection.value = crossSectionResponse;
    correlation.value = correlationResponse;
    comparison.value = comparisonResponse;
    runtime.markSynced();
  } catch (err) {
    error.value = getErrorMessage(err);
    clearAnalysisResults();
  } finally {
    loadingAnalysis.value = false;
  }
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
          在当前导入批次内，对选定标的执行指标、风险、异常、横截面、相关性、数据质量和批次对比分析。
        </p>
      </div>
      <div class="page__actions">
        <el-button type="primary" :loading="loadingAnalysis" @click="loadAnalysis">刷新分析</el-button>
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

    <PanelCard title="分析筛选器" description="所有分析都在当前导入批次的可见范围内执行。">
      <div class="analysis-filters">
        <el-select
          v-model="queryForm.importRunId"
          placeholder="选择批次"
          filterable
          class="analysis-filters__control"
          @change="loadInstruments"
        >
          <el-option
            v-for="item in importRuns"
            :key="item.id"
            :label="`#${item.display_id} - ${item.dataset_name}`"
            :value="item.id"
          />
        </el-select>

        <el-select
          v-model="queryForm.instrumentCode"
          placeholder="选择标的"
          filterable
          class="analysis-filters__control"
          @change="loadAnalysis"
        >
          <el-option
            v-for="item in instruments"
            :key="item.instrument_code"
            :label="`${item.instrument_code}${item.instrument_name ? ` · ${item.instrument_name}` : ''}`"
            :value="item.instrument_code"
          />
        </el-select>

        <el-date-picker
          v-model="queryForm.startDate"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="开始日期"
          class="analysis-filters__control"
        />

        <el-date-picker
          v-model="queryForm.endDate"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="结束日期"
          class="analysis-filters__control"
        />

        <el-select
          v-model="queryForm.crossMetric"
          placeholder="横截面指标"
          class="analysis-filters__control"
          @change="loadAnalysis"
        >
          <el-option
            v-for="item in crossMetricOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>

        <el-input
          v-model="queryForm.topNInput"
          placeholder="Top N"
          class="analysis-filters__control"
          @change="loadAnalysis"
        />

        <el-select
          v-model="queryForm.compareRunId"
          placeholder="对比批次"
          filterable
          class="analysis-filters__control"
          @change="loadAnalysis"
        >
          <el-option
            v-for="item in importRuns"
            :key="`compare-${item.id}`"
            :label="`#${item.display_id} - ${item.dataset_name}`"
            :value="item.id"
          />
        </el-select>

        <el-select
          v-model="queryForm.correlationInstrumentCodes"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="相关性标的"
          class="analysis-filters__control analysis-filters__control--wide"
          @change="loadAnalysis"
        >
          <el-option
            v-for="item in instruments"
            :key="`corr-${item.instrument_code}`"
            :label="`${item.instrument_code}${item.instrument_name ? ` · ${item.instrument_name}` : ''}`"
            :value="item.instrument_code"
          />
        </el-select>
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
        title="暂无摘要"
        description="选择一个有数据的批次和标的后，这里会展示区间摘要。"
      />
    </PanelCard>

    <PanelCard title="指标" description="含收益率、均线、EMA、MACD、RSI、Bollinger、ATR。">
      <template #actions>
        <span v-if="latestIndicatorPoint" class="pill">最新点 {{ latestIndicatorPoint.trade_date }}</span>
      </template>

      <div v-if="indicators?.points.length" class="analysis-stack">
        <EChartPanel :option="indicatorChartOption" :loading="loadingAnalysis" height="360px" />

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
        title="暂无指标数据"
        description="当筛选区间内存在行情记录时，这里会展示指标走势与最新值。"
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
        title="暂无风险结果"
        description="完成分析后，这里会展示波动率、最大回撤、上涨日占比等指标。"
      />
    </PanelCard>

    <PanelCard title="异常" description="全部采用可解释规则：放量、收益率异动、振幅异动、突破前高/前低。">
      <el-table v-if="anomalies?.anomalies.length" :data="anomalies.anomalies" stripe>
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
        title="未检测到异常"
        description="如果没有满足规则阈值的记录，这里会保持空状态。"
      />
    </PanelCard>

    <PanelCard title="横截面 / 相关性" description="支持批次内多标的排序与收益率相关性矩阵。">
      <div class="analysis-stack">
        <div>
          <div class="analysis-subtitle">横截面排序</div>
          <el-table v-if="crossSection?.rows.length" :data="crossSection.rows" stripe>
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
            title="暂无横截面结果"
            description="这里会展示同一批次内多标的的区间排序结果。"
          />
        </div>

        <div>
          <div class="analysis-subtitle">相关性矩阵</div>
          <el-table v-if="correlationTableRows.length" :data="correlationTableRows" stripe>
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
            title="暂无相关性结果"
            description="相关性需要至少两个标的且存在重叠收益率样本。"
          />
        </div>
      </div>
    </PanelCard>

    <PanelCard title="数据质量 / 批次对比" description="用于支撑系统的数据管理能力，而不仅是单点算法查询。">
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
              {{ quality.non_positive_amount_count }}
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
        </div>

        <div>
          <div class="analysis-subtitle">批次对比</div>
          <el-descriptions v-if="comparison" :column="2" border>
            <el-descriptions-item label="Base ID">{{ formatImportRunDisplayLabel(comparison.base_run_id) }}</el-descriptions-item>
            <el-descriptions-item label="Target ID">{{ formatImportRunDisplayLabel(comparison.target_run_id) }}</el-descriptions-item>
            <el-descriptions-item label="Base Records">{{ comparison.base_record_count }}</el-descriptions-item>
            <el-descriptions-item label="Target Records">{{ comparison.target_record_count }}</el-descriptions-item>
            <el-descriptions-item label="Base Instruments">{{ comparison.base_instrument_count }}</el-descriptions-item>
            <el-descriptions-item label="Target Instruments">{{ comparison.target_instrument_count }}</el-descriptions-item>
            <el-descriptions-item label="Base Amount">
              {{ formatCompact(comparison.base_total_amount, 2) }}
            </el-descriptions-item>
            <el-descriptions-item label="Target Amount">
              {{ formatCompact(comparison.target_total_amount, 2) }}
            </el-descriptions-item>
          </el-descriptions>

          <div v-if="comparison" class="analysis-compare">
            <div>
              <div class="analysis-compare__label">Shared Instruments</div>
              <div class="analysis-tags">
                <span v-for="item in comparison.shared_instruments" :key="`shared-${item}`" class="pill">{{ item }}</span>
              </div>
            </div>
            <div>
              <div class="analysis-compare__label">Added In Target</div>
              <div class="analysis-tags">
                <span v-for="item in comparison.added_instruments" :key="`added-${item}`" class="pill">{{ item }}</span>
              </div>
            </div>
            <div>
              <div class="analysis-compare__label">Removed From Base</div>
              <div class="analysis-tags">
                <span v-for="item in comparison.removed_instruments" :key="`removed-${item}`" class="pill">{{ item }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </PanelCard>
    <PanelCard title="CDQ Joint Anomalies" description="Across all instruments, rank days by joint return shock and volume expansion using historical CDQ dominance counts.">
      <el-table v-if="jointAnomalyRows.length" :data="jointAnomalyRows" stripe>
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
        title="No CDQ Joint Anomalies"
        description="This ranking appears after the run has enough history to form 20-day baselines and any event reaches the medium percentile threshold."
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

.analysis-filters__control {
  width: 100%;
}

.analysis-filters__control--wide {
  grid-column: 1 / -1;
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
