<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, watch } from "vue";
import { SwapHorizontalOutline, TrashOutline } from "@vicons/ionicons5";

import type { EChartsOption } from "echarts";
import {
  NButton,
  NDataTable,
  NForm,
  NFormItemGi,
  NGrid,
  NIcon,
  NInput,
  NModal,
  NSelect,
  NSwitch,
  NTabPane,
  NTabs,
  NTag,
  useMessage,
  type DataTableColumns,
  type DataTableCreateRowClassName,
} from "naive-ui";

import { commitTradingPreview, deleteImportRun, fetchImportRuns, fetchImportStats, previewTradingFile } from "@/api/imports";
import { fetchTradingRecords, fetchTradingStocks } from "@/api/trading";
import type {
  ImportPreviewRead,
  ImportRunRead,
  ImportStatsRead,
  TradingRecordRead,
  TradingStockRead,
} from "@/api/types";
import EChartPanel from "@/components/EChartPanel.vue";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import { useTablePager } from "@/composables/useTablePager";
import { useDatasetContextStore } from "@/stores/datasetContext";
import { useRuntimeStore } from "@/stores/runtime";
import {
  formatCompact,
  formatDate,
  formatDateTime,
  formatNumberish,
  formatRmbAmount,
  formatShareVolume,
  getErrorMessage,
  toNumber,
  toStatusTagType,
} from "@/utils/format";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";
import { formatStatusText } from "@/utils/displayText";


const message = useMessage();
const runtime = useRuntimeStore();
const datasetContext = useDatasetContextStore();
const stats = ref<ImportStatsRead | null>(null);
const importRuns = ref<ImportRunRead[]>([]);
const stocks = ref<TradingStockRead[]>([]);
const records = ref<TradingRecordRead[]>([]);
const loading = ref(false);
const loadingPreview = ref(false);
const previewingImport = ref(false);
const committingImport = ref(false);
const deletingRunId = ref<number | null>(null);
const error = ref("");
usePageErrorNotification(error, "数据集页面加载失败");
const selectedFile = ref<File | null>(null);
const importPreview = ref<ImportPreviewRead | null>(null);
const mappingSelections = reactive<Record<string, string | null>>({});
const requiredColumnEnabled = reactive<Record<string, boolean>>({});
const optionalColumnEnabled = reactive<Record<string, boolean>>({});
const mappingModalVisible = ref(false);
const mappingModalTab = ref<"required" | "optional">("required");

const optionalCanonicalColumns = [
  "benchmark_close",
  "amount",
  "turnover",
  "pe_ttm",
  "pb",
  "roe",
  "asset_liability_ratio",
  "revenue_yoy",
  "net_profit_yoy",
  "valuation_as_of",
  "fundamental_report_date",
  "stock_name",
] as const;
const canonicalLabelMap: Record<string, string> = {
  stock_code: "股票代码",
  trade_date: "交易日期",
  open: "开盘价",
  high: "最高价",
  low: "最低价",
  close: "收盘价",
  volume: "成交量",
  benchmark_close: "基准收盘价",
  amount: "成交额",
  turnover: "换手率",
  pe_ttm: "PE(TTM)",
  pb: "PB",
  roe: "ROE",
  asset_liability_ratio: "资产负债率",
  revenue_yoy: "营收同比",
  net_profit_yoy: "净利同比",
  valuation_as_of: "估值时间",
  fundamental_report_date: "报告期",
  stock_name: "股票名称",
};

const workspaceForm = reactive({
  importRunId: undefined as number | undefined,
  stockCode: "",
  startDate: "",
  endDate: "",
  limitInput: "200",
});

const uploadForm = reactive({
  datasetName: "",
});

const currentDataset = computed(
  () => importRuns.value.find((item) => item.id === workspaceForm.importRunId) ?? null
);

const currentDatasetLabel = computed(() => {
  if (!currentDataset.value) {
    return "未选择数据";
  }

  return `#${currentDataset.value.display_id} · ${currentDataset.value.dataset_name}`;
});

const importRunOptions = computed(() =>
  importRuns.value.map((item) => ({
    label: `#${item.display_id} · ${item.dataset_name}`,
    value: item.id,
  }))
);

