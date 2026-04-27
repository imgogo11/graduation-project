<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";

import {
  NAlert,
  NButton,
  NDatePicker,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NSpace,
  useMessage,
} from "naive-ui";

import { fetchImportRuns, fetchImportStats } from "@/api/imports";
import { fetchTradingStocks } from "@/api/trading";
import type { ImportRunRead, TradingStockRead } from "@/api/types";
import { useDatasetContextStore } from "@/stores/datasetContext";
import { getErrorMessage } from "@/utils/format";

const props = defineProps<{
  show: boolean;
}>();

const emit = defineEmits<{
  "update:show": [value: boolean];
}>();

const datasetContext = useDatasetContextStore();
const message = useMessage();
const loadingRuns = ref(false);
const loadingStocks = ref(false);
const error = ref("");
const importRuns = ref<ImportRunRead[]>([]);
const stocks = ref<TradingStockRead[]>([]);

const draft = reactive({
  importRunId: undefined as number | undefined,
  stockCode: "",
  startDate: "",
  endDate: "",
  sampleLimitInput: "200",
  crossMetric: "total_return",
  topNInput: "10",
  correlationStockCodes: [] as string[],
  kInput: "1",
  kthMethod: "persistent_segment_tree" as "persistent_segment_tree" | "t_digest",
  jointTopNInput: "20",
  severity: "",
  eventTopNInput: "50",
});

const drawerVisible = computed({
  get: () => props.show,
  set: (value: boolean) => emit("update:show", value),
});

const importRunOptions = computed(() =>
  importRuns.value.map((item) => ({ label: `#${item.display_id} · ${item.dataset_name}`, value: item.id }))
);
const currentImportRun = computed(() => importRuns.value.find((item) => item.id === draft.importRunId) ?? null);
const stockOptions = computed(() =>
  stocks.value.map((item) => ({ label: `${item.stock_code}${item.stock_name ? ` · ${item.stock_name}` : ""}`, value: item.stock_code }))
);
const startDatePickerValue = computed({
  get: () => draft.startDate || undefined,
  set: (value: string | null | undefined) => {
    draft.startDate = value ?? "";
  },
});
const endDatePickerValue = computed({
  get: () => draft.endDate || undefined,
  set: (value: string | null | undefined) => {
    draft.endDate = value ?? "";
  },
});
const crossMetricOptions = [
  { label: "区间收益", value: "total_return" },
  { label: "波动", value: "volatility" },
  { label: "成交量", value: "total_volume" },
  { label: "成交额", value: "total_amount" },
  { label: "平均振幅", value: "average_amplitude" },
];
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

function collapseDateQuickJumpPanel(event: MouseEvent) {
  const target = event.target as HTMLElement | null;
  const item = target?.closest(".n-date-panel-month-calendar__picker-col-item");
  if (!item) {
    return;
  }

  const itemText = item.textContent?.trim() ?? "";
  const isMonthItem = /^(?:[1-9]|1[0-2])月?$/.test(itemText);
  if (!isMonthItem) {
    return;
  }

  window.setTimeout(() => {
    const activeHeader = document.querySelector<HTMLElement>(".n-date-panel-month__text--active");
    activeHeader?.click();
  }, 80);
}

function syncDraftFromContext() {
  draft.importRunId = datasetContext.state.importRunId;
  draft.stockCode = datasetContext.state.stockCode;
  draft.startDate = datasetContext.state.startDate;
  draft.endDate = datasetContext.state.endDate;
  draft.sampleLimitInput = datasetContext.state.sampleLimitInput;
  draft.crossMetric = datasetContext.state.crossMetric;
  draft.topNInput = datasetContext.state.topNInput;
  draft.correlationStockCodes = [...datasetContext.state.correlationStockCodes];
  draft.kInput = datasetContext.state.kInput;
  draft.kthMethod = datasetContext.state.kthMethod;
  draft.jointTopNInput = datasetContext.state.jointTopNInput;
  draft.severity = datasetContext.state.severity;
  draft.eventTopNInput = datasetContext.state.eventTopNInput;
}

function pickVisibleRunId(candidates: Array<number | undefined>) {
  return candidates.find((candidate) => candidate !== undefined && importRuns.value.some((item) => item.id === candidate)) ?? importRuns.value[0]?.id;
}

async function loadStocks() {
  if (!draft.importRunId) {
    stocks.value = [];
    draft.stockCode = "";
    return;
  }

  loadingStocks.value = true;
  try {
    const rows = await fetchTradingStocks(draft.importRunId);
    stocks.value = rows;
    if (!rows.some((item) => item.stock_code === draft.stockCode)) {
      draft.stockCode = rows[0]?.stock_code || "";
    }
    if (!draft.correlationStockCodes.length) {
      draft.correlationStockCodes = rows.slice(0, 6).map((item) => item.stock_code);
    } else {
      draft.correlationStockCodes = draft.correlationStockCodes.filter((code) => rows.some((item) => item.stock_code === code));
    }
  } finally {
    loadingStocks.value = false;
  }
}

async function loadRuns() {
  loadingRuns.value = true;
  error.value = "";
  try {
    syncDraftFromContext();
    const statsResponse = await fetchImportStats();
    importRuns.value = await fetchImportRuns({ limit: Math.max(statsResponse.total_runs, 1) });
    draft.importRunId = pickVisibleRunId([draft.importRunId]);
    await loadStocks();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loadingRuns.value = false;
  }
}

