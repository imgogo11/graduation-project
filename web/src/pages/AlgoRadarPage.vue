<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import type { EChartsOption } from "echarts";
import { NAlert, NButton, NForm, NFormItem, NInput, NPagination, NSelect, NTable, NTag } from "naive-ui";
import { useRoute } from "vue-router";

import { fetchTradingJointAnomalyRanking, fetchTradingSummary } from "@/api/analysis";
import { fetchImportRuns, fetchImportStats } from "@/api/imports";
import {
  fetchAlgoIndexStatus,
  fetchRiskRadarCalendar,
  fetchRiskRadarEventContext,
  fetchRiskRadarEvents,
  fetchRiskRadarStocks,
  fetchRiskRadarOverview,
  rebuildAlgoIndex,
} from "@/api/riskRadar";
import { fetchTradingRangeKthVolume, fetchTradingRangeMaxAmount, fetchTradingStocks } from "@/api/trading";
import type {
  AlgoIndexStatusRead,
  ImportRunRead,
  TradingDataContractRead,
  TradingJointAnomalyRankingRead,
  TradingRangeKthVolumeRead,
  TradingRangeMaxAmountRead,
  TradingRiskRadarCalendarDayRead,
  TradingRiskRadarEventContextRead,
  TradingRiskRadarEventRead,
  TradingRiskRadarOverviewRead,
  TradingStockRead,
  TradingStockRiskProfileRead,
  TradingSummaryRead,
} from "@/api/types";
import DateInputField from "@/components/DateInputField.vue";
import EChartPanel from "@/components/EChartPanel.vue";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import StatCard from "@/components/StatCard.vue";
import { useTablePager } from "@/composables/useTablePager";
import { useAuthStore } from "@/stores/auth";
import { useDatasetContextStore } from "@/stores/datasetContext";
import { useRuntimeStore } from "@/stores/runtime";
import { formatCompact, formatDate, formatDateTime, formatNumberish, getErrorMessage, toNumber, toStatusTagType } from "@/utils/format";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";
import {
  formatAlgoMethodText,
  formatSeverityText,
  formatStatusText,
  TECHNICAL_TEXT,
} from "@/utils/displayText";


const ALGO_SECTION_TABS = [
  {
    key: "risk",
    label: "风险雷达",
  },
  {
    key: "algorithms",
    label: "算法查询与事件上下文",
  },
] as const;

const runtime = useRuntimeStore();
const auth = useAuthStore();
const datasetContext = useDatasetContextStore();
const route = useRoute();
const loadingRuns = ref(false);
const loadingAlgo = ref(false);
const loadingRadar = ref(false);
const rebuilding = ref(false);
const error = ref("");
usePageErrorNotification(error, "算法雷达加载失败");

const importRuns = ref<ImportRunRead[]>([]);
const stocks = ref<TradingStockRead[]>([]);

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

const algoSummary = ref<TradingSummaryRead | null>(null);
const algoResult = ref<TradingRangeMaxAmountRead | null>(null);
const algoKthResult = ref<TradingRangeKthVolumeRead | null>(null);
const jointAnomalies = ref<TradingJointAnomalyRankingRead | null>(null);
const indexStatus = ref<AlgoIndexStatusRead | null>(null);
const overview = ref<TradingRiskRadarOverviewRead | null>(null);
const events = ref<TradingRiskRadarEventRead[]>([]);
const stockProfiles = ref<TradingStockRiskProfileRead[]>([]);
const calendarRows = ref<TradingRiskRadarCalendarDayRead[]>([]);
const eventContext = ref<TradingRiskRadarEventContextRead | null>(null);
const selectedEventKey = ref("");
const panelNotices = reactive({
  maxAmount: "",
  kthVolume: "",
  joint: "",
  eventContext: "",
});

const kthMethodOptions = [
  { label: "精确结果", value: "persistent_segment_tree" as const },
  { label: "近似结果", value: "t_digest" as const },
];
const severityOptions = [
  { label: "全部严重", value: "" },
  { label: "中", value: "medium" },
  { label: "高", value: "high" },
  { label: "严重", value: "critical" },
];