const stockOptions = computed(() =>
  stocks.value.map((item) => ({
    label: `${item.stock_code}${item.stock_name ? ` · ${item.stock_name}` : ""}`,
    value: item.stock_code,
  }))
);
const hasImportPreview = computed(() => importPreview.value !== null);
const importMappingOptions = computed(() =>
  (importPreview.value?.original_columns ?? []).map((column) => ({ label: column, value: column }))
);
const mappingFieldsByCanonical = computed(() => {
  const output: Record<string, ImportPreviewRead["field_suggestions"][number]> = {};
  for (const field of importPreview.value?.field_suggestions ?? []) {
    output[field.canonical_column] = field;
  }
  return output;
});
const requiredMappingFields = computed(() =>
  (importPreview.value?.required_columns ?? [])
    .map((canonical) => mappingFieldsByCanonical.value[canonical])
    .filter((item): item is ImportPreviewRead["field_suggestions"][number] => Boolean(item))
);
const optionalMappingFields = computed(() =>
  optionalCanonicalColumns
    .map((canonical) => mappingFieldsByCanonical.value[canonical])
    .filter((item): item is ImportPreviewRead["field_suggestions"][number] => Boolean(item))
);
const requiredOffColumns = computed(() =>
  (importPreview.value?.required_columns ?? []).filter((canonical) => {
    return !requiredColumnEnabled[canonical];
  })
);
const unresolvedEnabledRequiredColumns = computed(() =>
  (importPreview.value?.required_columns ?? []).filter((canonical) => {
    if (!requiredColumnEnabled[canonical]) {
      return false;
    }
    const selected = mappingSelections[canonical];
    return !selected;
  })
);
const unresolvedEnabledOptionalColumns = computed(() =>
  optionalCanonicalColumns.filter((canonical) => optionalColumnEnabled[canonical] && !mappingSelections[canonical])
);
const requiredConfirmationAck = computed(
  () =>
    Boolean(importPreview.value?.preview_id) &&
    requiredOffColumns.value.length === 0 &&
    unresolvedEnabledRequiredColumns.value.length === 0
);
const canCommitImport = computed(
  () =>
    Boolean(importPreview.value?.preview_id) &&
    requiredOffColumns.value.length === 0 &&
    unresolvedEnabledRequiredColumns.value.length === 0 &&
    requiredConfirmationAck.value &&
    unresolvedEnabledOptionalColumns.value.length === 0
);
const importRunsPager = useTablePager(importRuns, {
  initialPageSize: 20,
  pageSizes: [10, 20, 50, 100],
});
const recordsScopeKey = computed(
  () =>
    `${workspaceForm.importRunId ?? ""}|${workspaceForm.stockCode}|${workspaceForm.startDate}|${workspaceForm.endDate}`
);
const recordsPager = useTablePager(records, {
  initialPageSize: 20,
  pageSizes: [10, 20, 50, 100],
  resetTriggers: [recordsScopeKey],
});
const startDatePickerValue = computed({
  get: () => workspaceForm.startDate || undefined,
  set: (value: string | null | undefined) => {
    workspaceForm.startDate = value ?? "";
  },
});
const endDatePickerValue = computed({
  get: () => workspaceForm.endDate || undefined,
  set: (value: string | null | undefined) => {
    workspaceForm.endDate = value ?? "";
  },
});

type MappingField = ImportPreviewRead["field_suggestions"][number];

const mappingTableScrollX = 820;
const mappingTableMaxHeight = "min(45vh, 440px)";
const importRunsTableMaxHeight = "min(48vh, 420px)";
const recordsTableMaxHeight = "min(48vh, 420px)";

const requiredMappingColumns: DataTableColumns<MappingField> = [
  {
    title: "目标列",
    key: "canonical_column",
    width: 180,
    render(field) {
      return resolveCanonicalLabel(field.canonical_column);
    },
  },
  {
    title: "建议置信度",
    key: "selected_confidence",
    width: 180,
    render(field) {
      return `${field.selected_confidence}${field.selected_score !== null ? ` (${field.selected_score.toFixed(3)})` : ""}`;
    },
  },
  {
    title: "映射源列",
    key: "mapping",
    width: 320,
    render(field) {
      return h(NSelect, {
        value: mappingSelections[field.canonical_column],
        options: importMappingOptions.value,
        placeholder: "选择源列",
        clearable: true,
        "onUpdate:value": (value: string | null) => {
          mappingSelections[field.canonical_column] = value;
          onRequiredMappingChange(field.canonical_column, value);
        },
      });
    },
  },
  {
    title: "确认导入",
    key: "enabled",
    width: 140,
    render(field) {
      return h(NSwitch, {
        value: requiredColumnEnabled[field.canonical_column],
        disabled: !mappingSelections[field.canonical_column],
        "onUpdate:value": (value: boolean) => {
          requiredColumnEnabled[field.canonical_column] = value;
        },
      });
    },
  },
];

