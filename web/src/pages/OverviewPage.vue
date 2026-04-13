<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import type { EChartsOption } from "echarts";

import {
  deleteAdminUser,
  disableAdminUser,
  enableAdminUser,
  fetchAdminUsers,
  updateAdminUser,
} from "@/api/auth";
import { fetchHealth } from "@/api/health";
import { deleteImportRun, fetchImportRuns, fetchImportStats, uploadTradingFile } from "@/api/imports";
import { fetchTradingRecords, fetchTradingStocks } from "@/api/trading";
import type {
  AdminManagedUserRead,
  HealthResponse,
  ImportRunRead,
  ImportStatsRead,
  TradingRecordRead,
  TradingStockRead,
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
  formatDateTime,
  formatNumberish,
  getErrorMessage,
  toNumber,
  toStatusTagType,
} from "@/utils/format";


const runtime = useRuntimeStore();
const auth = useAuthStore();
const datasetContext = useDatasetContextStore();

const health = ref<HealthResponse | null>(null);
const stats = ref<ImportStatsRead | null>(null);
const importRuns = ref<ImportRunRead[]>([]);
const stocks = ref<TradingStockRead[]>([]);
const records = ref<TradingRecordRead[]>([]);

const loadingOverview = ref(false);
const loadingPreview = ref(false);
const uploading = ref(false);
const deletingRunId = ref<number | null>(null);
const error = ref("");
const selectedFile = ref<File | null>(null);
const ownerFilterInput = ref("");
const adminUserSearch = ref("");
const adminUsers = ref<AdminManagedUserRead[]>([]);
const loadingAdminUsers = ref(false);
const adminUserError = ref("");
const savingAdminUser = ref(false);
const editingAdminUser = ref<AdminManagedUserRead | null>(null);
const userDialogVisible = ref(false);

const uploadForm = reactive({
  datasetName: "",
});

const adminUserForm = reactive({
  username: "",
  password: "",
  is_active: true,
});

const workspaceForm = reactive({
  importRunId: undefined as number | undefined,
  stockCode: "",
  startDate: "",
  endDate: "",
  limitInput: "200",
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
    return "未选择数据集";
  }

  return `#${currentDataset.value.display_id} · ${currentDataset.value.dataset_name}`;
});

const summaryCards = computed<
  Array<{ label: string; value: string; hint: string; tone: "neutral" | "teal" | "orange" | "berry" }>
>(() => [
  {
    label: auth.isAdmin.value ? "当前范围批次" : "我的导入批次",
    value: String(stats.value?.total_runs ?? 0),
    hint: auth.isAdmin.value ? "管理员可切换全站或指定用户视角" : "当前账号可见范围内的全部导入批次",
    tone: "teal",
  },
  {
    label: "成功批次",
    value: String(stats.value?.completed_runs ?? 0),
    hint: "已完成解析入库的批次数量",
    tone: "orange",
  },
  {
    label: "累计记录数",
    value: formatCompact(stats.value?.total_records ?? null, 2),
    hint: "当前范围内已保留的交易记录总量",
    tone: "berry",
  },
  {
    label: "可用数据集",
    value: String(stats.value?.available_datasets ?? 0),
    hint: auth.isAdmin.value ? "当前管理视角内，成功且未删除的数据集去重后数量" : "当前账号成功且未删除的数据集数量",
    tone: "neutral",
  },
  {
    label: "当前股票数",
    value: String(stocks.value.length),
    hint: currentDataset.value ? `来自 ${currentDatasetLabel.value}` : "先在导入历史列表中选中一个数据集",
    tone: "teal",
  },
  {
    label: "当前样本点",
    value: String(records.value.length),
    hint: workspaceForm.stockCode ? `股票 ${workspaceForm.stockCode} 的预览样本` : "先选择一个股票",
    tone: "orange",
  },
]);