const importRunOptions = computed(() =>
  importRuns.value.map((item) => ({ label: `#${item.display_id} · ${item.dataset_name}`, value: item.id }))
);
const currentImportRun = computed(() => importRuns.value.find((item) => item.id === filters.importRunId) ?? null);
const stockOptions = computed(() =>
  stocks.value.map((item) => ({ label: `${item.stock_code}${item.stock_name ? ` · ${item.stock_name}` : ""}`, value: item.stock_code }))
);
const currentSection = computed<(typeof ALGO_SECTION_TABS)[number]["key"]>(() =>
  route.path.startsWith("/algo-radar/algorithms") ? "algorithms" : "risk"
);
const isRiskSection = computed(() => currentSection.value === "risk");
const algoCards = computed(() => [
  {
    label: "当前范围记录",
    value: String(algoSummary.value?.record_count ?? 0),
    hint: algoSummary.value ? `${algoSummary.value.start_date} ~ ${algoSummary.value.end_date}` : "等待算法结果",
    tone: "teal" as const,
  },
  {
    label: "区间最大成交额",
    value: algoResult.value ? formatCompact(algoResult.value.max_amount, 2) : "--",
    hint: panelNotices.maxAmount || (algoResult.value ? `命中 ${algoResult.value.matches.length} 个交易日` : "等待区间最大结果"),
    tone: "orange" as const,
  },
  {
    label: "区间第 K 大成交量",
    value: algoKthResult.value ? formatCompact(algoKthResult.value.value, 2) : "--",
    hint:
      panelNotices.kthVolume ||
      (algoKthResult.value ? `${formatAlgoMethodText(algoKthResult.value.method)} / K=${algoKthResult.value.k}` : "等待第 K 大查询结果"),
    tone: "berry" as const,
  },
  {
    label: "联合异常条数",
    value: String(jointAnomalies.value?.rows.length ?? 0),
    hint: panelNotices.joint || (jointAnomalies.value ? "按联合百分位排序" : "等待联合异常结果"),
    tone: "neutral" as const,
  },
]);
const activeRadarEvent = computed(() => {
  if (eventContext.value?.event) {
    return eventContext.value.event;
  }
  if (!selectedEventKey.value) {
    return events.value[0] ?? null;
  }
  return events.value.find((item) => `${item.stock_code}:${item.trade_date}` === selectedEventKey.value) ?? events.value[0] ?? null;
});
const radarCards = computed(() => [
  {
    label: "索引状态",
    value: indexStatus.value?.status ? formatStatusText(indexStatus.value.status) : "--",
    hint: indexStatus.value?.build_completed_at ? `完成于 ${formatDateTime(indexStatus.value.build_completed_at)}` : "等待索引状态",
    tone: "teal" as const,
  },
  {
    label: "异常事件",
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
    label: "中心联合分位",
    value: activeRadarEvent.value ? formatNumberish(activeRadarEvent.value.joint_percentile, 4) : "--",
    hint:
      activeRadarEvent.value
        ? `${activeRadarEvent.value.stock_code} · ${formatDate(activeRadarEvent.value.trade_date)}`
        : "等待事件数据",
    tone: "neutral" as const,
  },
]);
const jointRows = computed(() => jointAnomalies.value?.rows ?? []);
const algoScopeKey = computed(
  () =>
    [
      filters.importRunId ?? "",
      filters.stockCode,
      filters.startDate,
      filters.endDate,
      filters.kInput,
      filters.kthMethod,
      filters.jointTopNInput,
      filters.severity,
      filters.topNInput,
      currentSection.value,
    ].join("|")
);
const jointPager = useTablePager(jointRows, {
  initialPageSize: 20,
  pageSizes: [10, 20, 50, 100],
  resetTriggers: [algoScopeKey],
});
const eventPager = useTablePager(events, {
  initialPageSize: 20,
  pageSizes: [10, 20, 50, 100],
  resetTriggers: [algoScopeKey],
});
const stockProfilePager = useTablePager(stockProfiles, {
  initialPageSize: 20,
  pageSizes: [10, 20, 50, 100],
  resetTriggers: [algoScopeKey],
});