const optionalMappingColumns: DataTableColumns<MappingField> = [
  {
    title: "目标列",
    key: "canonical_column",
    width: 180,
    render(field) {
      return resolveCanonicalLabel(field.canonical_column);
    },
  },
  {
    title: "建议置信度",
    key: "selected_confidence",
    width: 180,
    render(field) {
      return `${field.selected_confidence}${field.selected_score !== null ? ` (${field.selected_score.toFixed(3)})` : ""}`;
    },
  },
  {
    title: "映射源列",
    key: "mapping",
    width: 320,
    render(field) {
      return h(NSelect, {
        value: mappingSelections[field.canonical_column],
        options: importMappingOptions.value,
        placeholder: "选择源列",
        clearable: true,
        "onUpdate:value": (value: string | null) => {
          mappingSelections[field.canonical_column] = value;
        },
      });
    },
  },
  {
    title: "确认导入",
    key: "enabled",
    width: 140,
    render(field) {
      return h(NSwitch, {
        value: optionalColumnEnabled[field.canonical_column],
        "onUpdate:value": (value: boolean) => {
          optionalColumnEnabled[field.canonical_column] = value;
        },
      });
    },
  },
];

const importRunsTableColumns: DataTableColumns<ImportRunRead> = [
  {
    title: "批次",
    key: "display_id",
    width: 110,
    render(item) {
      return `#${item.display_id}`;
    },
  },
  {
    title: "数据",
    key: "dataset_name",
    width: 220,
    ellipsis: {
      tooltip: true,
    },
  },
  {
    title: "状态",
    key: "status",
    width: 130,
    render(item) {
      return h(
        NTag,
        {
          type: toStatusTagType(item.status),
          round: true,
          size: "small",
        },
        { default: () => formatStatusText(item.status) }
      );
    },
  },
  {
    title: "所属用户",
    key: "owner_username",
    width: 150,
    render(item) {
      return item.owner_username || "--";
    },
  },
  {
    title: "记录",
    key: "record_count",
    width: 130,
    render(item) {
      return formatCompact(item.record_count ?? null, 2);
    },
  },
  {
    title: "开始时间",
    key: "started_at",
    width: 210,
    render(item) {
      return formatDateTime(item.started_at);
    },
  },
  {
    title: "操作",
    key: "actions",
    width: 170,
    render(item) {
      return h("div", { class: "toolbar-row datasets-table__actions" }, [
        h(
          NButton,
          {
            text: true,
            type: "primary",
            onClick: () => loadDatasets(item.id, { notify: true, action: "switch" }),
          },
          {
            icon: () => h(NIcon, null, { default: () => h(SwapHorizontalOutline) }),
            default: () => "切换",
          }
        ),
        h(
          NButton,
          {
            text: true,
            type: "error",
            loading: deletingRunId.value === item.id,
            onClick: () => removeRun(item),
          },
          {
            icon: () => h(NIcon, null, { default: () => h(TrashOutline) }),
            default: () => "删除",
          }
        ),
      ]);
    },
  },
];

const importRunsTablePagination = computed(() => ({
  page: importRunsPager.page.value,
  pageSize: importRunsPager.pageSize.value,
  itemCount: importRunsPager.total.value,
  pageSizes: importRunsPager.pageSizes,
  showSizePicker: true,
  onUpdatePage: importRunsPager.setPage,
  onUpdatePageSize: importRunsPager.setPageSize,
}));

const importRunsRowClassName: DataTableCreateRowClassName<ImportRunRead> = (item) =>
  item.id === workspaceForm.importRunId ? "data-table__row--active" : "";

const recordsTableColumns: DataTableColumns<TradingRecordRead> = [
  {
    title: "股票",
    key: "stock_code",
    width: 210,
    render(item) {
      return `${item.stock_code}${item.stock_name ? ` · ${item.stock_name}` : ""}`;
    },
  },
  {
    title: "日期",
    key: "trade_date",
    width: 140,
    render(item) {
      return formatDate(item.trade_date);
    },
  },
  {
    title: "开",
    key: "open",
    width: 110,
    render(item) {
      return formatNumberish(item.open, 2);
    },
  },
  {
    title: "最高",
    key: "high",
    width: 110,
    render(item) {
      return formatNumberish(item.high, 2);
    },
  },
  {
    title: "最低",
    key: "low",
    width: 110,
    render(item) {
      return formatNumberish(item.low, 2);
    },
  },
  {
    title: "收盘",
    key: "close",
    width: 120,
    render(item) {
      return formatNumberish(item.close, 2);
    },
  },
  {
    title: "成交量",
    key: "volume",
    width: 160,
    render(item) {
      return formatShareVolume(item.volume, 2);
    },
  },
  {
    title: "成交额",
    key: "amount",
    width: 160,
    render(item) {
      return formatRmbAmount(item.amount, 2);
    },
  },
];

