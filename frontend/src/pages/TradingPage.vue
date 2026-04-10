<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import type { EChartsOption } from "echarts";

import { deleteImportRun, fetchImportRuns, uploadTradingFile } from "@/api/imports";
import { fetchTradingInstruments, fetchTradingRangeKthVolume, fetchTradingRangeMaxAmount, fetchTradingRecords } from "@/api/trading";
import type {
  ImportRunRead,
  TradingInstrumentRead,
  TradingRangeKthVolumeRead,
  TradingRangeMaxAmountRead,
  TradingRecordRead,
} from "@/api/types";
import EChartPanel from "@/components/EChartPanel.vue";
import EmptyState from "@/components/EmptyState.vue";
import PanelCard from "@/components/PanelCard.vue";
import StatCard from "@/components/StatCard.vue";
import { useAuthStore } from "@/stores/auth";
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


const runtime = useRuntimeStore();
const auth = useAuthStore();
const loadingRuns = ref(false);
const loadingAnalysis = ref(false);
const uploading = ref(false);
const deletingRunId = ref<number | null>(null);
const error = ref("");
const algoNotice = ref("");
const algoKthNotice = ref("");
const selectedFile = ref<File | null>(null);
const importRuns = ref<ImportRunRead[]>([]);
const instruments = ref<TradingInstrumentRead[]>([]);
const records = ref<TradingRecordRead[]>([]);
const algoResult = ref<TradingRangeMaxAmountRead | null>(null);
const algoKthResult = ref<TradingRangeKthVolumeRead | null>(null);
const importRunDisplayIdMap = computed(() => new Map(importRuns.value.map((item) => [item.id, item.display_id])));

const uploadForm = reactive({
  datasetName: "",
  assetClass: "stock",
});

const queryForm = reactive({
  importRunId: undefined as number | undefined,
  instrumentCode: "",
  startDate: "",
  endDate: "",
  kInput: "1",
  kthMethod: "persistent_segment_tree" as "persistent_segment_tree" | "t_digest",
  limitInput: "",
});

const kthMethodOptions = [
  { label: "精确结果", value: "persistent_segment_tree" as const },
  { label: "近似结果", value: "t_digest" as const },
];

const cards = computed(() => [
  {
    label: "可见批次",
    value: String(importRuns.value.length),
    hint: auth.isAdmin.value ? "管理员默认查看所有未删除批次" : "当前用户自己的导入历史",
    tone: "teal" as const,
  },
  {
    label: "当前标的数",
    value: String(instruments.value.length),
    hint: queryForm.importRunId ? `来自批次 ${formatImportRunDisplayLabel(queryForm.importRunId)}` : "先选择一个导入批次",
    tone: "orange" as const,
  },
  {
    label: "当前样本点",
    value: String(records.value.length),
    hint: queryForm.instrumentCode ? `标的 ${queryForm.instrumentCode}` : "先选择标的",
    tone: "neutral" as const,
  },
  {
    label: "区间最大成交额",
    value: algoResult.value ? formatCompact(algoResult.value.max_amount, 2) : "--",
    hint: algoResult.value ? `命中 ${algoResult.value.matches.length} 个交易日` : algoNotice.value || "等待分析",
    tone: "berry" as const,
  },
]);

const chartOption = computed<EChartsOption | null>(() => {
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
        lineStyle: {
          width: 3,
          color: "#0b8f8c",
        },
        areaStyle: {
          color: "rgba(11, 143, 140, 0.12)",
        },
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
        data: records.value.map((item) => toNumber(item.amount)),
      },
    ],
  };
});

function parseLimitInput() {
  const normalized = queryForm.limitInput.trim();
  if (!normalized) {
    return undefined;
  }

  const parsed = Number(normalized);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error("样本数限制必须是正整数，留空则表示不限制。");
  }
  return parsed;
}

function parseKInput() {
  const normalized = queryForm.kInput.trim();
  if (!normalized) {
    throw new Error("K 值必须是正整数。");
  }

  const parsed = Number(normalized);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error("K 值必须是正整数。");
  }
  return parsed;
}