const radarIndicators = [
  { key: "score_return_shock", label: "收益冲击", max: 100 },
  { key: "score_vol_regime", label: "波动体制切换", max: 100 },
  { key: "score_range_shock", label: "真实波幅冲击", max: 100 },
  { key: "score_rvol20", label: "成交活跃(RVOL20)", max: 100 },
  { key: "score_drawdown_pressure", label: "回撤压力", max: 100 },
] as const;

const radarMissingAxes = computed(() => {
  const event = activeRadarEvent.value;
  if (!event) {
    return [];
  }
  return radarIndicators
    .filter((item) => event[item.key] === null || event[item.key] === undefined)
    .map((item) => item.label);
});

const radarOption = computed<EChartsOption | null>(() => {
  const event = activeRadarEvent.value;
  if (!event || radarMissingAxes.value.length) {
    return null;
  }

  return {
    backgroundColor: "transparent",
    tooltip: { trigger: "item" },
    radar: {
      indicator: radarIndicators.map((item) => ({ name: `${item.label}(0-100)`, max: item.max })),
      radius: "70%",
      splitNumber: 5,
    },
    series: [
      {
        type: "radar",
        name: `${event.stock_code} ${formatDate(event.trade_date)}`,
        data: [
          {
            value: radarIndicators.map((item) => toNumber(event[item.key])),
            name: `${event.stock_code} ${formatDate(event.trade_date)}`,
            areaStyle: { opacity: 0.25 },
          },
        ],
      },
    ],
  };
});

const calendarChartOption = computed<EChartsOption | null>(() => {
  if (!calendarRows.value.length) {
    return null;
  }

  return {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" },
    legend: { top: 0 },
    grid: { left: 56, right: 36, top: 56, bottom: 72, containLabel: true },
    xAxis: { type: "category", data: calendarRows.value.map((item) => item.trade_date), axisLabel: { rotate: 35 } },
    yAxis: [{ type: "value", name: "事件数" }, { type: "value", name: "最大百分位" }],
    series: [
      { type: "bar", name: "事件", barMaxWidth: 18, data: calendarRows.value.map((item) => item.event_count) },
      { type: "line", name: "最大百分位", yAxisIndex: 1, smooth: true, showSymbol: false, data: calendarRows.value.map((item) => toNumber(item.max_joint_percentile)) },
    ],
  };
});

function parsePositiveInt(raw: string, label: string): number | undefined;
function parsePositiveInt(raw: string, label: string, allowEmpty: true): number | undefined;
function parsePositiveInt(raw: string, label: string, allowEmpty: false): number;
function parsePositiveInt(raw: string, label: string, allowEmpty = true): number | undefined {
  const normalized = raw.trim();
  if (!normalized) {
    if (allowEmpty) {
      return undefined;
    }
    throw new Error(`${label} 必须是正整数`);
  }

  const parsed = Number(normalized);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`${label}必须是正整数`);
  }

  return parsed;
}

type AlgoPanelNoticeKey = keyof typeof panelNotices;

function clearPanelNotices() {
  (Object.keys(panelNotices) as AlgoPanelNoticeKey[]).forEach((key) => {
    panelNotices[key] = "";
  });
}

function pickVisibleRunId(runRows: ImportRunRead[], candidates: Array<number | undefined>) {
  return candidates.find((candidate) => candidate !== undefined && runRows.some((item) => item.id === candidate)) ?? runRows[0]?.id;
}