const recordsTablePagination = computed(() => ({
  page: recordsPager.page.value,
  pageSize: recordsPager.pageSize.value,
  itemCount: recordsPager.total.value,
  pageSizes: recordsPager.pageSizes,
  showSizePicker: true,
  onUpdatePage: recordsPager.setPage,
  onUpdatePageSize: recordsPager.setPageSize,
}));

function getMappingRowKey(field: MappingField) {
  return field.canonical_column;
}

function getImportRunRowKey(item: ImportRunRead) {
  return item.id;
}

function getRecordRowKey(item: TradingRecordRead) {
  return item.id;
}

type FeedbackOptions = {
  notify?: boolean;
};

type DatasetLoadFeedbackOptions = FeedbackOptions & {
  action?: "switch";
};

const historyTitlePills = computed(() => [
  {
    label: "当前可见批次",
    value: String(importRuns.value.length),
  },
]);

const currentDatasetTitlePill = computed(() => ({
  label: "当前股票",
  value: String(stocks.value.length),
}));

const recordsTitlePill = computed(() => ({
  label: "当前样本",
  value: String(records.value.length),
}));

function pickVisibleRunId(runRows: ImportRunRead[], candidates: Array<number | undefined>) {
  for (const candidate of candidates) {
    if (candidate && runRows.some((item) => item.id === candidate)) {
      return candidate;
    }
  }

  return runRows[0]?.id;
}

const previewChartOption = computed<EChartsOption | null>(() => {
  if (!records.value.length) {
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
      left: 52,
      right: 44,
      top: 56,
      bottom: 28,
    },
    xAxis: {
      type: "category",
      data: records.value.map((item) => item.trade_date),
      axisLabel: { color: "#526072" },
    },
    yAxis: [
      {
        type: "value",
        name: "收盘",
        axisLabel: { color: "#526072" },
        splitLine: {
          lineStyle: { color: "rgba(82, 96, 114, 0.12)" },
        },
      },
      {
        type: "value",
        name: "成交",
        axisLabel: { color: "#526072" },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        type: "line",
        name: "收盘",
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 3, color: "#2f6fed" },
        data: records.value.map((item) => toNumber(item.close)),
      },
      {
        type: "bar",
        name: "成交",
        yAxisIndex: 1,
        barMaxWidth: 18,
        itemStyle: {
          color: "#f05a28",
          borderRadius: [6, 6, 0, 0],
        },
        data: records.value.map((item) => toNumber(item.amount)),
      },
    ],
  };
});

function parseLimitInput() {
  const trimmed = workspaceForm.limitInput.trim();
  if (!trimmed) {
    return undefined;
  }

  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error("预览样本数必须是正整数");
  }

  return parsed;
}

function syncWorkspaceFromStore() {
  workspaceForm.importRunId = datasetContext.state.importRunId;
  workspaceForm.stockCode = datasetContext.state.stockCode;
  workspaceForm.startDate = datasetContext.state.startDate;
  workspaceForm.endDate = datasetContext.state.endDate;
  workspaceForm.limitInput = datasetContext.state.sampleLimitInput;
}

function applySharedScope() {
  datasetContext.applyScope({
    importRunId: workspaceForm.importRunId,
    importRunDisplayId: currentDataset.value?.display_id,
    stockCode: workspaceForm.stockCode,
    startDate: workspaceForm.startDate,
    endDate: workspaceForm.endDate,
    sampleLimitInput: workspaceForm.limitInput,
  });
}

function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] ?? null;
  importPreview.value = null;
  mappingModalVisible.value = false;
  mappingModalTab.value = "required";
  for (const key of Object.keys(mappingSelections)) {
    delete mappingSelections[key];
  }
  for (const key of Object.keys(requiredColumnEnabled)) {
    delete requiredColumnEnabled[key];
  }
  for (const key of Object.keys(optionalColumnEnabled)) {
    delete optionalColumnEnabled[key];
  }
}

async function loadPreview(options: FeedbackOptions = {}) {
  if (!workspaceForm.importRunId) {
    records.value = [];
    if (options.notify) {
      message.warning("请先选择导入批次");
    }
    return;
  }

  loadingPreview.value = true;
  error.value = "";

  try {
    const rows = await fetchTradingRecords({
      import_run_id: workspaceForm.importRunId,
      stock_code: workspaceForm.stockCode || undefined,
      start_date: workspaceForm.startDate || undefined,
      end_date: workspaceForm.endDate || undefined,
      limit: parseLimitInput(),
    });
    records.value = rows;
    applySharedScope();
    runtime.markSynced();
    if (options.notify) {
      message.success("范围已应用");
    }
  } catch (err) {
    error.value = getErrorMessage(err);
    records.value = [];
    if (options.notify) {
      message.error(error.value);
    }
  } finally {
    loadingPreview.value = false;
  }
}

