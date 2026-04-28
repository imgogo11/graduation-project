<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, watch } from "vue";

import type { EChartsOption } from "echarts";
import {
  NAlert,
  NButton,
  NDataTable,
  NDatePicker,
  NForm,
  NFormItemGi,
  NGrid,
  NInput,
  NSelect,
  NTag,
  useMessage,
  type DataTableColumns,
  type DataTableCreateRowClassName,
  type DataTableCreateRowProps,
} from "naive-ui";
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
} from "@/api/riskRadar";
import { fetchTradingRangeKthVolume, fetchTradingRangeMaxAmount, fetchTradingStocks } from "@/api/trading";
import type {
  AlgoIndexStatusRead,
  ImportRunRead,
  NumericLike,
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
import EChartPanel from "@/components/EChartPanel.vue";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import { useTablePager } from "@/composables/useTablePager";
import { useDatasetContextStore } from "@/stores/datasetContext";
import { useRuntimeStore } from "@/stores/runtime";
import {
  formatDate,
  formatNumberish,
  formatRmbAmount,
  formatShareVolume,
  getErrorMessage,
  toNumber,
  toStatusTagType,
} from "@/utils/format";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";
import {
  formatRiskCauseText,
  formatSeverityText,
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
const datasetContext = useDatasetContextStore();
const route = useRoute();
const message = useMessage();
const loadingRuns = ref(false);
const loadingAlgo = ref(false);
const loadingRadar = ref(false);
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
  { label: "全部", value: "" },
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
const currentSection = computed<(typeof ALGO_SECTION_TABS)[number]["key"]>(() =>
  route.path.startsWith("/algo-radar/algorithms") ? "algorithms" : "risk"
);
const isRiskSection = computed(() => currentSection.value === "risk");
const activeRadarEvent = computed(() => {
  if (eventContext.value?.event) {
    return eventContext.value.event;
  }
  if (!selectedEventKey.value) {
    return events.value[0] ?? null;
  }
  return events.value.find((item) => `${item.stock_code}:${item.trade_date}` === selectedEventKey.value) ?? events.value[0] ?? null;
});
const radarCenterJointText = computed(() => (activeRadarEvent.value ? formatNumberish(activeRadarEvent.value.joint_percentile, 4) : "--"));
const radarEventCountText = computed(() => String(eventPager.total.value));
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

type JointAnomalyRow = TradingJointAnomalyRankingRead["rows"][number];
type DistributionChangeRow = TradingRiskRadarEventContextRead["distribution_changes"][number];

const algoTableMaxHeight = "min(48vh, 420px)";
const eventTableScrollX = 1320;
const distributionTableMaxHeight = "min(45vh, 420px)";

const jointTableColumns: DataTableColumns<JointAnomalyRow> = [
  {
    title: "股票",
    key: "stock_code",
    width: 190,
    render(item) {
      return `${item.stock_code}${item.stock_name ? ` · ${item.stock_name}` : ""}`;
    },
  },
  {
    title: "日期",
    key: "trade_date",
    width: 130,
    render(item) {
      return formatDate(item.trade_date);
    },
  },
  {
    title: "严重",
    key: "severity",
    width: 110,
    render(item) {
      return h(
        NTag,
        {
          type: toStatusTagType(item.severity),
          round: true,
          size: "small",
        },
        { default: () => formatSeverityText(item.severity) }
      );
    },
  },
  {
    title: "日收益",
    key: "daily_return",
    width: 120,
    render(item) {
      return formatNumberish(item.daily_return, 4);
    },
  },
  {
    title: TECHNICAL_TEXT.returnZ20,
    key: "return_z20",
    width: 140,
    render(item) {
      return formatNumberish(item.return_z20, 4);
    },
  },
  {
    title: TECHNICAL_TEXT.volumeRatio20,
    key: "volume_ratio20",
    width: 150,
    render(item) {
      return formatNumberish(item.volume_ratio20, 4);
    },
  },
  {
    title: "联合百分位",
    key: "joint_percentile",
    width: 140,
    render(item) {
      return formatNumberish(item.joint_percentile, 4);
    },
  },
];

const jointTablePagination = computed(() => ({
  page: jointPager.page.value,
  pageSize: jointPager.pageSize.value,
  itemCount: jointPager.total.value,
  pageSizes: jointPager.pageSizes,
  showSizePicker: true,
  onUpdatePage: jointPager.setPage,
  onUpdatePageSize: jointPager.setPageSize,
}));

const eventTableColumns: DataTableColumns<TradingRiskRadarEventRead> = [
  {
    title: "股票",
    key: "stock_code",
    width: 190,
    render(item) {
      return `${item.stock_code}${item.stock_name ? ` · ${item.stock_name}` : ""}`;
    },
  },
  {
    title: "日期",
    key: "trade_date",
    width: 130,
    render(item) {
      return formatDate(item.trade_date);
    },
  },
  {
    title: "严重",
    key: "severity",
    width: 110,
    render(item) {
      return h(
        NTag,
        {
          type: toStatusTagType(item.severity),
          round: true,
          size: "small",
        },
        { default: () => formatSeverityText(item.severity) }
      );
    },
  },
  {
    title: "原因",
    key: "cause_label",
    width: 150,
    render(item) {
      return formatRiskCauseText(item.cause_label);
    },
  },
  {
    title: "收益冲击",
    key: "return_shock",
    width: 120,
    render(item) {
      return formatNumberish(item.return_shock, 4);
    },
  },
  {
    title: "波动体制",
    key: "vol_regime",
    width: 120,
    render(item) {
      return formatNumberish(item.vol_regime, 4);
    },
  },
  {
    title: "波幅冲击",
    key: "range_shock",
    width: 120,
    render(item) {
      return formatNumberish(item.range_shock, 4);
    },
  },
  {
    title: "RVOL20",
    key: "rvol20",
    width: 110,
    render(item) {
      return formatNumberish(item.rvol20, 4);
    },
  },
  {
    title: "回撤压力",
    key: "drawdown_pressure",
    width: 120,
    render(item) {
      return formatNumberish(item.drawdown_pressure, 4);
    },
  },
  {
    title: "联合分位",
    key: "joint_percentile",
    width: 140,
    render(item) {
      return formatNumberish(item.joint_percentile, 4);
    },
  },
];

const eventTablePagination = computed(() => ({
  page: eventPager.page.value,
  pageSize: eventPager.pageSize.value,
  itemCount: eventPager.total.value,
  pageSizes: eventPager.pageSizes,
  showSizePicker: true,
  onUpdatePage: eventPager.setPage,
  onUpdatePageSize: eventPager.setPageSize,
}));

const eventRowClassName: DataTableCreateRowClassName<TradingRiskRadarEventRead> = (item) =>
  selectedEventKey.value === `${item.stock_code}:${item.trade_date}` ? "data-table__row--active" : "";

const eventRowProps: DataTableCreateRowProps<TradingRiskRadarEventRead> = (item) => ({
  onClick: () => loadEventContext(item),
});

const stockProfileTableColumns: DataTableColumns<TradingStockRiskProfileRead> = [
  {
    title: "股票",
    key: "stock_code",
    width: 190,
    render(item) {
      return `${item.stock_code}${item.stock_name ? ` · ${item.stock_name}` : ""}`;
    },
  },
  {
    title: "事件数",
    key: "event_count",
    width: 110,
  },
  {
    title: "严重",
    key: "critical_count",
    width: 100,
  },
  {
    title: "高",
    key: "high_count",
    width: 90,
  },
  {
    title: "中",
    key: "medium_count",
    width: 90,
  },
  {
    title: "最大百分位",
    key: "max_joint_percentile",
    width: 150,
    render(item) {
      return formatNumberish(item.max_joint_percentile, 4);
    },
  },
  {
    title: "最近事件",
    key: "latest_event_date",
    width: 130,
    render(item) {
      return formatDate(item.latest_event_date);
    },
  },
];

const stockProfileTablePagination = computed(() => ({
  page: stockProfilePager.page.value,
  pageSize: stockProfilePager.pageSize.value,
  itemCount: stockProfilePager.total.value,
  pageSizes: stockProfilePager.pageSizes,
  showSizePicker: true,
  onUpdatePage: stockProfilePager.setPage,
  onUpdatePageSize: stockProfilePager.setPageSize,
}));

const distributionTableColumns: DataTableColumns<DistributionChangeRow> = [
  {
    title: "指标",
    key: "metric",
    width: 160,
  },
  {
    title: "窗口",
    key: "window_days",
    width: 100,
    render(item) {
      return String(item.window_days);
    },
  },
  {
    title: "前中位数",
    key: "before_median",
    width: 140,
    render(item) {
      return formatNumberish(item.before_median, 4);
    },
  },
  {
    title: "前 P95",
    key: "before_p95",
    width: 140,
    render(item) {
      return formatNumberish(item.before_p95, 4);
    },
  },
  {
    title: "后中位数",
    key: "after_median",
    width: 140,
    render(item) {
      return formatNumberish(item.after_median, 4);
    },
  },
  {
    title: "后 P95",
    key: "after_p95",
    width: 160,
    render(item) {
      return formatNumberish(item.after_p95, 4);
    },
  },
];

function getJointRowKey(item: JointAnomalyRow) {
  return `${item.stock_code}-${item.trade_date}`;
}

function getEventRowKey(item: TradingRiskRadarEventRead) {
  return `${item.stock_code}-${item.trade_date}`;
}

function getStockProfileRowKey(item: TradingStockRiskProfileRead) {
  return item.stock_code;
}

function getDistributionRowKey(item: DistributionChangeRow) {
  return `${item.metric}-${item.window_days}`;
}

function formatEventContextValue(metric: string, value: NumericLike) {
  if (metric === "volume") {
    return formatShareVolume(value, 2);
  }
  return formatNumberish(value, 4);
}

function severityPillClass(severity: string) {
  return ["event-context-severity", `event-context-severity--${severity}`];
}

const radarIndicators = [
  { key: "score_return_shock", label: "收益冲击", max: 100 },
  { key: "score_vol_regime", label: "波动体制切换", max: 100 },
  { key: "score_range_shock", label: "真实波幅冲击", max: 100 },
  { key: "score_rvol20", label: "成交活跃(RVOL20)", max: 100 },
  { key: "score_drawdown_pressure", label: "回撤压力", max: 100 },
] as const;

function isUsableRadarValue(value: unknown) {
  return value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
}

const radarMissingAxes = computed(() => {
  const event = activeRadarEvent.value;
  if (!event) {
    return [];
  }
  return radarIndicators
    .filter((item) => !isUsableRadarValue(event[item.key]))
    .map((item) => item.label);
});
const radarEmptyDescription = computed(() => {
  if (indexStatus.value?.is_ready === false) {
    return "请先完成算法索引构建后再查看风险雷达。";
  }
  if (overview.value && !activeRadarEvent.value) {
    return "当前筛选范围内没有可展示的风险事件，请调整日期范围、严重程度或事件数量。";
  }
  return "执行算法后，这里会展示 5 轴雷达图。";
});

const radarOption = computed<EChartsOption | null>(() => {
  const event = activeRadarEvent.value;
  if (!event || radarMissingAxes.value.length) {
    return null;
  }

  return {
    backgroundColor: "transparent",
    tooltip: { trigger: "item", appendToBody: true, confine: false },
    radar: {
      indicator: radarIndicators.map((item) => ({ name: `${item.label}(0-100)`, max: item.max })),
      center: ["50%", "54%"],
      radius: "58%",
      splitNumber: 5,
      axisName: {
        overflow: "break",
        width: 92,
      },
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
    kInput: filters.kInput,
    kthMethod: filters.kthMethod,
    jointTopNInput: filters.jointTopNInput,
    severity: filters.severity,
    eventTopNInput: filters.topNInput,
  });
}

function syncFiltersFromContext() {
  filters.importRunId = datasetContext.state.importRunId;
  filters.stockCode = datasetContext.state.stockCode;
  filters.startDate = datasetContext.state.startDate;
  filters.endDate = datasetContext.state.endDate;
  filters.kInput = datasetContext.state.kInput;
  filters.kthMethod = datasetContext.state.kthMethod;
  filters.jointTopNInput = datasetContext.state.jointTopNInput;
  filters.severity = datasetContext.state.severity;
  filters.topNInput = datasetContext.state.eventTopNInput;
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

async function applyScope(options: { notify?: boolean } = {}) {
  error.value = "";
  try {
    syncContext();
    await Promise.all([loadAlgoPanels(), loadRadar()]);
    runtime.markSynced();
    if (options.notify && !error.value) {
      message.success("范围已应用");
    } else if (options.notify && error.value) {
      message.warning("范围已应用，部分结果加载失败");
    }
  } catch (err) {
    error.value = getErrorMessage(err);
    if (options.notify) {
      message.error(error.value);
    }
  }
}

async function handleRunChange() {
  await loadStocks();
  await applyScope();
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
    <section v-if="!isRiskSection">
      <PanelCard title="区间算法结果">
        <div v-if="algoSummary" class="detail-grid">
          <div class="detail-grid__item"><span class="detail-grid__label">股票</span><div class="detail-grid__value">{{ algoSummary.stock_code }}{{ algoSummary.stock_name ? ` · ${algoSummary.stock_name}` : "" }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">时间范围</span><div class="detail-grid__value">{{ algoSummary.start_date }} ~ {{ algoSummary.end_date }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">区间最大成交额</span><div class="detail-grid__value">{{ algoResult ? formatRmbAmount(algoResult.max_amount, 2) : "--" }}</div></div>
          <div class="detail-grid__item"><span class="detail-grid__label">第 K 大成交量</span><div class="detail-grid__value">{{ algoKthResult ? formatShareVolume(algoKthResult.value, 2) : "--" }}</div></div>
        </div>
        <n-alert v-if="panelNotices.maxAmount" type="warning" :show-icon="true" style="margin-top: 12px;">{{ panelNotices.maxAmount }}</n-alert>
        <n-alert v-if="panelNotices.kthVolume" type="warning" :show-icon="true" style="margin-top: 12px;">{{ panelNotices.kthVolume }}</n-alert>
        <div v-if="algoResult?.matches.length" class="inline-hint" style="margin-top: 12px;">最大成交额命中日期：{{ algoResult.matches.map((item) => item.trade_date).join("、") }}</div>
        <div v-if="algoKthResult?.matches.length" class="inline-hint" style="margin-top: 8px;">第 K 大成交量命中日期：{{ algoKthResult.matches.map((item) => item.trade_date).join("、") }}</div>
        <EmptyState v-else-if="!algoSummary" title="暂无区间算法结果" description="选择批次和股票后，这里会展示区间算法查询结果" />
      </PanelCard>
    </section>

    <section v-if="!isRiskSection">
      <PanelCard title="联合异常排名">
        <n-alert v-if="panelNotices.joint" type="warning" :show-icon="true">{{ panelNotices.joint }}</n-alert>
      <n-data-table
        v-else-if="jointPager.total.value"
        class="algo-data-table"
        :columns="jointTableColumns"
        :data="jointRows"
        :pagination="jointTablePagination"
        :row-key="getJointRowKey"
        :max-height="algoTableMaxHeight"
        :single-line="false"
        striped
        size="small"
      />
        <div v-if="jointAnomalies" class="inline-hint" style="margin-top: 8px;">{{ formatModuleSummary(jointAnomalies) }}</div>
        <EmptyState v-else title="暂无联合异常结果" description="执行算法后，这里会展示跨股票的联合异常排名" />
      </PanelCard>
    </section>

    <section v-if="isRiskSection" class="page__grid page__grid--double">
      <PanelCard title="风险雷达（5轴分位）">
        <template #title>
          <span class="panel-title-inline">
            <span>风险雷达（5轴分位）</span>
            <n-tag size="small" round type="info">中心联合分位 {{ radarCenterJointText }}</n-tag>
          </span>
        </template>
        <n-alert v-if="radarMissingAxes.length" type="warning" :show-icon="true" style="margin-bottom: 12px;">
          当前事件样本不足，缺失轴：{{ radarMissingAxes.join("、") }}。请扩大日期范围或使用更长历史数据。
        </n-alert>
        <EChartPanel v-if="radarOption" :option="radarOption" :loading="loadingRadar" height="420px" />
        <EmptyState
          v-if="!radarOption && !radarMissingAxes.length"
          :title="indexStatus?.is_ready === false ? '索引尚未就绪' : '暂无风险雷达数据'"
          :description="radarEmptyDescription"
        />
        <div v-if="overview" class="inline-hint" style="margin-top: 8px;">{{ formatModuleSummary(overview) }}</div>
      </PanelCard>

      <PanelCard title="风险日历">
        <EChartPanel v-if="calendarChartOption" :option="calendarChartOption" :loading="loadingRadar" />
        <EmptyState v-else title="暂无风险日历" description="执行算法后，这里会展示事件时间分布" />
      </PanelCard>
    </section>

    <section v-if="isRiskSection">
      <PanelCard title="风险事件列表">
        <template #title>
          <span class="panel-title-inline">
            <span>风险事件列表</span>
            <n-tag size="small" round type="warning">当前事件 {{ radarEventCountText }}</n-tag>
          </span>
        </template>
      <n-data-table
        v-if="eventPager.total.value"
        class="algo-data-table algo-data-table--clickable"
        :columns="eventTableColumns"
        :data="events"
        :pagination="eventTablePagination"
        :row-class-name="eventRowClassName"
        :row-key="getEventRowKey"
        :row-props="eventRowProps"
        :max-height="algoTableMaxHeight"
        :scroll-x="eventTableScrollX"
        :scrollbar-props="{ trigger: 'none' }"
        :single-line="false"
        striped
        size="small"
      />
        <EmptyState v-else title="暂无风险事件" description="索引准备好后，这里会返回当前范围内的异常事件" />
      </PanelCard>
    </section>

    <section v-if="isRiskSection">
      <PanelCard title="高风险股票画像">
      <n-data-table
        v-if="stockProfilePager.total.value"
        class="algo-data-table"
        :columns="stockProfileTableColumns"
        :data="stockProfiles"
        :pagination="stockProfileTablePagination"
        :row-key="getStockProfileRowKey"
        :max-height="algoTableMaxHeight"
        :single-line="false"
        striped
        size="small"
      />
        <EmptyState v-else title="暂无股票画像" description="执行风险雷达查询后，这里会展示受影响股票的聚合画像" />
      </PanelCard>
    </section>

    <PanelCard v-if="!isRiskSection" title="事件上下文">
      <n-alert v-if="panelNotices.eventContext" type="warning" :show-icon="true">{{ panelNotices.eventContext }}</n-alert>
      <div v-else-if="eventContext" class="event-context">
        <div class="event-context-summary">
          <div class="event-context-summary__identity">
            <span class="event-context-summary__code">{{ eventContext.event.stock_code }}</span>
            <span v-if="eventContext.event.stock_name" class="event-context-summary__name">{{ eventContext.event.stock_name }}</span>
          </div>
          <div class="event-context-summary__meta">
            <div class="event-context-summary__item">
              <span class="event-context-summary__label">事件日期</span>
              <strong>{{ formatDate(eventContext.event.trade_date) }}</strong>
            </div>
            <div class="event-context-summary__item">
              <span class="event-context-summary__label">严重程度</span>
              <span :class="severityPillClass(eventContext.event.severity)">
                {{ formatSeverityText(eventContext.event.severity) }}
              </span>
            </div>
            <div class="event-context-summary__item event-context-summary__item--wide">
              <span class="event-context-summary__label">触发原因</span>
              <strong>{{ formatRiskCauseText(eventContext.event.cause_label) }}</strong>
            </div>
          </div>
        </div>

        <div class="event-context-metrics">
          <div
            v-for="group in eventContext.window_groups"
            :key="group.metric"
            class="event-context-metric"
          >
            <div class="event-context-metric__head">
              <span class="event-context-metric__label">{{ group.label }}</span>
              <span class="event-context-metric__metric">{{ group.metric }}</span>
            </div>
            <div class="event-context-window-grid">
              <div
                v-for="item in group.windows"
                :key="`${group.metric}-${item.window_days}`"
                class="event-context-window"
              >
                <div class="event-context-window__period">{{ item.window_days }}日窗口</div>
                <div class="event-context-window__row">
                  <span>当前</span>
                  <strong>{{ formatEventContextValue(group.metric, item.current_value) }}</strong>
                </div>
                <div class="event-context-window__row">
                  <span>P95</span>
                  <strong>{{ formatEventContextValue(group.metric, item.p95) }}</strong>
                </div>
                <div class="event-context-window__row">
                  <span>精确分位</span>
                  <strong>{{ formatNumberish(item.exact_percentile, 4) }}</strong>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>

      <n-data-table
        v-if="eventContext?.distribution_changes.length"
        class="algo-data-table event-context-table"
        :columns="distributionTableColumns"
        :data="eventContext.distribution_changes"
        :row-key="getDistributionRowKey"
        :max-height="distributionTableMaxHeight"
        :single-line="false"
        striped
        size="small"
      />

      <EmptyState v-else-if="!eventContext" title="暂无事件上下文" description="点击左侧任一风险事件后，这里会展示对应的窗口统计" />
      <div v-if="eventContext" class="inline-hint" style="margin-top: 12px;">{{ formatModuleSummary(eventContext) }}</div>
    </PanelCard>
  </div>
</template>

<style scoped>
.panel-title-inline {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.algo-data-table {
  border-radius: 18px;
  overflow: visible;
}

:deep(.algo-data-table .n-data-table-th) {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  white-space: nowrap;
}

:deep(.algo-data-table .n-data-table-td) {
  vertical-align: top;
}

:deep(.algo-data-table .n-data-table__pagination) {
  padding: 0 12px 10px;
  border-top: 1px solid var(--panel-border);
  background: #fff;
}

:deep(.algo-data-table--clickable .n-data-table-tr) {
  cursor: pointer;
}

.event-context-table {
  margin-top: 18px;
}

.event-context {
  display: grid;
  gap: 16px;
}

.event-context-summary {
  display: grid;
  grid-template-columns: minmax(220px, 0.8fr) minmax(360px, 1.6fr);
  gap: 14px;
  align-items: stretch;
}

.event-context-summary__identity,
.event-context-summary__meta,
.event-context-metric {
  border: 1px solid var(--panel-border);
  border-radius: 16px;
  background: #fbfcfe;
}

.event-context-summary__identity {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  min-height: 92px;
  padding: 16px 18px;
}

.event-context-summary__code {
  color: var(--text-primary);
  font-size: 22px;
  font-weight: 800;
  line-height: 1.2;
}

.event-context-summary__name {
  color: var(--text-secondary);
  font-size: 15px;
  line-height: 1.5;
}

.event-context-summary__meta {
  display: grid;
  grid-template-columns: minmax(130px, 0.7fr) minmax(130px, 0.7fr) minmax(180px, 1fr);
  gap: 10px;
  padding: 14px;
}

.event-context-summary__item {
  display: flex;
  min-width: 0;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  padding: 8px 10px;
}

.event-context-summary__label,
.event-context-metric__metric {
  color: var(--text-soft);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.event-context-summary__item strong {
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.5;
}

.event-context-severity {
  display: inline-flex;
  align-items: center;
  align-self: flex-start;
  min-width: 0;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}

.event-context-severity--medium {
  color: #b86b00;
  background: #fff7e8;
  box-shadow: inset 0 0 0 1px rgba(245, 166, 35, 0.34);
}

.event-context-severity--high,
.event-context-severity--critical {
  color: #b42318;
  background: #fff1f0;
  box-shadow: inset 0 0 0 1px rgba(217, 45, 32, 0.28);
}

.event-context-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 14px;
}

.event-context-metric {
  padding: 16px;
}

.event-context-metric__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.event-context-metric__label {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 800;
  line-height: 1.4;
}

.event-context-window-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(128px, 1fr));
  gap: 10px;
}

.event-context-window {
  min-width: 0;
  padding: 12px;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: inset 0 0 0 1px rgba(112, 129, 153, 0.14);
}

.event-context-window__period {
  margin-bottom: 10px;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 800;
}

.event-context-window__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.7;
}

.event-context-window__row strong {
  min-width: 0;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 700;
  overflow-wrap: anywhere;
  text-align: right;
}

@media (max-width: 980px) {
  .event-context-summary {
    grid-template-columns: 1fr;
  }

  .event-context-summary__meta {
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  }
}

@media (max-width: 720px) {
  .event-context-metrics {
    grid-template-columns: 1fr;
  }

  .event-context-window-grid {
    grid-template-columns: 1fr;
  }
}
</style>