const monthlyChartOption = computed<EChartsOption | null>(() => {
  if (!stats.value?.monthly_imports.length) {
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
      left: 44,
      right: 24,
      top: 54,
      bottom: 28,
    },
    xAxis: {
      type: "category",
      data: stats.value.monthly_imports.map((item) => item.month),
      axisLabel: { color: "#59676b" },
    },
    yAxis: [
      {
        type: "value",
        name: "批次",
        axisLabel: { color: "#59676b" },
        splitLine: {
          lineStyle: { color: "rgba(89, 103, 107, 0.10)" },
        },
      },
      {
        type: "value",
        name: "记录数",
        axisLabel: { color: "#59676b" },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        type: "line",
        name: "导入批次",
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 3, color: "#0b8f8c" },
        areaStyle: { color: "rgba(11, 143, 140, 0.12)" },
        data: stats.value.monthly_imports.map((item) => item.runs),
      },
      {
        type: "bar",
        name: "导入记录数",
        yAxisIndex: 1,
        barMaxWidth: 22,
        itemStyle: {
          color: "#f28c28",
          borderRadius: [6, 6, 0, 0],
        },
        data: stats.value.monthly_imports.map((item) => item.records),
      },
    ],
  };
});

const previewChartOption = computed<EChartsOption | null>(() => {
  if (!records.value.length) {
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
      left: 44,
      right: 48,
      top: 56,
      bottom: 28,
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: records.value.map((item) => item.trade_date),
      axisLine: {
        lineStyle: { color: "rgba(89, 103, 107, 0.22)" },
      },
      axisLabel: { color: "#59676b" },
    },
    yAxis: [
      {
        type: "value",
        name: "收盘价",
        axisLabel: { color: "#59676b" },
        splitLine: {
          lineStyle: { color: "rgba(89, 103, 107, 0.10)" },
        },
      },
      {
        type: "value",
        name: "成交额",
        axisLabel: { color: "#59676b" },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        type: "line",
        name: "收盘价",
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 3, color: "#0b8f8c" },
        areaStyle: { color: "rgba(11, 143, 140, 0.12)" },
        data: records.value.map((item) => toNumber(item.close)),
      },
      {
        type: "bar",
        name: "成交额",
        yAxisIndex: 1,
        barMaxWidth: 18,
        itemStyle: {
          color: "#f28c28",
          borderRadius: [6, 6, 0, 0],
        },
        data: records.value.map((item) => (item.amount === null || item.amount === "" ? null : toNumber(item.amount))),
      },
    ],
  };
});