async function loadStocks(loadPreviewAfterSync = true) {
  if (!workspaceForm.importRunId) {
    stocks.value = [];
    records.value = [];
    workspaceForm.stockCode = "";
    return;
  }

  try {
    const rows = await fetchTradingStocks(workspaceForm.importRunId);
    stocks.value = rows;

    if (!rows.find((item) => item.stock_code === workspaceForm.stockCode)) {
      workspaceForm.stockCode = rows[0]?.stock_code || "";
    }

    if (loadPreviewAfterSync) {
      await loadPreview();
    }
  } catch (err) {
    error.value = getErrorMessage(err);
    stocks.value = [];
    records.value = [];
  }
}

async function loadDatasets(preferredRunId?: number, options: DatasetLoadFeedbackOptions = {}) {
  loading.value = true;
  error.value = "";

  try {
    const statsResponse = await fetchImportStats();
    const runRows = await fetchImportRuns({
      limit: Math.max(statsResponse.total_runs, 1),
    });

    stats.value = statsResponse;
    importRuns.value = runRows;

    workspaceForm.importRunId = pickVisibleRunId(runRows, [
      preferredRunId,
      workspaceForm.importRunId,
      datasetContext.state.importRunId,
    ]);

    if (!workspaceForm.importRunId) {
      workspaceForm.stockCode = "";
      records.value = [];
      stocks.value = [];
      if (options.notify) {
        message.warning("当前没有可用数据集");
      }
      return;
    }

    await loadStocks(true);
    runtime.markSynced();
    if (options.notify && !error.value) {
      if (options.action === "switch") {
        message.success(`已切换到批次 #${currentDataset.value?.display_id ?? preferredRunId}`);
      } else {
        message.success("数据集已刷新");
      }
    } else if (options.notify && error.value) {
      message.error(error.value);
    }
  } catch (err) {
    error.value = getErrorMessage(err);
    if (options.notify) {
      message.error(error.value);
    }
  } finally {
    loading.value = false;
  }
}

function applyPreviewSuggestedMapping(preview: ImportPreviewRead) {
  for (const key of Object.keys(mappingSelections)) {
    delete mappingSelections[key];
  }
  for (const key of Object.keys(requiredColumnEnabled)) {
    delete requiredColumnEnabled[key];
  }
  for (const key of Object.keys(optionalColumnEnabled)) {
    delete optionalColumnEnabled[key];
  }
  for (const [canonical, original] of Object.entries(preview.suggested_mapping)) {
    mappingSelections[canonical] = original;
  }
  for (const canonical of preview.required_columns) {
    if (!(canonical in mappingSelections)) {
      mappingSelections[canonical] = null;
    }
  }
  for (const canonical of preview.optional_columns) {
    if (!(canonical in mappingSelections)) {
      mappingSelections[canonical] = null;
    }
  }
  const requiredIssueSet = new Set(preview.required_issue_columns);
  for (const requiredColumn of preview.required_columns) {
    const hasIssue = requiredIssueSet.has(requiredColumn);
    if (hasIssue) {
      mappingSelections[requiredColumn] = null;
      requiredColumnEnabled[requiredColumn] = false;
    } else {
      requiredColumnEnabled[requiredColumn] = Boolean(mappingSelections[requiredColumn]);
    }
  }
  for (const optionalColumn of optionalCanonicalColumns) {
    optionalColumnEnabled[optionalColumn] = false;
  }
}

function resolveCanonicalLabel(canonical: string) {
  return canonicalLabelMap[canonical] ?? canonical;
}

function openMappingModal(mode: "auto" | "manual") {
  if (!importPreview.value) {
    error.value = "请先执行列头解析";
    message.warning(error.value);
    return;
  }
  if (mode === "auto") {
    mappingModalTab.value = "required";
  } else {
    mappingModalTab.value = "optional";
  }
  mappingModalVisible.value = true;
}

function setAllOptionalColumns(enabled: boolean) {
  for (const optionalColumn of optionalCanonicalColumns) {
    optionalColumnEnabled[optionalColumn] = enabled;
  }
}

function setAllRequiredColumns(enabled: boolean) {
  for (const requiredColumn of importPreview.value?.required_columns ?? []) {
    if (!mappingSelections[requiredColumn]) {
      requiredColumnEnabled[requiredColumn] = false;
      continue;
    }
    requiredColumnEnabled[requiredColumn] = enabled;
  }
}

function onRequiredMappingChange(canonical: string, value: string | null) {
  if (!value) {
    requiredColumnEnabled[canonical] = false;
  }
}