function onFileSelected(event: Event) {
  const target = event.target as HTMLInputElement;
  selectedFile.value = target.files?.[0] || null;
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
      queryForm.instrumentCode = "";
      instruments.value = [];
      records.value = [];
      algoResult.value = null;
      algoKthResult.value = null;
      algoNotice.value = "";
      algoKthNotice.value = "";
      return;
    }

    const candidateId =
      preferredRunId && rows.some((row) => row.id === preferredRunId)
        ? preferredRunId
        : queryForm.importRunId && rows.some((row) => row.id === queryForm.importRunId)
          ? queryForm.importRunId
          : rows[0].id;
    queryForm.importRunId = candidateId;
    await loadInstruments();
    runtime.markSynced();
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
    records.value = [];
    algoResult.value = null;
    algoKthResult.value = null;
    algoNotice.value = "";
    algoKthNotice.value = "";
    return;
  }

  try {
    const rows = await fetchTradingInstruments(queryForm.importRunId);
    instruments.value = rows;
    if (!rows.length) {
      queryForm.instrumentCode = "";
      records.value = [];
      algoResult.value = null;
      algoKthResult.value = null;
      algoNotice.value = "当前导入批次没有可分析的标的。";
      algoKthNotice.value = algoNotice.value;
      return;
    }

    if (!rows.some((row) => row.instrument_code === queryForm.instrumentCode)) {
      queryForm.instrumentCode = rows[0].instrument_code;
    }
    await runAnalysis();
  } catch (err) {
    error.value = getErrorMessage(err);
  }
}

async function runAnalysis() {
  if (!queryForm.importRunId || !queryForm.instrumentCode) {
    records.value = [];
    algoResult.value = null;
    algoKthResult.value = null;
    return;
  }

  loadingAnalysis.value = true;
  error.value = "";
  algoNotice.value = "";
  algoKthNotice.value = "";

  try {
    const limit = parseLimitInput();
    const rows = await fetchTradingRecords({
      import_run_id: queryForm.importRunId,
      instrument_code: queryForm.instrumentCode,
      start_date: queryForm.startDate || undefined,
      end_date: queryForm.endDate || undefined,
      limit,
    });
    records.value = rows;

    if (!rows.length) {
      algoResult.value = null;
      algoKthResult.value = null;
      algoNotice.value = "当前条件下没有匹配的交易记录。";
      algoKthNotice.value = algoNotice.value;
      runtime.markSynced();
      return;
    }

    const startDate = queryForm.startDate || rows[0].trade_date;
    const endDate = queryForm.endDate || rows[rows.length - 1].trade_date;

    try {
      algoResult.value = await fetchTradingRangeMaxAmount({
        import_run_id: queryForm.importRunId,
        instrument_code: queryForm.instrumentCode,
        start_date: startDate,
        end_date: endDate,
      });
    } catch (err) {
      algoResult.value = null;
      algoNotice.value = getErrorMessage(err);
    }

    try {
      const k = parseKInput();
      algoKthResult.value = await fetchTradingRangeKthVolume({
        import_run_id: queryForm.importRunId,
        instrument_code: queryForm.instrumentCode,
        start_date: startDate,
        end_date: endDate,
        k,
        method: queryForm.kthMethod,
      });
    } catch (err) {
      algoKthResult.value = null;
      algoKthNotice.value = getErrorMessage(err);
    }
    runtime.markSynced();
  } catch (err) {
    error.value = getErrorMessage(err);
    algoResult.value = null;
    algoKthResult.value = null;
  } finally {
    loadingAnalysis.value = false;
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
      asset_class: uploadForm.assetClass,
      file: selectedFile.value,
    });
    uploadForm.datasetName = "";
    uploadForm.assetClass = "stock";
    selectedFile.value = null;
    await loadRuns(run.id);
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
    await loadRuns();
  } catch (err) {
    error.value = getErrorMessage(err);
  } finally {
    deletingRunId.value = null;
  }
}

function handleRunRowClick(row: ImportRunRead) {
  queryForm.importRunId = row.id;
  void loadInstruments();
}

onMounted(async () => {
  await loadRuns();
});
</script>