function parseLimitInput() {
  const normalized = workspaceForm.limitInput.trim();
  if (!normalized) {
    return undefined;
  }

  const parsed = Number(normalized);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error("预览样本数必须是正整数，留空则表示不限制。");
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

function rowClassName(payload: { row: ImportRunRead }) {
  return payload.row.id === workspaceForm.importRunId ? "is-current-dataset" : "";
}

function openAdminUserDialog(user: AdminManagedUserRead) {
  editingAdminUser.value = user;
  adminUserForm.username = user.username;
  adminUserForm.password = "";
  adminUserForm.is_active = user.is_active;
  userDialogVisible.value = true;
}

function closeAdminUserDialog() {
  editingAdminUser.value = null;
  adminUserForm.username = "";
  adminUserForm.password = "";
  adminUserForm.is_active = true;
  userDialogVisible.value = false;
}

function onFileSelected(event: Event) {
  const target = event.target as HTMLInputElement;
  selectedFile.value = target.files?.[0] || null;
}

async function loadPreview() {
  if (!workspaceForm.importRunId || !workspaceForm.stockCode) {
    records.value = [];
    applySharedScope();
    return;
  }

  loadingPreview.value = true;
  error.value = "";
  try {
    const rows = await fetchTradingRecords({
      import_run_id: workspaceForm.importRunId,
      stock_code: workspaceForm.stockCode,
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
    workspaceForm.stockCode = "";
    records.value = [];
    datasetContext.resetScope();
    return;
  }

  try {
    const rows = await fetchTradingStocks(workspaceForm.importRunId);
    stocks.value = rows;
    if (!rows.length) {
      workspaceForm.stockCode = "";
      records.value = [];
      applySharedScope();
      return;
    }

    if (!rows.some((row) => row.stock_code === workspaceForm.stockCode)) {
      workspaceForm.stockCode = rows[0].stock_code;
    }

    if (loadPreviewAfterSync) {
      await loadPreview();
    }
  } catch (err) {
    error.value = getErrorMessage(err);
  }
}

async function loadOverview(preferredRunId?: number) {
  loadingOverview.value = true;
  error.value = "";

  try {
    const [healthResponse, statsResponse, importRunResponse] = await Promise.all([
      fetchHealth(),
      fetchImportStats({ owner_user_id: appliedOwnerUserId.value }),
      fetchImportRuns({
        limit: 50,
        owner_user_id: appliedOwnerUserId.value,
      }),
    ]);

    health.value = healthResponse;
    stats.value = statsResponse;
    importRuns.value = importRunResponse;

    if (!importRunResponse.length) {
      workspaceForm.importRunId = undefined;
      workspaceForm.stockCode = "";
      stocks.value = [];
      records.value = [];
      datasetContext.resetScope();
      runtime.markSynced();
      return;
    }

    syncWorkspaceFromStore();
    const nextRunId =
      preferredRunId && importRunResponse.some((item) => item.id === preferredRunId)
        ? preferredRunId
        : workspaceForm.importRunId && importRunResponse.some((item) => item.id === workspaceForm.importRunId)
          ? workspaceForm.importRunId
          : importRunResponse[0].id;

    workspaceForm.importRunId = nextRunId;
    await loadStocks(true);
    runtime.markSynced();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    loadingOverview.value = false;
  }
}

async function loadAdminUsers() {
  if (!auth.isAdmin.value) {
    adminUsers.value = [];
    return;
  }

  loadingAdminUsers.value = true;
  adminUserError.value = "";
  try {
    adminUsers.value = await fetchAdminUsers(adminUserSearch.value.trim() || undefined);
  } catch (err) {
    adminUserError.value = getErrorMessage(err);
  } finally {
    loadingAdminUsers.value = false;
  }
}

async function submitUpload() {
  if (!selectedFile.value) {
    error.value = "请选择要上传的 CSV 或 XLSX 文件。";
    return;
  }
  if (!uploadForm.datasetName.trim()) {
    error.value = "请先填写数据集名称。";
    return;
  }

  uploading.value = true;
  error.value = "";
  try {
    const run = await uploadTradingFile({
      dataset_name: uploadForm.datasetName,
      file: selectedFile.value,
    });
    uploadForm.datasetName = "";
    selectedFile.value = null;
    workspaceForm.startDate = "";
    workspaceForm.endDate = "";
    await loadOverview(run.id);
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    uploading.value = false;
  }
}

async function removeRun(runId: number) {
  deletingRunId.value = runId;
  error.value = "";
  try {
    await deleteImportRun(runId);
    const preferredRunId = workspaceForm.importRunId === runId ? undefined : workspaceForm.importRunId;
    await loadOverview(preferredRunId);
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    deletingRunId.value = null;
  }
}

async function saveAdminUser() {
  if (!editingAdminUser.value) {
    return;
  }

  savingAdminUser.value = true;
  adminUserError.value = "";
  try {
    await updateAdminUser(editingAdminUser.value.id, {
      username: adminUserForm.username.trim(),
      password: adminUserForm.password.trim() || undefined,
      is_active: adminUserForm.is_active,
    });
    await loadAdminUsers();
    closeAdminUserDialog();
  } catch (err) {
    adminUserError.value = getErrorMessage(err);
  } finally {
    savingAdminUser.value = false;
  }
}

async function toggleAdminUserActive(user: AdminManagedUserRead) {
  adminUserError.value = "";
  try {
    if (user.is_active) {
      await disableAdminUser(user.id);
    } else {
      await enableAdminUser(user.id);
    }
    await loadAdminUsers();
  } catch (err) {
    adminUserError.value = getErrorMessage(err);
  }
}

async function removeAdminUser(user: AdminManagedUserRead) {
  if (!window.confirm(`确定删除用户 ${user.username} 吗？`)) {
    return;
  }

  adminUserError.value = "";
  try {
    await deleteAdminUser(user.id);
    await loadAdminUsers();
  } catch (err) {
    adminUserError.value = getErrorMessage(err);
  }
}

async function handleStockChange() {
  await loadPreview();
}

function handleRunRowClick(row: ImportRunRead) {
  workspaceForm.importRunId = row.id;
  workspaceForm.startDate = "";
  workspaceForm.endDate = "";
  void loadStocks(true);
}

onMounted(() => {
  syncWorkspaceFromStore();
  void loadOverview(workspaceForm.importRunId);
  void loadAdminUsers();
});
</script>

<template>
  <div class="page">
    <section class="page__header">
      <div>
        <div class="page__eyebrow">Overview / 系统总览</div>
        <h2 class="page__title">先切换数据集，再上传文件，随后直接浏览当前股票样本</h2>
        <p class="page__subtitle">
          当前页优先承接高交互操作。数据集切换以导入历史列表为主入口，工作台负责选择股票、时间范围和预览样本。
        </p>
      </div>
      <div class="page__actions">
        <el-button type="primary" :loading="loadingOverview" @click="loadOverview(workspaceForm.importRunId)">
          刷新总览
        </el-button>
      </div>
    </section>

    <el-alert
      v-if="error"
      title="系统总览加载失败"
      type="error"
      :description="error"
      show-icon
      :closable="false"
    />

    <PanelCard title="导入历史列表" description="点击某一行即可切换当前数据集；高亮行表示当前分析上下文。">
      <template #actions>
        <span class="pill">{{ importRuns.length }} 条批次</span>
      </template>

      <el-table
        v-if="importRuns.length"
        :data="importRuns"
        stripe
        class="data-table"
        max-height="460"
        :row-class-name="rowClassName"
        @row-click="handleRunRowClick"
      >
        <el-table-column prop="display_id" label="ID" width="90" />
        <el-table-column v-if="auth.isAdmin.value" prop="owner_username" label="用户" min-width="140" />
        <el-table-column prop="dataset_name" label="数据集名称" min-width="190" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="toStatusTagType(row.status)" effect="plain">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="导入时间" min-width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.started_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="record_count" label="记录数" width="110" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button
              text
              type="danger"
              :loading="deletingRunId === row.id"
              @click.stop="removeRun(row.id)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <EmptyState
        v-else
        title="还没有导入历史"
        description="上传第一份交易文件后，这里会开始积累数据集历史。"
      />
    </PanelCard>

    <PanelCard
      v-if="auth.isAdmin.value"
      title="用户管理"
      description="管理员可查看普通用户账号，编辑用户名、重置密码、启用/禁用账号，并在无业务数据时删除用户。"
    >
      <div class="overview-admin-tools">
        <el-input
          v-model="adminUserSearch"
          placeholder="按用户名搜索普通用户"
          clearable
          class="overview-owner-filter"
        />
        <el-button :loading="loadingAdminUsers" @click="loadAdminUsers">刷新用户列表</el-button>
      </div>

      <el-alert
        v-if="adminUserError"
        title="用户管理操作失败"
        type="error"
        :description="adminUserError"
        show-icon
        :closable="false"
      />

      <el-table v-if="adminUsers.length" :data="adminUsers" stripe class="data-table" max-height="420">
        <el-table-column prop="username" label="用户名" min-width="180" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" effect="plain">
              {{ row.is_active ? "启用" : "禁用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="业务数据" width="120">
          <template #default="{ row }">
            <el-tag :type="row.has_business_data ? 'warning' : 'success'" effect="plain">
              {{ row.has_business_data ? "有数据" : "无数据" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="最近登录" min-width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.last_login_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="260">
          <template #default="{ row }">
            <div class="overview-user-actions">
              <el-button text type="primary" @click="openAdminUserDialog(row)">编辑</el-button>
              <el-button text :type="row.is_active ? 'warning' : 'success'" @click="toggleAdminUserActive(row)">
                {{ row.is_active ? "禁用" : "启用" }}
              </el-button>
              <el-button text type="danger" :disabled="row.has_business_data" @click="removeAdminUser(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <EmptyState
        v-else
        title="当前没有普通用户"
        description="如果没有符合筛选条件的普通用户，这里会显示为空。"
      />
    </PanelCard>

    <section class="page__grid page__grid--double">
      <PanelCard title="当前数据集工作台" description="当前数据集由上方导入历史列表决定，这里只负责股票和时间范围。">
        <template #actions>
          <span class="pill">{{ currentDatasetLabel }}</span>
        </template>

        <div class="overview-current">
          <div class="overview-current__line">
            <span class="muted">当前数据集</span>
            <strong>{{ currentDataset?.dataset_name || "未选择" }}</strong>
          </div>
          <div class="overview-current__line">
            <span class="muted">当前范围</span>
            <strong>{{ workspaceForm.startDate || "起始不限" }} ~ {{ workspaceForm.endDate || "结束不限" }}</strong>
          </div>
        </div>

        <el-form class="overview-form" label-position="top">
          <el-form-item label="当前股票">
            <el-select v-model="workspaceForm.stockCode" placeholder="选择股票" filterable @change="handleStockChange">
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
              <el-date-picker
                v-model="workspaceForm.startDate"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="开始日期"
                clearable
              />
            </el-form-item>
            <el-form-item label="结束日期">
              <el-date-picker
                v-model="workspaceForm.endDate"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="结束日期"
                clearable
              />
            </el-form-item>
          </div>

          <el-form-item label="预览样本数">
            <el-input v-model="workspaceForm.limitInput" placeholder="留空表示不限制，例如 200" clearable />
          </el-form-item>
        </el-form>

        <div class="overview-actions-row">
          <el-button type="primary" plain :loading="loadingPreview" @click="loadPreview">应用当前数据集</el-button>
          <span class="muted">当前选择会同步给 Analysis Center 和 Algo Radar。</span>
        </div>
      </PanelCard>

      <PanelCard title="上传交易文件" description="支持常见列头自动识别的 CSV / XLSX 文件。">
        <template #actions>
          <a class="overview-template-link" href="/trading_import_template.csv" download>下载模板</a>
        </template>

        <el-form class="overview-form" label-position="top">
          <el-form-item label="数据集名称">
            <el-input v-model="uploadForm.datasetName" placeholder="例如 2026_Q1_stock_backtest" />
          </el-form-item>
          <el-form-item label="上传文件">
            <label class="overview-file-input">
              <input type="file" accept=".csv,.xlsx" @change="onFileSelected" />
              <span>{{ selectedFile?.name || "选择 CSV / XLSX 文件" }}</span>
            </label>
          </el-form-item>
        </el-form>

        <div class="overview-actions-row">
          <el-button type="primary" :loading="uploading" @click="submitUpload">上传并导入</el-button>
          <span class="muted">
            必要列：股票代码、日期、开盘、最高、最低、收盘、成交量；可选列：股票名称、成交额、换手率
          </span>
        </div>
      </PanelCard>
    </section>

    <section class="page__grid page__grid--double">
      <PanelCard title="当前数据集预览" description="折线显示收盘价，柱状图显示成交额。">
        <EChartPanel v-if="previewChartOption" :option="previewChartOption" :loading="loadingPreview" height="380px" />
        <EmptyState
          v-else
          title="还没有可预览的数据"
          description="先在导入历史列表选中一个数据集，再选择股票，这里会展示时间序列预览。"
        />
      </PanelCard>

      <PanelCard title="当前样本明细" description="用于核对当前上下文中的股票样本。">
        <el-table v-if="records.length" :data="[...records].slice().reverse()" stripe class="data-table" max-height="420">
          <el-table-column prop="trade_date" label="交易日" min-width="120" />
          <el-table-column prop="stock_code" label="股票代码" min-width="120" />
          <el-table-column label="收盘价" min-width="120">
            <template #default="{ row }">
              {{ formatNumberish(row.close, 4) }}
            </template>
          </el-table-column>
          <el-table-column label="成交量" min-width="140">
            <template #default="{ row }">
              {{ formatNumberish(row.volume, 4) }}
            </template>
          </el-table-column>
          <el-table-column label="成交额" min-width="140">
            <template #default="{ row }">
              {{ formatNumberish(row.amount, 4) }}
            </template>
          </el-table-column>
        </el-table>
        <EmptyState
          v-else
          title="还没有读取到样本记录"
          description="应用当前数据集后，这里会展示当前股票的样本明细。"
        />
      </PanelCard>
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

    <PanelCard
      v-if="auth.isAdmin.value"
      title="管理员视角"
      description="管理员可切换用户范围，并查看用户级汇总与完整系统状态。"
    >
      <div class="overview-admin-tools">
        <el-input
          v-model="ownerFilterInput"
          placeholder="输入用户 ID，切换到该用户视角"
          clearable
          class="overview-owner-filter"
        />
        <el-button :loading="loadingOverview" @click="loadOverview(workspaceForm.importRunId)">应用管理员筛选</el-button>
      </div>

      <el-table v-if="stats?.owner_summaries.length" :data="stats.owner_summaries" stripe class="data-table" max-height="420">
        <el-table-column prop="owner_user_id" label="用户 ID" width="120" />
        <el-table-column prop="owner_username" label="用户名" min-width="180" />
        <el-table-column prop="runs" label="批次" width="120" />
        <el-table-column prop="records" label="记录数" min-width="140" />
      </el-table>
      <EmptyState
        v-else
        title="当前没有可展示的用户汇总"
        description="管理员未切到全站视角，或当前没有导入数据时，这里会显示为空。"
      />
    </PanelCard>

    <section class="page__grid page__grid--double">
      <PanelCard
        :title="auth.isAdmin.value ? '系统健康状态' : '系统可用状态'"
        :description="auth.isAdmin.value ? '管理员可查看完整服务与数据库状态。' : '普通用户仅看到是否可正常使用。'"
      >
        <div v-if="health" class="overview-health">
          <div class="overview-health__line">
            <span class="muted">状态</span>
            <el-tag :type="toStatusTagType(health.status)" effect="dark">{{ health.status }}</el-tag>
          </div>

          <template v-if="auth.isAdmin.value">
            <div class="overview-health__line">
              <span class="muted">环境</span>
              <strong>{{ health.environment }}</strong>
            </div>
            <div class="overview-health__line">
              <span class="muted">数据库</span>
              <strong>{{ health.database_ok ? "连接正常" : "连接失败" }}</strong>
            </div>
            <div class="overview-health__detail">{{ health.detail }}</div>
          </template>

          <template v-else>
            <div class="overview-health__detail">
              {{ health.status === "ok" ? "当前系统服务可正常使用。" : "当前系统存在异常，请稍后重试。" }}
            </div>
          </template>
        </div>
        <EmptyState
          v-else
          title="等待健康检查结果"
          description="点击刷新后会展示当前后端和数据库的可用状态。"
        />
      </PanelCard>

      <PanelCard title="按月导入趋势" description="默认按当前可见范围统计，不包含已删除的批次。">
        <EChartPanel v-if="monthlyChartOption" :option="monthlyChartOption" :loading="loadingOverview" height="340px" />
        <EmptyState
          v-else
          title="还没有导入趋势数据"
          description="上传交易数据文件后，这里会按月份汇总导入批次和记录数。"
        />
      </PanelCard>
    </section>

    <el-dialog v-model="userDialogVisible" title="编辑普通用户" width="460px" destroy-on-close>
      <el-form class="overview-form" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="adminUserForm.username" placeholder="输入新的用户名" />
        </el-form-item>
        <el-form-item label="重置密码">
          <el-input v-model="adminUserForm.password" type="password" show-password placeholder="留空表示不重置密码" />
        </el-form-item>
        <el-form-item label="账号状态">
          <el-switch v-model="adminUserForm.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="overview-user-actions">
          <el-button @click="closeAdminUserDialog">取消</el-button>
          <el-button type="primary" :loading="savingAdminUser" @click="saveAdminUser">保存修改</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.overview-owner-filter {
  width: min(260px, 100%);
}

.overview-admin-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
}

.overview-user-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.overview-current {
  display: grid;
  gap: 10px;
  margin-bottom: 16px;
}

.overview-current__line {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding-bottom: 10px;
  border-bottom: 1px dashed rgba(89, 103, 107, 0.18);
}

.overview-health {
  display: grid;
  gap: 14px;
}

.overview-health__line {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding-bottom: 10px;
  border-bottom: 1px dashed rgba(89, 103, 107, 0.18);
}

.overview-health__detail {
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(11, 143, 140, 0.06);
  color: var(--text-secondary);
  line-height: 1.7;
}

.overview-template-link {
  color: var(--accent-teal);
  font-weight: 700;
}

.overview-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px 14px;
}

.overview-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.date-range-group {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 10px;
  grid-column: 1 / -1;
}

.overview-file-input {
  display: flex;
  align-items: center;
  min-height: 40px;
  padding: 0 14px;
  border: 1px dashed rgba(24, 50, 47, 0.18);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--text-secondary);
  cursor: pointer;
}

.overview-file-input input {
  display: none;
}

.overview-actions-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-top: 18px;
}

:deep(.is-current-dataset) {
  --el-table-tr-bg-color: rgba(11, 143, 140, 0.08);
}

@media (max-width: 768px) {
  .date-range-group {
    grid-template-columns: 1fr;
  }
}
</style>