async function submitPreview() {
  if (!selectedFile.value) {
    error.value = "请先选择要上传的 CSV / XLSX 文件";
    message.warning(error.value);
    return;
  }

  if (!uploadForm.datasetName.trim()) {
    error.value = "请先填写数据集名称";
    message.warning(error.value);
    return;
  }

  previewingImport.value = true;
  error.value = "";

  try {
    const preview = await previewTradingFile({
      dataset_name: uploadForm.datasetName.trim(),
      file: selectedFile.value,
    });
    importPreview.value = preview;
    applyPreviewSuggestedMapping(preview);
    if (preview.required_confirmation_needed) {
      openMappingModal("auto");
      message.warning("必要列存在冲突或低置信问题，请手动选择并开启对应必要列。");
    } else if (preview.can_auto_commit) {
      message.success("列头识别完成，可一键确认导入。");
    } else {
      message.warning("列头识别完成，如需自定义映射请打开“列头映射”弹窗。");
    }
  } catch (err) {
    error.value = getErrorMessage(err);
    message.error(error.value);
  } finally {
    previewingImport.value = false;
  }
}

async function submitCommit() {
  if (!importPreview.value) {
    error.value = "请先执行列头解析";
    message.warning(error.value);
    return;
  }
  if (!canCommitImport.value) {
    if (requiredOffColumns.value.length) {
      error.value = `必要列必须全部开启后才可导入：${requiredOffColumns.value.join("、")}`;
    } else if (unresolvedEnabledRequiredColumns.value.length) {
      error.value = `请先补齐已开启必要列映射：${unresolvedEnabledRequiredColumns.value.join("、")}`;
    } else {
      error.value = `请先补齐已开启的可选列映射：${unresolvedEnabledOptionalColumns.value.join("、")}`;
    }
    message.warning(error.value);
    return;
  }

  committingImport.value = true;
  error.value = "";
  try {
    const mappingOverrides: Record<string, string | null> = {};
    for (const canonical of importPreview.value.required_columns) {
      mappingOverrides[canonical] = requiredColumnEnabled[canonical] ? (mappingSelections[canonical] ?? null) : null;
    }
    for (const canonical of optionalCanonicalColumns) {
      if (optionalColumnEnabled[canonical]) {
        mappingOverrides[canonical] = mappingSelections[canonical] ?? null;
      }
    }
    const createdRun = await commitTradingPreview({
      preview_id: importPreview.value.preview_id,
      required_confirmation_ack: requiredConfirmationAck.value,
      mapping_overrides: mappingOverrides,
    });
    uploadForm.datasetName = "";
    selectedFile.value = null;
    importPreview.value = null;
    mappingModalVisible.value = false;
    mappingModalTab.value = "required";
    for (const key of Object.keys(mappingSelections)) {
      delete mappingSelections[key];
    }
    for (const key of Object.keys(requiredColumnEnabled)) {
      delete requiredColumnEnabled[key];
    }
    for (const key of Object.keys(optionalColumnEnabled)) {
      delete optionalColumnEnabled[key];
    }
    message.success(`已创建导入批次 #${createdRun.display_id}`);
    await loadDatasets(createdRun.id);
  } catch (err) {
    error.value = getErrorMessage(err);
    message.error(error.value);
  } finally {
    committingImport.value = false;
  }
}

async function removeRun(run: ImportRunRead) {
  if (!window.confirm(`确认删除数据集批次 #${run.display_id} 吗？`)) {
    return;
  }

  deletingRunId.value = run.id;
  error.value = "";

  try {
    await deleteImportRun(run.id);
    message.success(`已删除批次 #${run.display_id}`);

    if (workspaceForm.importRunId === run.id) {
      datasetContext.resetScope();
      syncWorkspaceFromStore();
    }

    await loadDatasets();
  } catch (err) {
    error.value = getErrorMessage(err);
    message.error(error.value);
  } finally {
    deletingRunId.value = null;
  }
}

async function handleDatasetChange() {
  await loadStocks(true);
}

onMounted(() => {
  syncWorkspaceFromStore();
  void loadDatasets(datasetContext.state.importRunId);
});

watch(
  () => datasetContext.state.appliedRevision,
  () => {
    syncWorkspaceFromStore();
    void loadDatasets(workspaceForm.importRunId);
  }
);
</script>