async function handleRunChange() {
  error.value = "";
  try {
    await loadStocks();
  } catch (err) {
    error.value = getErrorMessage(err);
  }
}

function applyFilters() {
  if (!draft.importRunId || !draft.stockCode) {
    message.warning("请先选择批次和股票");
    return;
  }

  datasetContext.applyScope(
    {
      importRunId: draft.importRunId,
      importRunDisplayId: currentImportRun.value?.display_id,
      stockCode: draft.stockCode,
      startDate: draft.startDate,
      endDate: draft.endDate,
      sampleLimitInput: draft.sampleLimitInput,
      crossMetric: draft.crossMetric,
      topNInput: draft.topNInput,
      correlationStockCodes: draft.correlationStockCodes,
      kInput: draft.kInput,
      kthMethod: draft.kthMethod,
      jointTopNInput: draft.jointTopNInput,
      severity: draft.severity,
      eventTopNInput: draft.eventTopNInput,
    },
    { commit: true }
  );
  drawerVisible.value = false;
  message.success("筛选范围已应用");
}

watch(
  () => props.show,
  (show) => {
    if (show) {
      void loadRuns();
    }
  }
);

onMounted(() => {
  document.addEventListener("click", collapseDateQuickJumpPanel, true);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", collapseDateQuickJumpPanel, true);
});
</script>

<template>
  <n-drawer v-model:show="drawerVisible" :width="460" placement="right">
    <n-drawer-content title="筛选器" closable>
      <div class="filter-drawer">
        <n-alert v-if="error" type="error" :show-icon="true">{{ error }}</n-alert>

        <n-form label-placement="top">
          <section class="filter-drawer__section">
            <div class="filter-drawer__section-title">共享范围</div>
            <n-form-item label="批次">
              <n-select v-model:value="draft.importRunId" :loading="loadingRuns" :options="importRunOptions" @update:value="handleRunChange" />
            </n-form-item>
            <n-form-item label="股票">
              <n-select v-model:value="draft.stockCode" :loading="loadingStocks" :options="stockOptions" />
            </n-form-item>
            <n-form-item label="样本数">
              <n-input v-model:value="draft.sampleLimitInput" placeholder="默认 200" />
            </n-form-item>
            <div class="filter-drawer__grid">
              <n-form-item label="开始日期">
                <n-date-picker v-model:formatted-value="startDatePickerValue" type="date" value-format="yyyy-MM-dd" clearable />
              </n-form-item>
              <n-form-item label="结束日期">
                <n-date-picker v-model:formatted-value="endDatePickerValue" type="date" value-format="yyyy-MM-dd" clearable />
              </n-form-item>
            </div>
          </section>

          <section class="filter-drawer__section">
            <div class="filter-drawer__section-title">分析中心</div>
            <n-form-item label="横截面指标">
              <n-select v-model:value="draft.crossMetric" :options="crossMetricOptions" />
            </n-form-item>
            <n-form-item label="横截面前N(Top N)">
              <n-input v-model:value="draft.topNInput" placeholder="留空表示返回全部结果" />
            </n-form-item>
            <n-form-item label="相关性股票">
              <n-select v-model:value="draft.correlationStockCodes" :options="stockOptions" multiple clearable placeholder="建议不超过 6 只股票" />
            </n-form-item>
          </section>

          <section class="filter-drawer__section">
            <div class="filter-drawer__section-title">算法雷达</div>
            <div class="filter-drawer__grid">
              <n-form-item label="K 值">
                <n-input v-model:value="draft.kInput" placeholder="区间第 K 大成交量" />
              </n-form-item>
              <n-form-item label="K 算法">
                <n-select v-model:value="draft.kthMethod" :options="kthMethodOptions" />
              </n-form-item>
            </div>
            <n-form-item label="联合异常前N(Top N)">
              <n-input v-model:value="draft.jointTopNInput" placeholder="默认 20" />
            </n-form-item>
            <div class="filter-drawer__grid">
              <n-form-item label="事件严重">
                <n-select v-model:value="draft.severity" :options="severityOptions" />
              </n-form-item>
              <n-form-item label="事件前N(Top N)">
                <n-input v-model:value="draft.eventTopNInput" placeholder="默认 50" />
              </n-form-item>
            </div>
          </section>
        </n-form>
      </div>

      <template #footer>
        <n-space justify="end">
          <n-button @click="drawerVisible = false">取消</n-button>
          <n-button type="primary" :loading="loadingRuns || loadingStocks" @click="applyFilters">应用范围</n-button>
        </n-space>
      </template>
    </n-drawer-content>
  </n-drawer>
</template>

<style scoped>
.filter-drawer {
  display: grid;
  gap: 18px;
}

.filter-drawer__section {
  display: grid;
  gap: 2px;
}

.filter-drawer__section + .filter-drawer__section {
  padding-top: 16px;
  border-top: 1px solid var(--panel-border);
}

.filter-drawer__section-title {
  margin-bottom: 10px;
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 800;
}

.filter-drawer__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.filter-drawer :deep(.n-date-picker) {
  width: 100%;
}

@media (max-width: 640px) {
  .filter-drawer__grid {
    grid-template-columns: 1fr;
  }
}
</style>