function resolveAlgoPanelResult<T>(result: PromiseSettledResult<T>, key: Exclude<AlgoPanelNoticeKey, "eventContext">, label: string) {
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

async function loadStocks() {
  if (!filters.importRunId) {
    stocks.value = [];
    filters.stockCode = "";
    return;
  }

  try {
    stocks.value = await fetchTradingStocks(filters.importRunId);
    if (!stocks.value.some((item) => item.stock_code === filters.stockCode)) {
      filters.stockCode = stocks.value[0]?.stock_code || "";
    }
  } catch (err) {
    error.value = getErrorMessage(err);
    stocks.value = [];
    filters.stockCode = "";
  }
}

async function loadEventContext(event: TradingRiskRadarEventRead) {
  if (!filters.importRunId) {
    eventContext.value = null;
    selectedEventKey.value = "";
    panelNotices.eventContext = "";
    return;
  }

  selectedEventKey.value = `${event.stock_code}:${event.trade_date}`;
  panelNotices.eventContext = "";

  try {
    eventContext.value = await fetchRiskRadarEventContext({
      import_run_id: filters.importRunId,
      stock_code: event.stock_code,
      trade_date: event.trade_date,
    });
  } catch (err) {
    eventContext.value = null;
    panelNotices.eventContext = `事件上下文加载失败：${getErrorMessage(err)}`;
  }
}

async function loadAlgoPanels() {
  if (!filters.importRunId || !filters.stockCode) {
    algoSummary.value = null;
    algoResult.value = null;
    algoKthResult.value = null;
    jointAnomalies.value = null;
    clearPanelNotices();
    return;
  }

  loadingAlgo.value = true;
  try {
    clearPanelNotices();
    algoSummary.value = null;
    algoResult.value = null;
    algoKthResult.value = null;
    jointAnomalies.value = null;
    const summaryPayload = await fetchTradingSummary({
      import_run_id: filters.importRunId,
      stock_code: filters.stockCode,
      start_date: filters.startDate || undefined,
      end_date: filters.endDate || undefined,
    });
    algoSummary.value = summaryPayload;

    const startDate = filters.startDate || summaryPayload.start_date;
    const endDate = filters.endDate || summaryPayload.end_date;

    const results = await Promise.allSettled([
      fetchTradingRangeMaxAmount({ import_run_id: filters.importRunId, stock_code: filters.stockCode, start_date: startDate, end_date: endDate }),
      fetchTradingRangeKthVolume({
        import_run_id: filters.importRunId,
        stock_code: filters.stockCode,
        start_date: startDate,
        end_date: endDate,
        k: parsePositiveInt(filters.kInput, "K 值", false),
        method: filters.kthMethod,
      }),
      fetchTradingJointAnomalyRanking({
        import_run_id: filters.importRunId,
        start_date: filters.startDate || undefined,
        end_date: filters.endDate || undefined,
        top_n: parsePositiveInt(filters.jointTopNInput, "联合异常前N(Top N)"),
      }),
    ]);

    algoResult.value = resolveAlgoPanelResult(results[0], "maxAmount", "区间最大成交额");
    algoKthResult.value = resolveAlgoPanelResult(results[1], "kthVolume", "区间第 K 大成交量");
    jointAnomalies.value = resolveAlgoPanelResult(results[2], "joint", "联合异常排名");

    if (panelNotices.maxAmount || panelNotices.kthVolume || panelNotices.joint) {
      error.value = "部分算法结果加载失败，请查看对应卡片中的提示";
    }
  } finally {
    loadingAlgo.value = false;
  }
}

async function loadRadar() {
  if (!filters.importRunId) {
    indexStatus.value = null;
    overview.value = null;
    events.value = [];
    stockProfiles.value = [];
    calendarRows.value = [];
    eventContext.value = null;
    panelNotices.eventContext = "";
    selectedEventKey.value = "";
    return;
  }

  loadingRadar.value = true;
  try {
    indexStatus.value = null;
    overview.value = null;
    events.value = [];
    stockProfiles.value = [];
    calendarRows.value = [];
    eventContext.value = null;
    panelNotices.eventContext = "";
    selectedEventKey.value = "";
    indexStatus.value = await fetchAlgoIndexStatus({ import_run_id: filters.importRunId });
    if (!indexStatus.value.is_ready) {
      if (indexStatus.value.status === "failed" && indexStatus.value.last_error) {
        error.value = `算法雷达不可用：${indexStatus.value.last_error}`;
      }
      return;
    }

    const [overviewPayload, eventPayload, stockPayload, calendarPayload] = await Promise.all([
      fetchRiskRadarOverview({ import_run_id: filters.importRunId }),
      fetchRiskRadarEvents({
        import_run_id: filters.importRunId,
        start_date: filters.startDate || undefined,
        end_date: filters.endDate || undefined,
        severity: filters.severity || undefined,
        top_n: parsePositiveInt(filters.topNInput, "事件前N(Top N)"),
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
      panelNotices.eventContext = "";
    }
  } finally {
    loadingRadar.value = false;
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
    syncContext();
    await Promise.all([loadAlgoPanels(), loadRadar()]);
    runtime.markSynced();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loadingRuns.value = false;
  }
}

async function applyScope() {
  error.value = "";
  try {
    syncContext();
    await Promise.all([loadAlgoPanels(), loadRadar()]);
    runtime.markSynced();
  } catch (err) {
    error.value = getErrorMessage(err);
  }
}

async function handleRunChange() {
  await loadStocks();
  await applyScope();
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
    <PanelCard title="算法筛选器">
      <template #actions>
        <div class="toolbar-row">
          <n-button type="primary" :loading="loadingAlgo || loadingRadar" @click="applyScope">应用范围</n-button>
          <n-button v-if="auth.isAdmin.value" secondary :loading="rebuilding" @click="handleRebuild">重建索引</n-button>
        </div>
      </template>
      <n-form class="form-grid" label-placement="top">
        <n-form-item label="批次">
          <n-select v-model:value="filters.importRunId" :options="importRunOptions" @update:value="handleRunChange" />
        </n-form-item>
        <n-form-item label="股票">
          <n-select v-model:value="filters.stockCode" :options="stockOptions" @update:value="applyScope" />
        </n-form-item>
        <n-form-item label="开始日期">
          <DateInputField v-model="filters.startDate" clearable />
        </n-form-item>
        <n-form-item label="结束日期">
          <DateInputField v-model="filters.endDate" clearable />
        </n-form-item>
        <n-form-item label="K 值">
          <n-input v-model:value="filters.kInput" placeholder="区间第 K 大成交量" />
        </n-form-item>
        <n-form-item label="K 算法">
          <n-select v-model:value="filters.kthMethod" :options="kthMethodOptions" />
        </n-form-item>
        <n-form-item label="联合异常前N(Top N)">
          <n-input v-model:value="filters.jointTopNInput" placeholder="默认 20" />
        </n-form-item>
        <n-form-item label="事件严重">
          <n-select v-model:value="filters.severity" :options="severityOptions" />
        </n-form-item>
        <n-form-item label="事件前N(Top N)">
          <n-input v-model:value="filters.topNInput" placeholder="默认 50" />
        </n-form-item>
      </n-form>
    </PanelCard>

    <section v-if="!isRiskSection" class="page__grid page__grid--stats">
      <StatCard v-for="item in algoCards" :key="item.label" :label="item.label" :value="item.value" :hint="item.hint" :tone="item.tone" />
    </section>

    <section v-if="!isRiskSection" class="page__grid page__grid--double">
      <PanelCard title="区间算法结果">
        <div v-if="algoSummary" class="detail-grid">
          <div class="detail-grid__item"><span class="detail-grid__label">股票</span><div class="detail-grid__value">{{ algoSummary.stock_code }}{{ algoSummary.stock_name ? ` · ${algoSummary.stock_name}` : "" }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">时间范围</span><div class="detail-grid__value">{{ algoSummary.start_date }} ~ {{ algoSummary.end_date }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">区间最大成交额</span><div class="detail-grid__value">{{ algoResult ? formatCompact(algoResult.max_amount, 2) : "--" }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">第 K 大成交量</span><div class="detail-grid__value">{{ algoKthResult ? formatCompact(algoKthResult.value, 2) : "--" }}</div></div>
        </div>
        <n-alert v-if="panelNotices.maxAmount" type="warning" :show-icon="true" style="margin-top: 12px;">{{ panelNotices.maxAmount }}</n-alert>
        <n-alert v-if="panelNotices.kthVolume" type="warning" :show-icon="true" style="margin-top: 12px;">{{ panelNotices.kthVolume }}</n-alert>
        <div v-if="algoResult?.matches.length" class="inline-hint" style="margin-top: 12px;">最大成交额命中日期：{{ algoResult.matches.map((item) => item.trade_date).join("、") }}</div>
        <div v-if="algoKthResult?.matches.length" class="inline-hint" style="margin-top: 8px;">第 K 大成交量命中日期：{{ algoKthResult.matches.map((item) => item.trade_date).join("、") }}</div>
        <EmptyState v-else-if="!algoSummary" title="暂无区间算法结果" description="选择批次和股票后，这里会展示区间算法查询结果" />
      </PanelCard>

      <PanelCard title="联合异常排名">
        <n-alert v-if="panelNotices.joint" type="warning" :show-icon="true">{{ panelNotices.joint }}</n-alert>
      <div v-else-if="jointPager.total.value" class="data-table-wrap">
          <n-table class="data-table" striped size="small" :single-line="false">
            <thead><tr><th>股票</th><th>日期</th><th>严重</th><th>日收益</th><th>{{ TECHNICAL_TEXT.returnZ20 }}</th><th>{{ TECHNICAL_TEXT.volumeRatio20 }}</th><th>联合百分位</th></tr></thead>
            <tbody>
              <tr v-for="item in jointPager.pagedRows.value" :key="`${item.stock_code}-${item.trade_date}`">
                <td>{{ item.stock_code }}{{ item.stock_name ? ` · ${item.stock_name}` : "" }}</td>
                <td>{{ formatDate(item.trade_date) }}</td>
                <td><n-tag :type="toStatusTagType(item.severity)" round size="small">{{ formatSeverityText(item.severity) }}</n-tag></td>
                <td>{{ formatNumberish(item.daily_return, 4) }}</td>
                <td>{{ formatNumberish(item.return_z20, 4) }}</td>
                <td>{{ formatNumberish(item.volume_ratio20, 4) }}</td>
                <td>{{ formatNumberish(item.joint_percentile, 4) }}</td>
              </tr>
            </tbody>
          </n-table>
          <div class="table-pagination">
            <n-pagination
              :page="jointPager.page.value"
              :page-size="jointPager.pageSize.value"
              :item-count="jointPager.total.value"
              :page-sizes="jointPager.pageSizes"
              show-size-picker
              @update:page="jointPager.setPage"
              @update:page-size="jointPager.setPageSize"
            />
          </div>
        </div>
        <div v-if="jointAnomalies" class="inline-hint" style="margin-top: 8px;">{{ formatModuleSummary(jointAnomalies) }}</div>
        <EmptyState v-else title="暂无联合异常结果" description="执行算法后，这里会展示跨股票的联合异常排名" />
      </PanelCard>
    </section>

    <section v-if="isRiskSection" class="page__grid page__grid--stats">
      <StatCard v-for="item in radarCards" :key="item.label" :label="item.label" :value="item.value" :hint="item.hint" :tone="item.tone" />
    </section>

    <section v-if="isRiskSection" class="page__grid page__grid--double">
      <PanelCard title="风险雷达（5轴分位）">
        <n-alert v-if="radarMissingAxes.length" type="warning" :show-icon="true" style="margin-bottom: 12px;">
          当前事件样本不足，缺失轴：{{ radarMissingAxes.join("、") }}。请扩大日期范围或使用更长历史数据。
        </n-alert>
        <EChartPanel v-if="radarOption" :option="radarOption" :loading="loadingRadar" />
        <div v-if="overview" class="inline-hint" style="margin-top: 8px;">{{ formatModuleSummary(overview) }}</div>
        <EmptyState
          v-else
          :title="indexStatus?.is_ready === false ? '索引尚未就绪' : '暂无风险雷达数据'"
          :description="indexStatus?.is_ready === false ? '请先完成算法索引构建后再查看风险雷达。' : '执行算法后，这里会展示 5 轴雷达图。'"
        />
      </PanelCard>

      <PanelCard title="风险日历">
        <EChartPanel v-if="calendarChartOption" :option="calendarChartOption" :loading="loadingRadar" />
        <EmptyState v-else title="暂无风险日历" description="执行算法后，这里会展示事件时间分布" />
      </PanelCard>
    </section>

    <section v-if="isRiskSection" class="page__grid page__grid--double">
      <PanelCard title="风险事件列表">
      <div v-if="eventPager.total.value" class="data-table-wrap">
          <n-table class="data-table" striped size="small" :single-line="false">
            <thead><tr><th>股票</th><th>日期</th><th>严重</th><th>原因</th><th>收益冲击</th><th>波动体制</th><th>波幅冲击</th><th>RVOL20</th><th>回撤压力</th><th>联合分位</th></tr></thead>
            <tbody>
              <tr
                v-for="item in eventPager.pagedRows.value"
                :key="`${item.stock_code}-${item.trade_date}`"
                :class="{ 'data-table__row--active': selectedEventKey === `${item.stock_code}:${item.trade_date}` }"
                @click="loadEventContext(item)"
              >
                <td>{{ item.stock_code }}{{ item.stock_name ? ` · ${item.stock_name}` : "" }}</td>
                <td>{{ formatDate(item.trade_date) }}</td>
                <td><n-tag :type="toStatusTagType(item.severity)" round size="small">{{ formatSeverityText(item.severity) }}</n-tag></td>
                <td>{{ item.cause_label }}</td>
                <td>{{ formatNumberish(item.return_shock, 4) }}</td>
                <td>{{ formatNumberish(item.vol_regime, 4) }}</td>
                <td>{{ formatNumberish(item.range_shock, 4) }}</td>
                <td>{{ formatNumberish(item.rvol20, 4) }}</td>
                <td>{{ formatNumberish(item.drawdown_pressure, 4) }}</td>
                <td>{{ formatNumberish(item.joint_percentile, 4) }}</td>
              </tr>
            </tbody>
          </n-table>
          <div class="table-pagination">
            <n-pagination
              :page="eventPager.page.value"
              :page-size="eventPager.pageSize.value"
              :item-count="eventPager.total.value"
              :page-sizes="eventPager.pageSizes"
              show-size-picker
              @update:page="eventPager.setPage"
              @update:page-size="eventPager.setPageSize"
            />
          </div>
        </div>
        <EmptyState v-else title="暂无风险事件" description="索引准备好后，这里会返回当前范围内的异常事件" />
      </PanelCard>

      <PanelCard title="高风险股票画像">
      <div v-if="stockProfilePager.total.value" class="data-table-wrap">
          <n-table class="data-table" striped size="small" :single-line="false">
            <thead><tr><th>股票</th><th>事件数</th><th>严重</th><th>高</th><th>中</th><th>最大百分位</th><th>最近事件</th></tr></thead>
            <tbody>
              <tr v-for="item in stockProfilePager.pagedRows.value" :key="item.stock_code">
                <td>{{ item.stock_code }}{{ item.stock_name ? ` · ${item.stock_name}` : "" }}</td>
                <td>{{ item.event_count }}</td>
                <td>{{ item.critical_count }}</td>
                <td>{{ item.high_count }}</td>
                <td>{{ item.medium_count }}</td>
                <td>{{ formatNumberish(item.max_joint_percentile, 4) }}</td>
                <td>{{ formatDate(item.latest_event_date) }}</td>
              </tr>
            </tbody>
          </n-table>
          <div class="table-pagination">
            <n-pagination
              :page="stockProfilePager.page.value"
              :page-size="stockProfilePager.pageSize.value"
              :item-count="stockProfilePager.total.value"
              :page-sizes="stockProfilePager.pageSizes"
              show-size-picker
              @update:page="stockProfilePager.setPage"
              @update:page-size="stockProfilePager.setPageSize"
            />
          </div>
        </div>
        <EmptyState v-else title="暂无股票画像" description="执行风险雷达查询后，这里会展示受影响股票的聚合画像" />
      </PanelCard>
    </section>

    <PanelCard v-if="!isRiskSection" title="事件上下文">
      <n-alert v-if="panelNotices.eventContext" type="warning" :show-icon="true">{{ panelNotices.eventContext }}</n-alert>
      <div v-else-if="eventContext" class="page__grid page__grid--double">
        <div class="detail-grid">
          <div class="detail-grid__item"><span class="detail-grid__label">股票</span><div class="detail-grid__value">{{ eventContext.event.stock_code }}{{ eventContext.event.stock_name ? ` · ${eventContext.event.stock_name}` : "" }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">事件日期</span><div class="detail-grid__value">{{ formatDate(eventContext.event.trade_date) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">严重</span><div class="detail-grid__value">{{ formatSeverityText(eventContext.event.severity) }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">原因</span><div class="detail-grid__value">{{ eventContext.event.cause_label }}</div></div>
        </div>

        <div class="detail-grid">
          <div
            v-for="group in eventContext.window_groups"
            :key="group.metric"
            class="detail-grid__item"
            style="grid-column: 1 / -1;"
          >
            <span class="detail-grid__label">{{ group.label }}</span>
            <div class="detail-grid__value">
              {{ group.windows.map((item) => `${item.window_days}日: 当前 ${formatNumberish(item.current_value, 4)} / P95 ${formatNumberish(item.p95, 4)}`).join(" ｜ ") }}
            </div>
          </div>
        </div>
      </div>

      <div v-if="eventContext?.distribution_changes.length" style="margin-top: 18px;" class="data-table-wrap">
        <n-table class="data-table" striped size="small" :single-line="false">
          <thead><tr><th>指标</th><th>窗口</th><th>前中位数</th><th>前 P95</th><th>后中位数</th><th>后 P95</th></tr></thead>
          <tbody>
            <tr v-for="item in eventContext.distribution_changes" :key="`${item.metric}-${item.window_days}`">
              <td>{{ item.metric }}</td>
              <td>{{ item.window_days }} </td>
              <td>{{ formatNumberish(item.before_median, 4) }}</td>
              <td>{{ formatNumberish(item.before_p95, 4) }}</td>
              <td>{{ formatNumberish(item.after_median, 4) }}</td>
              <td>{{ formatNumberish(item.after_p95, 4) }}</td>
            </tr>
          </tbody>
        </n-table>
      </div>

      <div v-if="eventContext?.local_amount_peak" style="margin-top: 16px;" class="inline-hint">
        局部成交额峰：{{ eventContext.local_amount_peak.start_date }} ~ {{ eventContext.local_amount_peak.end_date }}，
        峰值 ${{ formatCompact(eventContext.local_amount_peak.peak_amount, 2) }}，
        日期 {{ eventContext.local_amount_peak.peak_dates.map((item) => item.trade_date).join("、") }}。
      </div>

      <EmptyState v-else-if="!eventContext" title="暂无事件上下文" description="点击左侧任一风险事件后，这里会展示对应的窗口统计" />
      <div v-if="eventContext" class="inline-hint" style="margin-top: 12px;">{{ formatModuleSummary(eventContext) }}</div>
    </PanelCard>
  </div>
</template>