<template>
  <div class="page">
    <section class="page__grid dataset-layout-section">
      <PanelCard class="dataset-card dataset-card--upload" title="上传新数据集">
        <n-form label-placement="top">
          <n-grid :x-gap="16" :y-gap="0" cols="1" responsive="screen">
            <n-form-item-gi label="数据集名">
              <n-input v-model:value="uploadForm.datasetName" placeholder="例如 2024 全市场日线数据" />
            </n-form-item-gi>
            <n-form-item-gi label="交易文件">
              <input type="file" accept=".csv,.xlsx,.xls" @change="onFileSelected" />
            </n-form-item-gi>
          </n-grid>
        </n-form>

        <div class="inline-hint">请先解析列头，再确认映射并提交导入。系统会自动给出建议映射，必要时可手动调整。</div>

        <div class="toolbar-row upload-actions" style="margin-top: 16px;">
          <n-button type="primary" :loading="previewingImport" @click="submitPreview">解析列头</n-button>
          <n-button secondary :disabled="!hasImportPreview" @click="openMappingModal('manual')">列头映射</n-button>
          <n-button
            type="primary"
            secondary
            :loading="committingImport"
            :disabled="!hasImportPreview || !canCommitImport"
            @click="submitCommit"
          >
            确认导入
          </n-button>
          <span class="muted">{{ selectedFile?.name || "尚未选择文件" }}</span>
        </div>

        <div v-if="importPreview" class="upload-preview-panel">
          <div class="inline-hint" style="margin-top: 12px;">预览编号：{{ importPreview.preview_id }}</div>
          <div class="inline-hint" style="margin-top: 8px;">
            {{ importPreview.action_hints.join("；") }}
          </div>
          <div v-if="importPreview.conflicts.length" class="inline-hint" style="margin-top: 8px; color: #b45309;">
            冲突：{{ importPreview.conflicts.map((item) => item.message).join("；") }}
          </div>
          <div v-if="requiredOffColumns.length" class="inline-hint" style="margin-top: 8px; color: #be123c;">
            未开启必要列：{{ requiredOffColumns.join("、") }}
          </div>
          <div v-if="unresolvedEnabledRequiredColumns.length" class="inline-hint" style="margin-top: 8px; color: #be123c;">
            必要列映射未完成：{{ unresolvedEnabledRequiredColumns.join("、") }}
          </div>
        </div>
      </PanelCard>
    </section>

    <n-modal
      v-model:show="mappingModalVisible"
      preset="card"
      title="列头映射确认"
      style="width: min(980px, 92vw);"
    >
      <template v-if="importPreview">
        <div class="inline-hint">
          必要列有问题时会自动打开此弹窗；你也可以随时手动打开进行自定义映射。
        </div>
        <n-tabs v-model:value="mappingModalTab" type="line" animated style="margin-top: 12px;">
          <n-tab-pane name="required" tab="必要列映射">
            <div class="toolbar-row" style="margin-bottom: 12px;">
              <span class="muted">
                状态：{{ requiredOffColumns.length === 0 && unresolvedEnabledRequiredColumns.length === 0 ? "可提交" : "待确认" }}
              </span>
              <n-button size="small" secondary @click="setAllRequiredColumns(true)">全开</n-button>
              <n-button size="small" secondary @click="setAllRequiredColumns(false)">全关</n-button>
            </div>
            <n-data-table
              class="mapping-data-table"
              :columns="requiredMappingColumns"
              :data="requiredMappingFields"
              :row-key="getMappingRowKey"
              :max-height="mappingTableMaxHeight"
              :scroll-x="mappingTableScrollX"
              :scrollbar-props="{ trigger: 'none' }"
              :single-line="false"
              striped
              size="small"
            />
          </n-tab-pane>
          <n-tab-pane name="optional" tab="可选列映射">
            <div class="toolbar-row" style="margin-bottom: 12px;">
              <n-button size="small" secondary @click="setAllOptionalColumns(true)">全开</n-button>
              <n-button size="small" secondary @click="setAllOptionalColumns(false)">全关</n-button>
            </div>
            <n-data-table
              class="mapping-data-table"
              :columns="optionalMappingColumns"
              :data="optionalMappingFields"
              :row-key="getMappingRowKey"
              :max-height="mappingTableMaxHeight"
              :scroll-x="mappingTableScrollX"
              :scrollbar-props="{ trigger: 'none' }"
              :single-line="false"
              striped
              size="small"
            />
          </n-tab-pane>
        </n-tabs>
        <div class="mapping-modal-actions">
          <n-button @click="mappingModalVisible = false">取消</n-button>
          <n-button
            type="primary"
            :loading="committingImport"
            :disabled="!canCommitImport"
            @click="submitCommit"
          >
            确认导入
          </n-button>
        </div>
      </template>
    </n-modal>

    <section class="page__grid dataset-layout-section">
      <PanelCard class="dataset-card dataset-card--summary" title="当前数据集摘要">
        <template #title>
          <span class="page-card__title">
            <span>当前数据集摘要</span>
            <span class="page-card__stats">
              <span class="pill page-card__pill">
                {{ currentDatasetTitlePill.label }} {{ currentDatasetTitlePill.value }}
              </span>
            </span>
          </span>
        </template>
        <div v-if="currentDataset" class="detail-grid">
          <div class="detail-grid__item">
            <span class="detail-grid__label">批次</span>
            <div class="detail-grid__value">#{{ currentDataset.display_id }}</div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">文件来源</span>
            <div class="detail-grid__value">{{ currentDataset.original_file_name || currentDataset.source_name }}</div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">记录规模</span>
            <div class="detail-grid__value">{{ formatCompact(currentDataset.record_count ?? null, 2) }}</div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">完成时间</span>
            <div class="detail-grid__value">{{ formatDateTime(currentDataset.completed_at || currentDataset.started_at) }}</div>
          </div>
        </div>
        <EmptyState
          v-else
          title="暂无当前数据"
          description="请选择一个有效批次，或先上传新的交易文件"
        />
      </PanelCard>

      <PanelCard class="dataset-card dataset-card--sample" title="样本预览">
        <EChartPanel v-if="previewChartOption" :option="previewChartOption" :loading="loadingPreview" height="320px" />
        <EmptyState
          v-else
          title="暂无样本图表"
          description="选定批次后，这里会展示当前筛选范围的收盘价与成交额"
        />
      </PanelCard>
    </section>

    <PanelCard title="导入历史">
      <template #title>
        <span class="page-card__title">
          <span>导入历史</span>
          <span class="page-card__stats">
            <span v-for="item in historyTitlePills" :key="item.label" class="pill page-card__pill">
              {{ item.label }} {{ item.value }}
            </span>
          </span>
        </span>
      </template>
      <n-data-table
        v-if="importRunsPager.total.value"
        class="datasets-data-table"
        :columns="importRunsTableColumns"
        :data="importRuns"
        :pagination="importRunsTablePagination"
        :row-class-name="importRunsRowClassName"
        :row-key="getImportRunRowKey"
        :max-height="importRunsTableMaxHeight"
        :single-line="false"
        striped
        size="small"
      />
      <EmptyState
        v-else
        title="暂无导入历史"
        description="完成首次导入后，这里会显示当前可见范围内的全部批次"
      />
    </PanelCard>

    <PanelCard title="交易样本">
      <template #title>
        <span class="page-card__title">
          <span>交易样本</span>
          <span class="page-card__stats">
            <span class="pill page-card__pill">
              {{ recordsTitlePill.label }} {{ recordsTitlePill.value }}
            </span>
          </span>
        </span>
      </template>
      <n-data-table
        v-if="recordsPager.total.value"
        class="datasets-data-table"
        :columns="recordsTableColumns"
        :data="records"
        :pagination="recordsTablePagination"
        :row-key="getRecordRowKey"
        :max-height="recordsTableMaxHeight"
        :single-line="false"
        striped
        size="small"
      />
      <EmptyState
        v-else
        title="暂无样本记录"
        description="选择有效批次后，这里会展示当前范围的交易记录样本"
      />
    </PanelCard>
  </div>
