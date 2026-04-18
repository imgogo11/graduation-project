<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import type { EChartsOption } from "echarts";
import { NButton, NForm, NFormItem, NInput, NPagination, NSelect, NTable, NTag, useMessage } from "naive-ui";

import { deleteImportRun, fetchImportRuns, fetchImportStats, uploadTradingFile } from "@/api/imports";
import { fetchTradingRecords, fetchTradingStocks } from "@/api/trading";
import type {
  ImportRunRead,
  ImportStatsRead,
  TradingRecordRead,
  TradingStockRead,
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
import {
  formatCompact,
  formatDate,
  formatDateTime,
  formatNumberish,
  getErrorMessage,
  toNumber,
  toStatusTagType,
} from "@/utils/format";
import { usePageErrorNotification } from "@/composables/usePageErrorNotification";


const message = useMessage();
const runtime = useRuntimeStore();
const auth = useAuthStore();
const datasetContext = useDatasetContextStore();
const stats = ref<ImportStatsRead | null>(null);
const importRuns = ref<ImportRunRead[]>([]);
const stocks = ref<TradingStockRead[]>([]);
const records = ref<TradingRecordRead[]>([]);
const loading = ref(false);
const loadingPreview = ref(false);
const uploading = ref(false);
const deletingRunId = ref<number | null>(null);
const error = ref("");
usePageErrorNotification(error, "Dataset Page Error");
const selectedFile = ref<File | null>(null);
const ownerFilterInput = ref("");

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

const appliedOwnerUserId = computed(() => {
  if (!auth.isAdmin.value) {
    return undefined;
  }

  const parsed = Number(ownerFilterInput.value.trim());
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
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
const importRunsPager = useTablePager(importRuns, {
  initialPageSize: 20,
  pageSizes: [10, 20, 50, 100],
  resetTriggers: [appliedOwnerUserId],
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

const summaryCards = computed(() => [
  {
    label: "当前可见批次",
    value: String(importRuns.value.length),
    hint: auth.isAdmin.value ? "会受到管理员 owner 过滤条件影响" : "当前账号可见的数据集批次",
    tone: "teal" as const,
  },
  {
    label: "当前股票",
    value: String(stocks.value.length),
    hint: currentDataset.value ? currentDatasetLabel.value : "先选择一个批次",
    tone: "orange" as const,
  },
  {
    label: "当前样本",
    value: String(records.value.length),
    hint: workspaceForm.stockCode || "当前筛选范围内的记录样本",
    tone: "berry" as const,
  },
  {
    label: "可用数据",
    value: String(stats.value?.available_datasets ?? 0),
    hint: "成功且未删除的数据集数量",
    tone: "neutral" as const,
  },
]);

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
}

function applySharedScope() {
  datasetContext.applyScope({
    importRunId: workspaceForm.importRunId,
    stockCode: workspaceForm.stockCode,
    startDate: workspaceForm.startDate,
    endDate: workspaceForm.endDate,
  });
}

function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] ?? null;
}

async function loadPreview() {
  if (!workspaceForm.importRunId) {
    records.value = [];
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
  } catch (err) {
    error.value = getErrorMessage(err);
    records.value = [];
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

async function loadDatasets(preferredRunId?: number) {
  loading.value = true;
  error.value = "";

  try {
    const statsResponse = await fetchImportStats({ owner_user_id: appliedOwnerUserId.value });
    const runRows = await fetchImportRuns({
      limit: Math.max(statsResponse.total_runs, 1),
      owner_user_id: appliedOwnerUserId.value,
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
      return;
    }

    await loadStocks(true);
    runtime.markSynced();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loading.value = false;
  }
}

async function submitUpload() {
  if (!selectedFile.value) {
    error.value = "请先选择要上传的 CSV / XLSX 文件";
    return;
  }

  if (!uploadForm.datasetName.trim()) {
    error.value = "请先填写数据集名称";
    return;
  }

  uploading.value = true;
  error.value = "";

  try {
    const createdRun = await uploadTradingFile({
      dataset_name: uploadForm.datasetName.trim(),
      file: selectedFile.value,
    });
    uploadForm.datasetName = "";
    selectedFile.value = null;
    message.success(`已创建导入批次 #${createdRun.display_id}`);
    await loadDatasets(createdRun.id);
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    uploading.value = false;
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
</script>

<template>
  <div class="page">
    <section class="page__header">
      <div>
        <div class="page__eyebrow">Datasets / 数据集管理</div>
        <h2 class="page__title">导入批次、共享范围与交易样本预览统一收口到数据集管理</h2>
        <p class="page__subtitle">
          这一页负责上传数据、切换当前数据集、预览交易样本，并让后续分析页面复用同一套共享上下文。
        </p>
      </div>
      <div class="page__actions">
        <n-button :loading="loading" @click="loadDatasets(workspaceForm.importRunId)">刷新数据</n-button>
        <n-button type="primary" :loading="loadingPreview" @click="loadPreview">刷新预览</n-button>
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
      <PanelCard title="共享范围设置" description="当前选择会同步到分析中心和算法雷达">
        <n-form class="form-grid" label-placement="top">
          <n-form-item label="导入批次">
            <n-select
              v-model:value="workspaceForm.importRunId"
              :options="importRunOptions"
              placeholder="选择导入批次"
              @update:value="handleDatasetChange"
            />
          </n-form-item>
          <n-form-item v-if="auth.isAdmin.value" label="Owner 用户 ID">
            <n-input v-model:value="ownerFilterInput" placeholder="留空表示全部用户，仅管理员可用" />
          </n-form-item>
          <n-form-item label="股票">
            <n-select
              v-model:value="workspaceForm.stockCode"
              :options="stockOptions"
              placeholder="留空表示全部股票"
              clearable
              @update:value="loadPreview"
            />
          </n-form-item>
          <n-form-item label="样本上限">
            <n-input v-model:value="workspaceForm.limitInput" placeholder="默认 200" />
          </n-form-item>
          <n-form-item label="开始日期">
            <DateInputField v-model="workspaceForm.startDate" clearable />
          </n-form-item>
          <n-form-item label="结束日期">
            <DateInputField v-model="workspaceForm.endDate" clearable />
          </n-form-item>
        </n-form>

        <div class="toolbar-row" style="margin-top: 8px;">
          <span class="pill">{{ currentDatasetLabel }}</span>
          <span class="pill">范围：{{ workspaceForm.startDate || "起始不限" }} ~ {{ workspaceForm.endDate || "结束不限" }}</span>
          <n-button type="primary" :loading="loadingPreview" @click="loadPreview">应用范围</n-button>
          <n-button v-if="auth.isAdmin.value" secondary @click="loadDatasets(workspaceForm.importRunId)">应用 owner 过滤</n-button>
        </div>
      </PanelCard>

      <PanelCard title="上传新数据集" description="保持现有后端导入接口，只重做前端交互">
        <n-form class="form-grid" label-placement="top">
          <n-form-item label="数据集名" class="form-grid--wide">
            <n-input v-model:value="uploadForm.datasetName" placeholder="例如 2024 全市场日线数据" />
          </n-form-item>
          <n-form-item label="交易文件" class="form-grid--wide">
            <input type="file" accept=".csv,.xlsx,.xls" @change="onFileSelected" />
          </n-form-item>
        </n-form>

        <div class="inline-hint">
          当前支持直接沿用现有的导入接口，上传完成后，新的批次会自动刷新并作为当前范围。
        </div>

        <div class="toolbar-row" style="margin-top: 16px;">
          <n-button type="primary" :loading="uploading" @click="submitUpload">上传并导入</n-button>
          <span class="muted">{{ selectedFile?.name || "尚未选择文件" }}</span>
        </div>
      </PanelCard>
    </section>

    <section class="page__grid page__grid--double">
      <PanelCard title="当前数据集摘要" description="优先展示当前批次的元数据与范围信息">
        <div v-if="currentDataset" class="detail-grid">
          <div class="detail-grid__item">
            <span class="detail-grid__label">批次</span>
            <div class="detail-grid__value">#{{ currentDataset.display_id }}</div>
          </div>
          <div class="detail-grid__item">
            <span class="detail-grid__label">状态</span>
            <div class="detail-grid__value">
              <n-tag :type="toStatusTagType(currentDataset.status)" round>{{ currentDataset.status }}</n-tag>
            </div>
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
            <span class="detail-grid__label">Owner</span>
            <div class="detail-grid__value">{{ currentDataset.owner_username || "--" }}</div>
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

      <PanelCard title="样本预览" description="用当前样本快速确认价格与成交额走势是否正常">
        <EChartPanel v-if="previewChartOption" :option="previewChartOption" :loading="loadingPreview" height="320px" />
        <EmptyState
          v-else
          title="暂无样本图表"
          description="选定批次后刷新预览，这里会展示当前筛选范围的收盘价与成交额"
        />
      </PanelCard>
    </section>

    <PanelCard title="导入历史" description="保留导入历史查看与删除能力，管理员可结合 owner 过滤进行巡检">
      <div v-if="importRunsPager.total.value" class="data-table-wrap">
        <n-table class="data-table" striped size="small" :single-line="false">
          <thead>
            <tr>
              <th>批次</th>
              <th>数据</th>
              <th>状态</th>
              <th>Owner</th>
              <th>记录</th>
              <th>开始时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in importRunsPager.pagedRows.value"
              :key="item.id"
              :class="{ 'data-table__row--active': item.id === workspaceForm.importRunId }"
            >
              <td>#{{ item.display_id }}</td>
              <td>{{ item.dataset_name }}</td>
              <td>
                <n-tag :type="toStatusTagType(item.status)" round size="small">{{ item.status }}</n-tag>
              </td>
              <td>{{ item.owner_username || "--" }}</td>
              <td>{{ formatCompact(item.record_count ?? null, 2) }}</td>
              <td>{{ formatDateTime(item.started_at) }}</td>
              <td>
                <div class="toolbar-row">
                  <n-button text type="primary" @click="loadDatasets(item.id)">切换</n-button>
                  <n-button
                    text
                    type="error"
                    :loading="deletingRunId === item.id"
                    @click="removeRun(item)"
                  >
                    删除
                  </n-button>
                </div>
              </td>
            </tr>
          </tbody>
        </n-table>
        <div class="table-pagination">
          <n-pagination
            :page="importRunsPager.page.value"
            :page-size="importRunsPager.pageSize.value"
            :item-count="importRunsPager.total.value"
            :page-sizes="importRunsPager.pageSizes"
            show-size-picker
            @update:page="importRunsPager.setPage"
            @update:page-size="importRunsPager.setPageSize"
          />
        </div>
      </div>
      <EmptyState
        v-else
        title="暂无导入历史"
        description="完成首次导入后，这里会显示当前可见范围内的全部批次"
      />
    </PanelCard>

    <PanelCard title="交易样本" description="表格预览保留当前交易记录的关键字段，便于校验数据质量">
      <div v-if="recordsPager.total.value" class="data-table-wrap">
        <n-table class="data-table" striped size="small" :single-line="false">
          <thead>
            <tr>
              <th>股票</th>
              <th>日期</th>
              <th>开</th>
              <th>最高</th>
              <th>最低</th>
              <th>收盘</th>
              <th>成交量</th>
              <th>成交额</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in recordsPager.pagedRows.value" :key="item.id">
              <td>{{ item.stock_code }}{{ item.stock_name ? ` · ${item.stock_name}` : "" }}</td>
              <td>{{ formatDate(item.trade_date) }}</td>
              <td>{{ formatNumberish(item.open, 2) }}</td>
              <td>{{ formatNumberish(item.high, 2) }}</td>
              <td>{{ formatNumberish(item.low, 2) }}</td>
              <td>{{ formatNumberish(item.close, 2) }}</td>
              <td>{{ formatCompact(item.volume, 2) }}</td>
              <td>{{ formatCompact(item.amount, 2) }}</td>
            </tr>
          </tbody>
        </n-table>
        <div class="table-pagination">
          <n-pagination
            :page="recordsPager.page.value"
            :page-size="recordsPager.pageSize.value"
            :item-count="recordsPager.total.value"
            :page-sizes="recordsPager.pageSizes"
            show-size-picker
            @update:page="recordsPager.setPage"
            @update:page-size="recordsPager.setPageSize"
          />
        </div>
      </div>
      <EmptyState
        v-else
        title="暂无样本记录"
        description="选择有效批次并点击刷新预览后，这里会展示当前范围的交易记录样本"
      />
    </PanelCard>
  </div>
</template>