<template>
  <div class="page">
    <section class="page__header">
      <div>
        <div class="page__eyebrow">Trading</div>
        <h2 class="page__title">上传自己的交易文件，并按批次选择历史数据进行分析</h2>
        <p class="page__subtitle">
          v1 采用固定模板导入。一个文件对应一个历史批次，普通用户只看自己的数据，管理员默认可以查看所有用户的未删除批次。
        </p>
      </div>
    </section>

    <el-alert
      v-if="error"
      title="交易数据操作失败"
      type="error"
      :description="error"
      show-icon
      :closable="false"
    />

    <section class="page__grid page__grid--stats">
      <StatCard
        v-for="item in cards"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :tone="item.tone"
      />
    </section>

    <section class="page__grid page__grid--double">
      <PanelCard title="上传交易文件" description="支持固定列头模板的 CSV / XLSX 文件。">
        <template #actions>
          <a class="trading-template-link" href="/trading_import_template.csv" download>下载模板</a>
        </template>

        <el-form class="trading-upload-form" label-position="top">
          <el-form-item label="数据集名称">
            <el-input v-model="uploadForm.datasetName" placeholder="例如 2026_Q1_gold_backtest" />
          </el-form-item>
          <el-form-item label="资产类型">
            <el-select v-model="uploadForm.assetClass">
              <el-option label="股票" value="stock" />
              <el-option label="商品" value="commodity" />
            </el-select>
          </el-form-item>
          <el-form-item label="上传文件">
            <label class="trading-file-input">
              <input type="file" accept=".csv,.xlsx" @change="onFileSelected" />
              <span>{{ selectedFile?.name || "选择 CSV / XLSX 文件" }}</span>
            </label>
          </el-form-item>
        </el-form>

        <div class="trading-upload-actions">
          <el-button type="primary" :loading="uploading" @click="submitUpload">上传并导入</el-button>
          <span class="muted">固定列头：instrument_code, instrument_name, trade_date, open, high, low, close, volume, amount</span>
        </div>
      </PanelCard>

      <PanelCard title="选择批次与标的" description="先选择一个导入批次，再选择该批次中的标的进行分析。">
        <template #actions>
          <el-button type="primary" plain :loading="loadingAnalysis" @click="runAnalysis">刷新分析</el-button>
        </template>

        <el-form class="trading-query-form" label-position="top">
          <el-form-item label="导入批次">
            <el-select v-model="queryForm.importRunId" placeholder="选择批次" @change="loadInstruments">
              <el-option
                v-for="item in importRuns"
                :key="item.id"
                :label="`#${item.display_id} ${item.dataset_name} (${item.asset_class || '--'})`"
                :value="item.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="标的代码">
            <el-select v-model="queryForm.instrumentCode" placeholder="选择标的" @change="runAnalysis">
              <el-option
                v-for="item in instruments"
                :key="item.instrument_code"
                :label="`${item.instrument_code} ${item.instrument_name || ''}`"
                :value="item.instrument_code"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="开始日期">
            <el-date-picker
              v-model="queryForm.startDate"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="开始日期"
              clearable
            />
          </el-form-item>
          <el-form-item label="结束日期">
            <el-date-picker
              v-model="queryForm.endDate"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="结束日期"
              clearable
            />
          </el-form-item>
          <el-form-item label="样本数限制">
            <el-input v-model="queryForm.limitInput" placeholder="留空表示不限制，例如 200" clearable />
          </el-form-item>
          <el-form-item label="K 值">
            <el-input v-model="queryForm.kInput" placeholder="正整数，例如 1" clearable @change="runAnalysis" />
          </el-form-item>
          <el-form-item label="算法方式">
            <el-select v-model="queryForm.kthMethod" placeholder="选择算法方式" @change="runAnalysis">
              <el-option
                v-for="item in kthMethodOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
        </el-form>
      </PanelCard>
    </section>

    <section class="page__grid page__grid--double">
      <PanelCard title="价格与成交额趋势" description="折线显示收盘价，柱状图显示成交额。">
        <EChartPanel v-if="chartOption" :option="chartOption" :loading="loadingAnalysis" height="380px" />
        <EmptyState
          v-else
          title="还没有可视化数据"
          description="先上传一份交易文件，再选择批次和标的，这里就会展示时间序列图表。"
        />
      </PanelCard>

      <PanelCard title="区间最大成交额结果" description="来自系统算法接口 `/api/algo/trading/range-max-amount`。">
        <div v-if="algoResult" class="algo-result">
          <div class="algo-result__hero">
            <div class="algo-result__value">{{ formatNumberish(algoResult.max_amount, 4) }}</div>
            <div class="algo-result__meta">
              <span>批次 {{ formatImportRunDisplayLabel(algoResult.import_run_id) }}</span>
              <span>{{ algoResult.instrument_code }}</span>
              <span>{{ algoResult.start_date }} ~ {{ algoResult.end_date }}</span>
            </div>
          </div>

          <div class="algo-result__matches">
            <div v-for="match in algoResult.matches" :key="`${match.trade_date}-${match.series_index}`" class="algo-result__match">
              <span class="mono">idx {{ match.series_index }}</span>
              <strong>{{ formatDate(match.trade_date) }}</strong>
            </div>
          </div>
        </div>

        <EmptyState
          v-else
          :title="algoNotice ? '算法结果提示' : '等待算法结果'"
          :description="algoNotice || '选择有成交额数据的批次和标的后，这里会展示区间最大成交额和命中的日期。'"
        />
      </PanelCard>

      <PanelCard title="区间第 K 大成交量结果" description="来自系统算法接口 `/api/algo/trading/range-kth-volume`。">
        <div v-if="algoKthResult" class="algo-result">
          <div class="algo-result__hero algo-result__hero--teal">
            <div class="algo-result__value">{{ formatNumberish(algoKthResult.value, 4) }}</div>
            <div class="algo-result__meta">
              <span>批次 {{ formatImportRunDisplayLabel(algoKthResult.import_run_id) }}</span>
              <span>{{ algoKthResult.instrument_code }}</span>
              <span>K = {{ algoKthResult.k }}</span>
              <span>{{ algoKthResult.start_date }} ~ {{ algoKthResult.end_date }}</span>
            </div>
          </div>

          <div class="algo-result__badges">
            <span class="pill">{{ algoKthResult.is_approx ? "近似结果" : "精确结果" }}</span>
            <span class="pill">method: {{ algoKthResult.method }}</span>
          </div>

          <div v-if="algoKthResult.approximation_note" class="algo-result__note">
            {{ algoKthResult.approximation_note }}
          </div>

          <div v-if="algoKthResult.matches.length" class="algo-result__matches">
            <div
              v-for="match in algoKthResult.matches"
              :key="`kth-${match.trade_date}-${match.series_index}`"
              class="algo-result__match"
            >
              <span class="mono">idx {{ match.series_index }}</span>
              <strong>{{ formatDate(match.trade_date) }}</strong>
            </div>
          </div>
        </div>

        <EmptyState
          v-else
          :title="algoKthNotice ? '算法结果提示' : '等待算法结果'"
          :description="algoKthNotice || '输入 K 值并选择算法方式后，这里会展示区间第 K 大成交量。'"
        />
      </PanelCard>
    </section>

    <section class="page__grid page__grid--double">
      <PanelCard title="当前样本明细" description="倒序展示最近读取到的交易记录，用于核对图表与算法结果。">
        <el-table v-if="records.length" :data="[...records].slice().reverse()" stripe>
          <el-table-column prop="trade_date" label="Trade Date" min-width="120" />
          <el-table-column label="Close" min-width="120">
            <template #default="{ row }">
              {{ formatNumberish(row.close, 4) }}
            </template>
          </el-table-column>
          <el-table-column label="Volume" min-width="140">
            <template #default="{ row }">
              {{ formatNumberish(row.volume, 4) }}
            </template>
          </el-table-column>
          <el-table-column label="Amount" min-width="140">
            <template #default="{ row }">
              {{ formatNumberish(row.amount, 4) }}
            </template>
          </el-table-column>
        </el-table>
        <EmptyState
          v-else
          title="还没有读取到样本记录"
          description="分析接口返回数据后，这里会展示当前选中标的的时间序列样本。"
        />
      </PanelCard>

      <PanelCard title="导入历史列表" description="点击某一行即可切换到该批次，删除采用软删除。">
        <el-table
          v-if="importRuns.length"
          :data="importRuns"
          stripe
          @row-click="handleRunRowClick"
        >
          <el-table-column prop="display_id" label="ID" width="90" />
          <el-table-column v-if="auth.isAdmin.value" prop="owner_username" label="Owner" min-width="140" />
          <el-table-column prop="dataset_name" label="Dataset" min-width="170" />
          <el-table-column prop="asset_class" label="Asset" width="110" />
          <el-table-column label="Status" width="110">
            <template #default="{ row }">
              <el-tag :type="toStatusTagType(row.status)" effect="plain">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="Started At" min-width="180">
            <template #default="{ row }">
              {{ formatDateTime(row.started_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="record_count" label="Records" width="110" />
          <el-table-column label="Actions" width="120">
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
          description="上传第一份模板文件后，这里会自动出现属于你的历史导入批次。"
        />
      </PanelCard>
    </section>
  </div>
</template>

<style scoped>
.trading-template-link {
  color: var(--accent-teal);
  font-weight: 700;
}

.trading-upload-form,
.trading-query-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px 18px;
}

.trading-upload-form :deep(.el-form-item),
.trading-query-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.trading-file-input {
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

.trading-file-input input {
  display: none;
}

.trading-upload-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-top: 18px;
}

.algo-result {
  display: grid;
  gap: 18px;
}

.algo-result__hero {
  display: grid;
  gap: 12px;
  padding: 20px;
  border-radius: 22px;
  background: linear-gradient(135deg, rgba(185, 82, 79, 0.12), rgba(242, 140, 40, 0.12));
}

.algo-result__hero--teal {
  background: linear-gradient(135deg, rgba(11, 143, 140, 0.14), rgba(216, 176, 115, 0.18));
}

.algo-result__value {
  font-size: clamp(34px, 5vw, 48px);
  font-weight: 700;
  line-height: 1;
}

.algo-result__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: var(--text-secondary);
}

.algo-result__badges {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.algo-result__note {
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid rgba(11, 143, 140, 0.16);
  background: rgba(11, 143, 140, 0.08);
  color: #275c5b;
  line-height: 1.5;
}

.algo-result__matches {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.algo-result__match {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 132px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(185, 82, 79, 0.16);
  background: rgba(255, 255, 255, 0.72);
}
</style>