</template>

<style scoped>
.page {
  display: grid;
  grid-template-columns: repeat(2, minmax(320px, 1fr));
  gap: 20px;
}

.dataset-layout-section {
  display: contents;
}

.dataset-card--summary {
  order: 1;
}

.dataset-card--upload {
  order: 2;
}

.dataset-card--sample {
  order: 3;
  grid-column: 1 / -1;
}

.page > :deep(.panel-card:not(.dataset-card)) {
  order: 4;
  grid-column: 1 / -1;
}

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

.upload-actions {
  gap: 16px;
  row-gap: 10px;
}

.mapping-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 16px;
  margin-top: 16px;
  border-top: 1px solid rgba(148, 163, 184, 0.24);
}

.mapping-data-table,
.datasets-data-table {
  border-radius: 18px;
  overflow: visible;
}

:deep(.mapping-data-table .n-data-table-th),
:deep(.datasets-data-table .n-data-table-th) {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  white-space: nowrap;
}

:deep(.mapping-data-table .n-data-table-td),
:deep(.datasets-data-table .n-data-table-td) {
  vertical-align: top;
}

:deep(.datasets-data-table .n-data-table__pagination) {
  padding: 0 12px 10px;
  border-top: 1px solid var(--panel-border);
  background: #fff;
}

.datasets-table__actions {
  flex-wrap: nowrap;
}

@media (max-width: 760px) {
  .page {
    grid-template-columns: 1fr;
  }
}
</style>
